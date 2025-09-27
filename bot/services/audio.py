"""
Audio service for Discord playback
Clean integration with Discord.py voice system
"""
import platform
import os
import asyncio
import subprocess
from typing import Dict, Optional, Callable, Union
import discord
from discord import FFmpegPCMAudio, PCMVolumeTransformer

from ..domain.models import Song, QueueManager
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
        self.volume: float = 0.5
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
        """Play a song with retry mechanism"""
        if not song.is_ready:
            logger.error(f"Cannot play song that is not ready: {song.display_name}")
            return False

        logger.info(
            f"Starting playback: {song.display_name} in guild {self.guild_id} (attempt {retry_count + 1})"
        )

        try:
            # Validate stream URL
            if not song.stream_url or not song.stream_url.startswith(
                ("http://", "https://")
            ):
                logger.error(f"Invalid stream URL for song: {song.display_name}")
                return False

            logger.debug(f"Creating audio source for: {song.stream_url}")

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

            # Stop current playback if any
            if self.voice_client.is_playing() or self.voice_client.is_paused():
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
                    elif "voice" in str(error).lower() or "websocket" in str(error).lower():
                        logger.warning(f"Voice connection error detected: {error}")
                        # Trigger error callback for reconnection handling
                        if self.on_error:
                            try:
                                if self._loop:
                                    self._loop.create_task(self.on_error(error, song))
                            except Exception as e:
                                logger.error(f"Error in error callback: {e}")
                                
                self._on_playback_finished(error, song)

            self.voice_client.play(audio_source, after=after_callback)

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
            
            # Base configuration
            base_before_options = "-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 2"
            base_options = "-vn -avoid_negative_ts make_zero"
            
            # Platform-aware optimization
            if arch in ['aarch64', 'arm64', 'armv7l'] or memory_mb < 2048:
                # ARM/Low-memory optimization (Raspberry Pi)
                threads = min(1, cpu_count)
                buffer_size = "32k"
                max_rate = "96k"
                timeout = "20000000"
                logger.debug(f"🍓 ARM/Low-mem optimization: {threads} threads, {buffer_size} buffer")
            else:
                # x86_64/High-memory optimization
                threads = min(2, cpu_count)
                buffer_size = "64k"
                max_rate = "128k"
                timeout = "30000000"
                logger.debug(f"💻 x86_64/High-mem optimization: {threads} threads, {buffer_size} buffer")
            
            before_options = f"{base_before_options} -timeout {timeout}"
            options = f"{base_options} -bufsize {buffer_size} -maxrate {max_rate} -threads {threads}"

            logger.debug(
                f"Creating FFmpeg source with enhanced options: before_options='{before_options}', options='{options}'"
            )

            audio_source = FFmpegPCMAudio(stream_url, before_options=before_options, options=options)

            # Apply volume transformation
            if self.volume != 1.0:
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


