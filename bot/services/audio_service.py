import asyncio
from typing import Dict, Optional, Union
import discord

from ..domain.entities.song import Song
from ..domain.entities.queue import QueueManager
from ..utils.resource_manager import ResourceManager
from ..config.performance import performance_config

from ..pkg.logger import logger
from .audio_player import AudioPlayer


class AudioService:
    """
    Main audio service managing all guild audio players
    Handles voice connections and playback coordination
    """

    def __init__(self):
        # Load performance configuration
        self.config = performance_config

        self._voice_clients: Dict[int, discord.VoiceClient] = {}
        self._audio_players: Dict[int, AudioPlayer] = {}
        self._queue_managers: Dict[int, QueueManager] = {}

        # Thread-safe locks for concurrent access
        self._voice_lock = asyncio.Lock()
        self._player_lock = asyncio.Lock()
        self._queue_lock = asyncio.Lock()

        # Initialize ResourceManager with dynamic config
        self.resource_manager = ResourceManager(
            max_connections=min(10, self.config.max_concurrent_processing * 3),
            cleanup_interval=self.config.cleanup_interval_seconds,
        )

    async def connect_to_channel(
        self, channel: Union[discord.VoiceChannel, discord.StageChannel]
    ) -> bool:
        """Connect to a voice channel"""
        guild_id = channel.guild.id

        async with self._voice_lock:
            try:
                # Disconnect if already connected
                if guild_id in self._voice_clients:
                    await self.disconnect_from_guild(guild_id)

                logger.info(f"Attempting to connect to voice channel: {channel.name}")

                # Connect to new channel with timeout
                try:
                    voice_client = await asyncio.wait_for(
                        channel.connect(), timeout=30.0
                    )
                except asyncio.TimeoutError:
                    logger.error(f"❌ Connection timeout for {channel.name}")
                    return False

                self._voice_clients[guild_id] = voice_client

                # Register connection with ResourceManager
                self.resource_manager.register_connection(guild_id, voice_client)

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
                logger.error(
                    f"❌ Timeout connecting to voice channel {channel.name} (>35s)"
                )
                return False
            except Exception as e:
                logger.error(
                    f"❌ Failed to connect to voice channel {channel.name}: {e}"
                )
                return False

    async def initialize_guild(
        self, guild_id: int, voice_client: discord.VoiceClient
    ) -> bool:
        """Initialize audio infrastructure for a guild with existing voice client"""
        try:
            async with self._voice_lock:
                # Store voice client
                self._voice_clients[guild_id] = voice_client

                # Register connection with ResourceManager
                self.resource_manager.register_connection(guild_id, voice_client)

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

                logger.info(f"✅ Audio infrastructure initialized for guild {guild_id}")
                return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize guild {guild_id}: {e}")
            return False

    async def disconnect_from_guild(self, guild_id: int) -> bool:
        """Disconnect from voice channel in guild"""
        async with self._voice_lock:
            try:
                # Stop playback with error handling
                if guild_id in self._audio_players:
                    try:
                        self._audio_players[guild_id].stop()
                    except Exception as e:
                        logger.warning(f"Error stopping audio player: {e}")
                    finally:
                        del self._audio_players[guild_id]

                # Disconnect voice client with timeout
                if guild_id in self._voice_clients:
                    voice_client = self._voice_clients[guild_id]
                    try:
                        await asyncio.wait_for(voice_client.disconnect(), timeout=5.0)
                    except asyncio.TimeoutError:
                        logger.warning(f"Disconnect timeout for guild {guild_id}")
                    except Exception as e:
                        logger.warning(f"Error during disconnect: {e}")
                    finally:
                        del self._voice_clients[guild_id]

                # Clean up queue manager
                if guild_id in self._queue_managers:
                    self._queue_managers[guild_id].clear()
                    del self._queue_managers[guild_id]

                # Unregister from ResourceManager
                self.resource_manager.unregister_connection(guild_id)

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

    async def start_resource_management(self):
        """Start ResourceManager background tasks"""
        await self.resource_manager.start_cleanup_task()
        logger.info("🔄 AudioService resource management started")

    async def cleanup_all(self):
        """Cleanup all resources and connections"""
        logger.info("🧹 AudioService: Starting full cleanup...")

        # Get list of all active guild IDs
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

        logger.info("✅ AudioService cleanup complete")

    async def force_cleanup_idle_connections(self):
        """Force cleanup of idle connections"""
        cleanup_stats = await self.resource_manager.perform_cleanup()
        logger.info(f"🧹 Forced cleanup completed: {cleanup_stats}")
        return cleanup_stats

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

    async def cleanup_all(self):
        """Cleanup all voice connections"""
        guild_ids = list(self._voice_clients.keys())
        for guild_id in guild_ids:
            await self.disconnect_from_guild(guild_id)

        logger.info("Cleaned up all voice connections")


# Global audio service instance
audio_service = AudioService()
