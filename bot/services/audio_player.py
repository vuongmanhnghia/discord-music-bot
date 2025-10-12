import platform
import os
import asyncio
import subprocess
from typing import Optional, Callable, Union
import discord
from discord import FFmpegPCMAudio, PCMVolumeTransformer

from ..domain.entities.song import Song

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
        # If song is not ready, try to wait for processing completion
        if not song.is_ready:
            if song.status.value == "processing":
                logger.info(
                    f"⏳ Song is processing, waiting for completion: {song.display_name}"
                )

                # Wait up to 30 seconds for processing to complete
                for wait_time in range(30):
                    if song.is_ready:
                        logger.info(
                            f"✅ Song processing completed after {wait_time}s: {song.display_name}"
                        )
                        break
                    elif song.status.value == "failed":
                        logger.error(f"❌ Song processing failed: {song.display_name}")
                        return False

                    await asyncio.sleep(1)

                # If still not ready after waiting, fail
                if not song.is_ready:
                    logger.error(
                        f"⏰ Timeout waiting for song processing: {song.display_name}"
                    )
                    return False
            else:
                logger.error(
                    f"Cannot play song that is not ready: {song.display_name} (status: {song.status.value})"
                )
                return False

        logger.info(
            f"Starting playback: {song.display_name} in guild {self.guild_id} (attempt {retry_count + 1})"
        )

        try:
            # Check if stream URL needs refresh (for 24/7 operation)
            from ..services.stream_refresh import stream_refresh_service

            if await stream_refresh_service.should_refresh_url(song):
                logger.info(
                    f"🔄 Stream URL expired, refreshing for: {song.display_name}"
                )
                refresh_success = await stream_refresh_service.refresh_stream_url(song)

                if not refresh_success:
                    logger.error(
                        f"❌ Failed to refresh stream URL for: {song.display_name}"
                    )
                    if retry_count < 2:
                        await asyncio.sleep(5)  # Wait before retry
                        return await self.play_song(song, retry_count + 1)
                    return False

            # Validate stream URL
            if not song.stream_url or not song.stream_url.startswith(
                ("http://", "https://")
            ):
                logger.error(f"Invalid stream URL for song: {song.display_name}")
                return False

            logger.debug(f"Creating audio source for: {song.stream_url}")
            logger.info(
                f"🔊 Stream URL: {song.stream_url[:100]}..."
            )  # Log first 100 chars

            # Create audio source with timeout protection
            audio_source = self._create_audio_source(song.stream_url)
            if not audio_source:
                logger.error(f"Failed to create audio source for: {song.display_name}")

                # Retry logic for stream issues
                if retry_count < 2:  # Max 3 attempts
                    logger.info(f"Retrying playback for: {song.display_name}")
                    await asyncio.sleep(2)  # Wait 2 seconds before retry
                    return await self.play_song(song, retry_count + 1)
                else:
                    return False

            logger.info(
                f"✅ Audio source created successfully, type: {type(audio_source).__name__}"
            )

            # Check voice client connection
            if not self.voice_client.is_connected():
                logger.error(f"❌ Voice client not connected in guild {self.guild_id}")
                return False

            logger.info(
                f"✅ Voice client connected to channel: {self.voice_client.channel.name if self.voice_client.channel else 'Unknown'}"
            )

            # Stop current playback if any
            if self.voice_client.is_playing() or self.voice_client.is_paused():
                logger.info("🛑 Stopping current playback")
                self.voice_client.stop()
                await asyncio.sleep(0.5)

            # Start playing with enhanced error callback
            def after_callback(error):
                if error:
                    logger.error(f"Discord playback error: {error}")
                    # Check if it's a network/stream error
                    if (
                        "Connection reset" in str(error)
                        or "corrupt" in str(error).lower()
                    ):
                        logger.warning(
                            f"Stream error detected for: {song.display_name}"
                        )
                    # Check for voice connection errors
                    elif (
                        "voice" in str(error).lower()
                        or "websocket" in str(error).lower()
                    ):
                        logger.warning(f"Voice connection error detected: {error}")
                        # Trigger error callback for reconnection handling
                        if self.on_error:
                            try:
                                if self._loop:
                                    self._loop.create_task(self.on_error(error, song))
                            except Exception as e:
                                logger.error(f"Error in error callback: {e}")

                self._on_playback_finished(error, song)

            logger.info(f"🎵 Calling voice_client.play() with volume={self.volume:.2f}")
            self.voice_client.play(audio_source, after=after_callback)

            # Verify playback started
            await asyncio.sleep(0.1)  # Give it a moment to start
            if not self.voice_client.is_playing():
                logger.error(
                    "❌ voice_client.play() called but is_playing() returns False!"
                )
                return False

            logger.info(f"✅ voice_client.is_playing() = True")

            # Update state
            self.current_song = song
            self.is_playing = True
            self.is_paused = False

            logger.info(f"Successfully started playback: {song.display_name}")
            return True

        except Exception as e:
            logger.error(f"Error playing song {song.display_name}: {e}")

            # Retry on network errors
            if retry_count < 2 and (
                "Connection reset" in str(e) or "corrupt" in str(e).lower()
            ):
                logger.info(f"Retrying due to network error: {song.display_name}")
                await asyncio.sleep(2)
                return await self.play_song(song, retry_count + 1)

            return False

    def pause(self) -> bool:
        """Pause current playback"""
        if not self.voice_client.is_playing():
            return False

        self.voice_client.pause()
        self.is_paused = True
        logger.info(f"Paused playback in guild {self.guild_id}")
        return True

    def resume(self) -> bool:
        """Resume paused playback"""
        if not self.voice_client.is_paused():
            return False

        self.voice_client.resume()
        self.is_paused = False
        logger.info(f"Resumed playback in guild {self.guild_id}")
        return True

    def stop(self) -> bool:
        """Stop current playback"""
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()
            self._reset_state()
            logger.info(f"Stopped playback in guild {self.guild_id}")
            return True
        return False

    def set_volume(self, volume: float) -> bool:
        """Set playback volume (0.0 to 1.0)"""
        volume = max(0.0, min(1.0, volume))
        self.volume = volume

        # If currently playing with volume transformer, update it
        if self.voice_client.is_playing() and isinstance(
            self.voice_client.source, PCMVolumeTransformer
        ):
            self.voice_client.source.volume = volume

        logger.debug(f"Set volume to {volume:.1%} in guild {self.guild_id}")
        return True

    def _create_audio_source(self, stream_url: str) -> Optional[discord.AudioSource]:
        """Create Discord audio source from stream URL with better error handling"""
        try:
            # Smart FFmpeg options with automatic platform optimization
            arch = platform.machine()

            # Try to get system info, fallback to defaults if psutil not available
            try:
                import psutil

                cpu_count = psutil.cpu_count(logical=False) or 1
                memory_mb = psutil.virtual_memory().total // (1024 * 1024)
            except ImportError:
                cpu_count = os.cpu_count() or 1
                # Estimate memory from container limits or assume moderate
                memory_mb = 1024  # Default assumption

            # Base configuration with improved reconnection and error handling
            base_before_options = (
                "-nostdin "
                "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
                "-multiple_requests 1 "  # Enable multiple HTTP requests
                "-loglevel error"  # Only show errors, hide TLS warnings
            )
            base_options = "-vn -avoid_negative_ts make_zero"

            # Platform-aware optimization
            if arch in ["aarch64", "arm64", "armv7l"] or memory_mb < 2048:
                # ARM/Low-memory optimization (Raspberry Pi)
                threads = min(1, cpu_count)
                buffer_size = "32k"
                max_rate = "96k"
                timeout = "20000000"
                logger.debug(
                    f"🍓 ARM/Low-mem optimization: {threads} threads, {buffer_size} buffer"
                )
            else:
                # x86_64/High-memory optimization
                threads = min(2, cpu_count)
                buffer_size = "64k"
                max_rate = "128k"
                timeout = "30000000"
                logger.debug(
                    f"💻 x86_64/High-mem optimization: {threads} threads, {buffer_size} buffer"
                )

            before_options = f"{base_before_options} -timeout {timeout}"
            options = f"{base_options} -bufsize {buffer_size} -maxrate {max_rate} -threads {threads}"

            logger.debug(
                f"Creating FFmpeg source with enhanced options: before_options='{before_options}', options='{options}'"
            )

            # Create audio source - let FFmpeg output go through normally
            audio_source = FFmpegPCMAudio(
                stream_url, before_options=before_options, options=options
            )

            # Always apply volume transformation for better control
            audio_source = PCMVolumeTransformer(audio_source, volume=self.volume)

            logger.debug("Audio source created successfully")
            return audio_source

        except FileNotFoundError:
            logger.error("FFmpeg not found! Please install FFmpeg")
            return None
        except subprocess.TimeoutExpired:
            logger.error("Timeout testing stream URL")
            return None
        except Exception as e:
            logger.error(f"Error creating audio source: {e}")
            logger.debug(f"Stream URL: {stream_url}")
            return None

    def _on_playback_finished(self, error, song: Song):
        """Called when playback finishes"""
        if error:
            logger.error(f"Playback error for {song.display_name}: {error}")
            if self.on_error and self._loop:
                asyncio.run_coroutine_threadsafe(self.on_error(error, song), self._loop)
        else:
            logger.debug(f"Playback finished normally: {song.display_name}")

        self._reset_state()

        # Notify callback
        if self.on_song_finished and self._loop:
            asyncio.run_coroutine_threadsafe(self.on_song_finished(song), self._loop)

    def _reset_state(self):
        """Reset playback state"""
        self.current_song = None
        self.is_playing = False
        self.is_paused = False
