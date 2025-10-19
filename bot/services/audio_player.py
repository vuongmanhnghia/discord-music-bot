import platform
import os
import asyncio
from typing import Optional
import discord
from discord import FFmpegPCMAudio, PCMVolumeTransformer

from ..domain.entities.song import Song
from ..config.service_constants import ServiceConstants
from ..pkg.logger import logger


class AudioPlayer:
    """
    Simplified audio player for a guild
    Manages playback state and auto-play next song
    """

    def __init__(
        self,
        voice_client: discord.VoiceClient,
        guild_id: int,
        queue_manager,  # Reference to QueueManager
        loop: asyncio.AbstractEventLoop,
    ):
        self.voice_client = voice_client
        self.guild_id = guild_id
        self.queue_manager = queue_manager
        self._loop = loop

        # Playback state
        self.current_song: Optional[Song] = None
        self.volume: float = 0.3
        self.is_playing: bool = False
        self.is_paused: bool = False

        self._is_disconnected: bool = False

    async def play_song(self, song: Song) -> bool:
        """Play a song (simplified with single retry)"""
        try:
            # ✅ 1. Wait for song processing
            if not await self._wait_for_song_ready(song):
                return False

            # ✅ 2. Refresh stream URL if needed
            if not await self._ensure_valid_stream_url(song):
                return False

            # ✅ 3. Create and play audio source
            return await self._start_playback(song)

        except Exception as e:
            logger.error(f"❌ Error playing {song.display_name}: {e}")
            return False

    async def _wait_for_song_ready(self, song: Song) -> bool:
        """Wait for song processing to complete"""
        if song.is_ready:
            return True

        if song.status.value != "processing":
            logger.error(f"❌ Cannot play unready song: {song.display_name}")
            return False

        # Wait up to 10 seconds for processing
        for _ in range(10):
            if song.is_ready:
                return True
            if song.status.value == "failed":
                logger.error(f"❌ Song processing failed: {song.display_name}")
                return False
            await asyncio.sleep(1)

        logger.error(f"⏱️ Timeout waiting for: {song.display_name}")
        return False

    async def _ensure_valid_stream_url(self, song: Song) -> bool:
        """Ensure stream URL is valid and fresh"""
        from ..services.stream_refresh import stream_refresh_service

        # Check if URL needs refresh
        if await stream_refresh_service.should_refresh_url(song):
            if not await stream_refresh_service.refresh_stream_url(song):
                logger.error(f"❌ Failed to refresh URL for: {song.display_name}")
                return False

        # Validate URL
        if not song.stream_url or not song.stream_url.startswith(
            ("http://", "https://")
        ):
            logger.error(f"❌ Invalid stream URL: {song.display_name}")
            return False

        return True

    async def _start_playback(self, song: Song) -> bool:
        """Start playing the audio"""
        # Create audio source
        audio_source = self._create_audio_source(song.stream_url)
        if not audio_source:
            logger.error(f"❌ Failed to create audio source for: {song.display_name}")
            return False

        # Check voice connection
        if not self.voice_client.is_connected():
            logger.error(f"❌ Voice client not connected in guild {self.guild_id}")
            return False

        # Stop current playback
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()
            await asyncio.sleep(0.3)

        # ✅ Play with auto-next callback
        self.voice_client.play(
            audio_source, after=lambda error: self._after_playback(error, song)
        )

        # Verify playback started
        await asyncio.sleep(0.1)
        if not self.voice_client.is_playing():
            logger.error(f"❌ Playback failed to start for: {song.display_name}")
            return False

        # Update state
        self.current_song = song
        self.is_playing = True
        self.is_paused = False

        logger.info(f"▶️ Now playing: {song.display_name}")
        return True

    def _after_playback(self, error, song: Song):
        """
        ✅ Callback after song finishes - AUTO-PLAY NEXT
        This is called by FFmpeg in a different thread
        """
        if error:
            logger.error(f"❌ Playback error for {song.display_name}: {error}")

        # Reset state
        self.is_playing = False
        self.is_paused = False
        self.current_song = None

        if self._is_disconnected:
            logger.debug(f"Skipping auto-play: guild {self.guild_id} is disconnecting")
            return

        asyncio.run_coroutine_threadsafe(self._play_next_song(), self._loop)

    async def _play_next_song(self):
        """Auto-play next song in queue (including loop)"""
        try:
            # Check voice connection
            if not self.voice_client or not self.voice_client.is_connected():
                logger.debug(
                    f"Skipping auto-play: voice client not connected in guild {self.guild_id}"
                )
                return
            if self._is_disconnected:
                logger.debug(
                    f"Skipping auto-play: guild {self.guild_id} is disconnecting"
                )
                return

            # Get next song (handles loop automatically)
            next_song = await self.queue_manager.next_song()

            if next_song:
                logger.info(f"🔄 Auto-playing next: {next_song.display_name}")
                success = await self.play_song(next_song)

                if not success:
                    if not self.voice_client.is_connected() or self._is_disconnected:
                        logger.debug(f"Skipping retry: disconnecting or not connected")
                        return

                    logger.warning(f"⚠️ Failed to play next song, trying again...")
                    # Try one more time
                    if self.voice_client.is_connected() and not self._is_disconnected:
                        await self.play_song(next_song)
            else:
                logger.info(f"📭 Queue finished for guild {self.guild_id}")

        except Exception as e:
            logger.error(f"❌ Error in auto-play next: {e}")

    def pause(self) -> bool:
        """Pause playback"""
        if not self.voice_client.is_playing():
            return False
        self.voice_client.pause()
        self.is_paused = True
        return True

    def resume(self) -> bool:
        """Resume playback"""
        if not self.voice_client.is_paused():
            return False
        self.voice_client.resume()
        self.is_paused = False
        return True

    def stop(self) -> bool:
        """Stop playback"""
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self._is_disconnected = True
            self.voice_client.stop()
            self.current_song = None
            self.is_playing = False
            self.is_paused = False
            return True
        return False

    def set_volume(self, volume: float) -> bool:
        """Set volume (0.0 to 1.0)"""
        volume = max(0.0, min(1.0, volume))
        self.volume = volume

        if self.voice_client.is_playing() and isinstance(
            self.voice_client.source, PCMVolumeTransformer
        ):
            self.voice_client.source.volume = volume
        return True

    def _create_audio_source(self, stream_url: str) -> Optional[discord.AudioSource]:
        """Create optimized FFmpeg audio source"""
        try:
            # Detect platform
            arch = platform.machine()
            is_low_power = arch in ["aarch64", "arm64", "armv7l"]

            # Get system resources
            try:
                import psutil

                memory_mb = psutil.virtual_memory().total // (1024 * 1024)
            except ImportError:
                memory_mb = 1024

            # ✅ Simple, optimized FFmpeg options
            if is_low_power or memory_mb < 2048:
                # Low-power devices
                before_opts = (
                    "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
                )
                opts = "-vn -bufsize 32k -maxrate 96k"
            else:
                # Normal devices
                before_opts = (
                    "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
                )
                opts = "-vn -bufsize 64k -maxrate 128k"

            audio_source = FFmpegPCMAudio(
                stream_url, before_options=before_opts, options=opts
            )

            return PCMVolumeTransformer(audio_source, volume=self.volume)

        except Exception as e:
            logger.error(f"❌ Error creating audio source: {e}")
            return None