class AudioService:
    """
    Main audio service managing all guild audio players
    Handles voice connections and playback coordination
    """

    def __init__(self):
        self._voice_clients: Dict[int, discord.VoiceClient] = {}
        self._audio_players: Dict[int, AudioPlayer] = {}
        self._queue_managers: Dict[int, QueueManager] = {}

    async def connect_to_channel(self, channel: Union[discord.VoiceChannel, discord.StageChannel]) -> bool:
        """Connect to a voice channel"""
        guild_id = channel.guild.id

        try:
            # Disconnect if already connected
            if guild_id in self._voice_clients:
                await self.disconnect_from_guild(guild_id)

            logger.info(f"Attempting to connect to voice channel: {channel.name}")

            # Connect to new channel
            voice_client = await channel.connect()
            
            self._voice_clients[guild_id] = voice_client

            # Create audio player
            audio_player = AudioPlayer(voice_client, guild_id)
            audio_player.on_song_finished = self._on_song_finished
            audio_player.on_error = self._on_playback_error

            # Set event loop for async callbacks
            audio_player._set_event_loop(asyncio.get_running_loop())
            self._audio_players[guild_id] = audio_player

            # Create queue manager if not exists
            if guild_id not in self._queue_managers:
                self._queue_managers[guild_id] = QueueManager(guild_id)

            logger.info(
                f"✅ Successfully connected to voice channel: {channel.name} in guild {guild_id}"
            )
            return True

        except asyncio.TimeoutError:
            logger.error(f"❌ Timeout connecting to voice channel {channel.name} (>35s)")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to connect to voice channel {channel.name}: {e}")
            return False

    async def disconnect_from_guild(self, guild_id: int) -> bool:
        """Disconnect from voice channel in guild"""
        try:
            # Stop playback
            if guild_id in self._audio_players:
                self._audio_players[guild_id].stop()
                del self._audio_players[guild_id]

            # Disconnect voice client
            if guild_id in self._voice_clients:
                voice_client = self._voice_clients[guild_id]
                await voice_client.disconnect()
                del self._voice_clients[guild_id]

            logger.info(f"Disconnected from voice in guild {guild_id}")
            return True

        except Exception as e:
            logger.error(f"Error disconnecting from guild {guild_id}: {e}")
            return False

    def get_audio_player(self, guild_id: int) -> Optional[AudioPlayer]:
        """Get audio player for guild"""
        return self._audio_players.get(guild_id)

    def get_queue_manager(self, guild_id: int) -> Optional[QueueManager]:
        """Get queue manager for guild"""
        if guild_id not in self._queue_managers:
            self._queue_managers[guild_id] = QueueManager(guild_id)
        return self._queue_managers[guild_id]

    def is_connected(self, guild_id: int) -> bool:
        """Check if connected to voice in guild"""
        voice_client = self._voice_clients.get(guild_id)
        return voice_client is not None and voice_client.is_connected()

    def is_playing(self, guild_id: int) -> bool:
        """Check if audio is playing in guild"""
        audio_player = self._audio_players.get(guild_id)
        return audio_player is not None and audio_player.is_playing

    async def play_next_song(self, guild_id: int) -> bool:
        """Play next song in queue"""
        audio_player = self._audio_players.get(guild_id)
        queue_manager = self._queue_managers.get(guild_id)

        if not audio_player or not queue_manager:
            logger.warning(f"No audio player or queue manager for guild {guild_id}")
            return False

        current_song = queue_manager.current_song
        if not current_song:
            logger.info(f"No more songs in queue for guild {guild_id}")
            return False

        if not current_song.is_ready:
            logger.warning(
                f"Current song not ready for playback: {current_song.display_name}"
            )
            return False

        return await audio_player.play_song(current_song)

    async def skip_to_next(self, guild_id: int) -> bool:
        """Skip to next song"""
        queue_manager = self._queue_managers.get(guild_id)
        if not queue_manager:
            return False

        # Move to next song
        next_song = queue_manager.next_song()
        if not next_song:
            logger.info(f"No next song in queue for guild {guild_id}")
            return False

        # Stop current playback (will trigger next song via callback)
        audio_player = self._audio_players.get(guild_id)
        if audio_player:
            audio_player.stop()

        return True

    async def _on_song_finished(self, song: Song):
        """Called when a song finishes playing"""
        guild_id = song.guild_id
        if not guild_id:
            return

        logger.info(f"Song finished: {song.display_name} in guild {guild_id}")

        # Auto-play next song
        queue_manager = self._queue_managers.get(guild_id)
        if not queue_manager:
            logger.warning(f"No queue manager found for guild {guild_id}")
            return

        # Get next song
        next_song = queue_manager.next_song()

        if next_song and next_song.is_ready:
            await self.play_next_song(guild_id)
        else:
            logger.info(f"No more songs to play in guild {guild_id}")

    async def _on_playback_error(self, error, song: Song):
        """Called when playback error occurs"""
        guild_id = song.guild_id
        logger.error(f"Playback error in guild {guild_id}: {error}")

        # Try to play next song on error
        if guild_id:
            await self.skip_to_next(guild_id)

    async def cleanup_all(self):
        """Cleanup all voice connections"""
        guild_ids = list(self._voice_clients.keys())
        for guild_id in guild_ids:
            await self.disconnect_from_guild(guild_id)

        logger.info("Cleaned up all voice connections")


# Global audio service instance
audio_service = AudioService()
