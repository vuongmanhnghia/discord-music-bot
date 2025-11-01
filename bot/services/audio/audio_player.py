import platform
import os
import asyncio
from typing import Optional
import discord
from discord import FFmpegPCMAudio, PCMVolumeTransformer
from ..stream_refresh import StreamRefreshService
from ...domain.entities.song import Song
from ...domain.entities.tracklist import Tracklist

from ...pkg.logger import logger


class AudioPlayer:
    """
    Simplified audio player for a guild
    Manages playback state and auto-play next song
    """

    def __init__(
        self,
        stream_refresh_service: StreamRefreshService,
        guild_id: int,
        voice_client: discord.VoiceClient,
        tracklist: Tracklist,
        loop: asyncio.AbstractEventLoop,
    ):
        self.voice_client = voice_client
        self.tracklist = tracklist
        self._loop = loop
        self.guild_id = guild_id

        # Playback state
        self.current_song: Optional[Song] = None
        self.volume: float = 0.3
        self.is_playing: bool = False
        self.is_paused: bool = False

        self._is_disconnected: bool = False

        # Services
        self.stream_refresh_service = stream_refresh_service

    async def play_song(self, song: Song) -> bool:
        """Play a song (simplified with single retry)"""
        try:
            # ✅ 1. Wait for song processing
            if not await self._wait_for_song_ready(song):
                return False

            # ✅ 2. Refresh stream URL if needed
            if await self.stream_refresh_service.should_refresh_url(song):
                refreshed = await self.stream_refresh_service.refresh_stream_url(song)
                if not refreshed:
                    logger.error(f"❌ Failed to refresh URL for: {song.display_name}")
                    return False

            # ✅ 3. Create and play audio source
            return await self._start_playback(song)

        except Exception as e:
            logger.error(f"❌ Error playing {song.display_name}: {e}")
            return False

    def _check_connection(self) -> bool:
        """Check if voice client is connected"""
        if not self.voice_client.is_connected() or self._is_disconnected:
            logger.error(f"❌ Voice client not connected")
            return False
        return True

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

    async def _start_playback(self, song: Song) -> bool:
        """Start playing the audio"""
        await self._wait_for_ffmpeg_terminate(timeout=1.0)
        # Create audio source
        audio_source = self._create_audio_source(song.stream_url)
        if not audio_source:
            logger.error(f"❌ Failed to create audio source for: {song.display_name}")
            return False

        # Check voice connection
        if not self._check_connection():
            return False

        # Stop current playback
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()
            await asyncio.sleep(0.3)

        # ✅ Play with auto-next callback
        self.voice_client.play(audio_source, after=lambda error: self._after_playback(error, song))

        # Verify playback started
        # await asyncio.sleep(0.1)
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
            error_str = str(error).lower()
            is_stream_error = any(keyword in error_str for keyword in ["403", "404", "expired", "unavailable", "http error"])

            if is_stream_error:
                logger.warning(f"⚠️ Stream error detected for {song.display_name}: {error}")
                # Schedule retry with fresh URL
                asyncio.run_coroutine_threadsafe(self._retry_with_fresh_url(song), self._loop)
                return
            else:
                logger.error(f"❌ Playback error for {song.display_name}: {error}")

        # Reset state
        self.is_playing = False
        self.is_paused = False
        self.current_song = None

        # ✅ Không auto-play nếu đang disconnect
        if self._is_disconnected:
            logger.debug(f"Skipping auto-play: guild {self.guild_id} is disconnecting")
            return

        # ✅ AUTO-PLAY NEXT SONG (including loop)
        asyncio.run_coroutine_threadsafe(self._play_next_song(), self._loop)

    async def _retry_with_fresh_url(self, song: Song):
        """Retry playing the same song with refreshed URL"""
        try:
            logger.info(f"🔄 Retrying with fresh URL: {song.display_name}")

            # Force refresh URL
            if await self.stream_refresh_service.refresh_stream_url(song):
                # Retry playback
                success = await self.play_song(song)
                if success:
                    logger.info(f"✅ Successfully retried: {song.display_name}")
                else:
                    logger.error(f"❌ Retry failed, skipping: {song.display_name}")
                    await self._play_next_song()
            else:
                logger.error(f"❌ Failed to refresh URL, skipping: {song.display_name}")
                await self._play_next_song()

        except Exception as e:
            logger.error(f"❌ Error in retry_with_fresh_url: {e}")
            await self._play_next_song()

    async def _play_next_song(self):
        """Auto-play next song in tracklist (including loop)"""
        try:
            # Get next song (handles loop automatically)
            next_song = await self.tracklist.next_song()

            if next_song:
                logger.info(f"🔄 Auto-playing next: {next_song.display_name}")
                success = await self.play_song(next_song)

                if not success:
                    if not self._check_connection():
                        return
                    logger.warning(f"⚠️ Failed to play next song, trying again...")
            else:
                logger.info(f"📭 Tracklist finished for guild {self.guild_id}")

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

    def stop(self, auto_play_next: bool = True) -> bool:
        """
        Stop playback

        Args:
            auto_play_next: If True, triggers auto-play next song via callback.
                          If False, prevents auto-play (used for manual skip/stop).
        """
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            # Prevent auto-play if requested (for manual operations)
            if not auto_play_next:
                self._is_disconnected = True

            self.voice_client.stop()
            self.current_song = None
            self.is_playing = False
            self.is_paused = False

            # Re-enable auto-play after stop completes
            if not auto_play_next:
                # Reset after a short delay to allow stop to complete
                asyncio.create_task(self._reset_auto_play_flag())

            return True
        return False

    async def _reset_auto_play_flag(self):
        """Reset auto-play flag after stop completes"""
        await asyncio.sleep(0.5)
        self._is_disconnected = False

    def set_volume(self, volume: float) -> bool:
        """Set volume (0.0 to 1.0)"""
        volume = max(0.0, min(1.0, volume))
        self.volume = volume

        if self.voice_client.is_playing() and isinstance(self.voice_client.source, PCMVolumeTransformer):
            self.voice_client.source.volume = volume
        return True

    def mark_disconnected(self) -> None:
        """Mark player as disconnected to prevent auto-play"""
        self._is_disconnected = True
        logger.debug(f"🔒 Audio player marked as disconnected for guild {self.guild_id}")

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
                logger.warning("⚠️ psutil not installed, assuming low memory for audio optimization")

            before_opts = "-reconnect 1 " "-reconnect_streamed 1 " "-reconnect_delay_max 5 " "-reconnect_on_network_error 1 " "-reconnect_on_http_error 4xx,5xx"

            if is_low_power or memory_mb < 2048:
                opts = "-vn -bufsize 32k -maxrate 96k"
            else:
                opts = "-vn -bufsize 64k -maxrate 128k"

            audio_source = FFmpegPCMAudio(
                stream_url,
                before_options=before_opts,
                options=opts,
                executable="ffmpeg",
            )

            return PCMVolumeTransformer(audio_source, volume=self.volume)

        except Exception as e:
            logger.error(f"❌ Error creating audio source {stream_url}: {e}")
            return None

    async def _wait_for_ffmpeg_terminate(self, timeout: float = 1.0) -> bool:
        """
        Poll underlying FFmpeg subprocess (if any) and wait until it exits or timeout.
        This helps avoid race when stop() was called but the ffmpeg process is still
        terminating and a new playback is started immediately.
        """
        try:
            source = getattr(self.voice_client, "source", None)
            # If wrapped in PCMVolumeTransformer, get inner source
            inner = getattr(source, "source", None) if source is not None else None
            ff = inner or source

            proc = None
            if ff is not None:
                proc = getattr(ff, "process", None) or getattr(ff, "proc", None)

            if not proc:
                return True

            start = self._loop.time()
            while proc.poll() is None:
                if (self._loop.time() - start) > timeout:
                    return False
                await asyncio.sleep(0.05)
            return True
        except Exception:
            return True