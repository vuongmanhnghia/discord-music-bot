import platform
import os
import asyncio
import subprocess
from typing import Optional, Callable
import discord
from discord import FFmpegPCMAudio, PCMVolumeTransformer

from ..domain.entities.song import Song
from ..config.service_constants import ServiceConstants
from ..pkg.logger import logger


class AudioPlayer:
    """
    Individual audio player for a guild
    Manages playback state and controls
    """

    def __init__(self, voice_client: discord.VoiceClient, guild_id: int):
        self.voice_client = voice_client
        self.guild_id = guild_id
        self.current_song: Optional[Song] = None
        self.current_playlist: Optional[str] = None
        self.volume: float = 0.3  # Default to 100% volume
        self.is_playing: bool = False
        self.is_paused: bool = False

        # Callbacks
        self.on_song_finished: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

        # Store event loop for async callbacks
        self._loop = None

    def _set_event_loop(self, loop):
        """Set event loop for async callbacks"""
        self._loop = loop

    async def play_song(self, song: Song, retry_count: int = 0) -> bool:
        """Play a song with retry mechanism and processing wait"""
        # Wait for processing completion if needed
        if not song.is_ready:
            if song.status.value == "processing":
                for wait_time in range(ServiceConstants.SONG_PROCESSING_WAIT_TIMEOUT):
                    if song.is_ready:
                        break
                    elif song.status.value == "failed":
                        logger.error(f"Song processing failed: {song.display_name}")
                        return False
                    await asyncio.sleep(1)

                if not song.is_ready:
                    logger.error(f"Timeout waiting for: {song.display_name}")
                    return False
            else:
                logger.error(f"Cannot play unready song: {song.display_name}")
                return False

        try:
            # Refresh stream URL if needed
            from ..services.stream_refresh import stream_refresh_service

            if await stream_refresh_service.should_refresh_url(song):
                refresh_success = await stream_refresh_service.refresh_stream_url(song)
                if not refresh_success:
                    if retry_count < 2:
                        await asyncio.sleep(5)
                        return await self.play_song(song, retry_count + 1)
                    return False

            # Validate stream URL
            if not song.stream_url or not song.stream_url.startswith(
                ("http://", "https://")
            ):
                logger.error(f"Invalid stream URL: {song.display_name}")
                return False

            # Create audio source
            audio_source = self._create_audio_source(song.stream_url)
            if not audio_source:
                if retry_count < ServiceConstants.PLAYBACK_RETRY_MAX_ATTEMPTS - 1:
                    await asyncio.sleep(ServiceConstants.PLAYBACK_RETRY_DELAY)
                    return await self.play_song(song, retry_count + 1)
                return False

            # Check voice client connection
            if not self.voice_client.is_connected():
                logger.error(f"Voice client not connected in guild {self.guild_id}")
                return False

            # Stop current playback if any
            if self.voice_client.is_playing() or self.voice_client.is_paused():
                self.voice_client.stop()
                await asyncio.sleep(0.5)

            # Start playing with enhanced error callback
            def after_callback(error):
                if error:
                    logger.error(f"Playback error: {error}")
                    # Trigger error callback for reconnection handling
                    if self.on_error and "voice" in str(error).lower():
                        try:
                            if self._loop:
                                self._loop.create_task(self.on_error(error, song))
                        except Exception as e:
                            logger.error(f"Error in error callback: {e}")
                self._on_playback_finished(error, song)

            self.voice_client.play(audio_source, after=after_callback)

            # Verify playback started
            await asyncio.sleep(0.1)
            if not self.voice_client.is_playing():
                logger.error("Playback failed to start")
                return False

            # Update state
            self.current_song = song
            self.is_playing = True
            self.is_paused = False
            return True

        except Exception as e:
            logger.error(f"Error playing {song.display_name}: {e}")

            # Retry on network errors
            if retry_count < ServiceConstants.PLAYBACK_RETRY_MAX_ATTEMPTS - 1:
                await asyncio.sleep(ServiceConstants.PLAYBACK_RETRY_DELAY)
                return await self.play_song(song, retry_count + 1)

            return False

    def pause(self) -> bool:
        """Pause current playback"""
        if not self.voice_client.is_playing():
            return False
        self.voice_client.pause()
        self.is_paused = True
        return True

    def resume(self) -> bool:
        """Resume paused playback"""
        if not self.voice_client.is_paused():
            return False
        self.voice_client.resume()
        self.is_paused = False
        return True

    def stop(self) -> bool:
        """Stop current playback"""
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()
            self._reset_state()
            return True
        return False

    def set_volume(self, volume: float) -> bool:
        """Set playback volume (0.0 to 1.0)"""
        volume = max(0.0, min(1.0, volume))
        self.volume = volume

        # Update volume if currently playing
        if self.voice_client.is_playing() and isinstance(
            self.voice_client.source, PCMVolumeTransformer
        ):
            self.voice_client.source.volume = volume
        return True

    def _create_audio_source(self, stream_url: str) -> Optional[discord.AudioSource]:
        """Create Discord audio source from stream URL"""
        try:
            arch = platform.machine()

            # Get system info
            try:
                import psutil

                cpu_count = psutil.cpu_count(logical=False) or 1
                memory_mb = psutil.virtual_memory().total // (1024 * 1024)
            except ImportError:
                cpu_count = os.cpu_count() or 1
                memory_mb = 1024

            # Base configuration
            base_before_options = (
                "-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
                "-multiple_requests 1 -loglevel error"
            )
            base_options = "-vn -avoid_negative_ts make_zero"

            # Platform-aware optimization
            if arch in ["aarch64", "arm64", "armv7l"] or memory_mb < 2048:
                threads, buffer_size, max_rate, timeout = 1, "32k", "96k", "20000000"
            else:
                threads, buffer_size, max_rate, timeout = 2, "64k", "128k", "30000000"

            before_options = f"{base_before_options} -timeout {timeout}"
            options = f"{base_options} -bufsize {buffer_size} -maxrate {max_rate} -threads {threads}"

            audio_source = FFmpegPCMAudio(
                stream_url, before_options=before_options, options=options
            )

            return PCMVolumeTransformer(audio_source, volume=self.volume)

        except FileNotFoundError:
            logger.error("FFmpeg not found! Please install FFmpeg")
            return None
        except subprocess.TimeoutExpired:
            logger.error("Timeout testing stream URL")
            return None
        except Exception as e:
            logger.error(f"Error creating audio source: {e}")
            return None

    def _on_playback_finished(self, error, song: Song):
        """Called when playback finishes"""
        if error:
            logger.error(f"Playback error for {song.display_name}: {error}")
            if self.on_error and self._loop:
                asyncio.run_coroutine_threadsafe(self.on_error(error, song), self._loop)

        self._reset_state()

        if self.on_song_finished and self._loop:
            asyncio.run_coroutine_threadsafe(self.on_song_finished(song), self._loop)

    def _reset_state(self):
        """Reset playback state"""
        self.current_song = None
        self.is_playing = False
        self.is_paused = False
