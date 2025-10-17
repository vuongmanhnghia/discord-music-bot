import asyncio
from typing import Dict, Optional, Union
import discord

from ..domain.entities.song import Song
from ..domain.entities.queue import QueueManager
from ..utils.cache import ResourceManager
from ..config.performance import performance_config
from ..config.service_constants import ServiceConstants
from ..pkg.logger import logger
from .audio_player import AudioPlayer


class AudioService:
    """
    Main audio service managing all guild audio players
    Thread-safe with optimized resource management
    """

    def __init__(self):
        self.config = performance_config

        self._voice_clients: Dict[int, discord.VoiceClient] = {}
        self._audio_players: Dict[int, AudioPlayer] = {}
        self._queue_managers: Dict[int, QueueManager] = {}

        # Thread-safe lock (only voice operations need locking)
        self._voice_lock = asyncio.Lock()

        # Resource manager
        self.resource_manager = ResourceManager(
            max_connections=min(10, self.config.max_concurrent_processing * 3),
            cleanup_interval=self.config.cleanup_interval_seconds,
        )

    async def connect_to_channel(
        self, channel: Union[discord.VoiceChannel, discord.StageChannel]
    ) -> bool:
        """Connect to a voice channel with timeout"""
        guild_id = channel.guild.id

        async with self._voice_lock:
            try:
                # Disconnect if already connected
                if guild_id in self._voice_clients:
                    await self.disconnect_from_guild(guild_id)

                # Connect with timeout
                voice_client = await asyncio.wait_for(
                    channel.connect(), timeout=ServiceConstants.VOICE_CONNECT_TIMEOUT
                )
                self._voice_clients[guild_id] = voice_client

                # Register connection
                self.resource_manager.register_connection(guild_id, voice_client)

                # Initialize audio infrastructure
                await self._initialize_audio_player(guild_id, voice_client)

                return True

            except asyncio.TimeoutError:
                logger.error(f"Connection timeout for {channel.name}")
                return False
            except Exception as e:
                logger.error(f"Failed to connect to {channel.name}: {e}")
                return False

    async def initialize_guild(
        self, guild_id: int, voice_client: discord.VoiceClient
    ) -> bool:
        """Initialize audio infrastructure for a guild"""
        try:
            async with self._voice_lock:
                self._voice_clients[guild_id] = voice_client
                self.resource_manager.register_connection(guild_id, voice_client)
                await self._initialize_audio_player(guild_id, voice_client)
                return True
        except Exception as e:
            logger.error(f"Failed to initialize guild {guild_id}: {e}")
            return False

    async def _initialize_audio_player(
        self, guild_id: int, voice_client: discord.VoiceClient
    ) -> None:
        """Initialize audio player for a guild"""
        # Create audio player
        audio_player = AudioPlayer(voice_client, guild_id)
        audio_player.on_song_finished = self._on_song_finished
        audio_player.on_error = self._on_playback_error
        audio_player._set_event_loop(asyncio.get_running_loop())
        self._audio_players[guild_id] = audio_player

        # Create queue manager if not exists
        if guild_id not in self._queue_managers:
            self._queue_managers[guild_id] = QueueManager(guild_id)

    async def disconnect_from_guild(self, guild_id: int) -> bool:
        """Disconnect from voice channel in guild"""
        async with self._voice_lock:
            try:
                # Stop playback
                if guild_id in self._audio_players:
                    try:
                        self._audio_players[guild_id].stop()
                    except Exception as e:
                        logger.warning(f"Error stopping audio player: {e}")
                    finally:
                        del self._audio_players[guild_id]

                # Disconnect voice client
                if guild_id in self._voice_clients:
                    voice_client = self._voice_clients[guild_id]
                    try:
                        await asyncio.wait_for(
                            voice_client.disconnect(),
                            timeout=ServiceConstants.VOICE_DISCONNECT_TIMEOUT,
                        )
                    except asyncio.TimeoutError:
                        logger.warning(f"Disconnect timeout for guild {guild_id}")
                    except Exception as e:
                        logger.warning(f"Error during disconnect: {e}")
                    finally:
                        del self._voice_clients[guild_id]

                # Clean queue
                if guild_id in self._queue_managers:
                    await self._queue_managers[guild_id].clear()
                    del self._queue_managers[guild_id]

                # Unregister from resource manager
                self.resource_manager.unregister_connection(guild_id)

                return True
            except Exception as e:
                logger.error(f"Error disconnecting from guild {guild_id}: {e}")
                return False

    def get_audio_player(self, guild_id: int) -> Optional[AudioPlayer]:
        """Get audio player for guild"""
        return self._audio_players.get(guild_id)

    def get_queue_manager(self, guild_id: int) -> Optional[QueueManager]:
        """Get or create queue manager for guild"""
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

        if not audio_player:
            logger.error(f"No audio player found for guild {guild_id}")
            return False

        if not queue_manager:
            logger.error(f"No queue manager found for guild {guild_id}")
            return False

        current_song = queue_manager.current_song
        if not current_song:
            return False

        try:
            return await audio_player.play_song(current_song)
        except Exception as e:
            logger.error(f"Error in audio_player.play_song: {e}")
            return False

    async def skip_to_next(self, guild_id: int) -> bool:
        """Skip to next song"""
        queue_manager = self._queue_managers.get(guild_id)
        if not queue_manager:
            logger.error(f"No queue manager found for guild {guild_id}")
            return False

        # Move to next song first
        next_song = await queue_manager.next_song()
        if not next_song:
            return False

        # Stop current playback (will trigger _on_song_finished but queue already moved)
        audio_player = self._audio_players.get(guild_id)
        if audio_player:
            audio_player.stop()
            await asyncio.sleep(ServiceConstants.SKIP_PLAYBACK_DELAY)
        else:
            logger.warning(f"No audio player found for guild {guild_id}")

        # Play next song
        return await self.play_next_song(guild_id)

    async def _on_song_finished(self, song: Song) -> None:
        """Called when a song finishes playing"""
        guild_id = song.guild_id
        if not guild_id:
            return

        queue_manager = self._queue_managers.get(guild_id)
        if not queue_manager:
            return

        # Check if this song is still the current song
        # (if skip was called, current song would have changed already)
        current_song = queue_manager.current_song
        if current_song and current_song.original_input != song.original_input:
            logger.info(f"Song finished but queue already moved (skip was called)")
            return

        current_pos, total_songs = queue_manager.position

        # Check if there are more songs
        if current_pos < total_songs:
            await queue_manager.next_song()
            await self.play_next_song(guild_id)
        else:
            # Handle queue end based on repeat mode
            if queue_manager._repeat_mode == "queue" and total_songs > 0:
                await queue_manager.next_song()
                await self.play_next_song(guild_id)

    async def _on_playback_error(self, error: Exception, song: Song) -> None:
        """Called when playback error occurs"""
        guild_id = song.guild_id
        logger.error(f"Playback error in guild {guild_id}: {error}")

        # Try to play next song on error
        if guild_id:
            await self.skip_to_next(guild_id)

    async def start_resource_management(self):
        """Start ResourceManager background tasks"""
        await self.resource_manager.start_cleanup_task()

    async def cleanup_all(self):
        """Cleanup all resources and connections"""
        guild_ids = list(self._voice_clients.keys())

        # Disconnect all voice clients
        for guild_id in guild_ids:
            try:
                await self.disconnect_from_guild(guild_id)
            except Exception as e:
                logger.error(f"Error cleaning up guild {guild_id}: {e}")

        # Clear all managers
        self._queue_managers.clear()

        # Shutdown ResourceManager
        await self.resource_manager.shutdown()

    async def force_cleanup_idle_connections(self):
        """Force cleanup of idle connections"""
        return await self.resource_manager.perform_cleanup()

    def get_resource_stats(self) -> dict:
        """Get resource management statistics"""
        stats = self.resource_manager.get_stats()
        stats.update(
            {
                "total_voice_clients": len(self._voice_clients),
                "total_audio_players": len(self._audio_players),
                "total_queue_managers": len(self._queue_managers),
            }
        )
        return stats


# Global audio service instance
audio_service = AudioService()
