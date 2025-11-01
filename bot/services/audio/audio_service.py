"""
Audio Service - Simplified for 24/7 bot without ResourceManager
Handles voice connections, audio players, and tracklist management
"""

import asyncio
import discord
from typing import Dict, Optional, Union
from ...pkg.logger import logger
from ...config.constants import VOICE_CONNECTION_TIMEOUT, FFMPEG_CLEANUP_DELAY

from ..stream_refresh import StreamRefreshService

from ...domain.entities.tracklist import Tracklist
from .audio_player import AudioPlayer
from ...config.performance import performance_config


class AudioService:
    """Simplified Audio Service without ResourceManager"""

    def __init__(self, stream_refresh_service: StreamRefreshService):
        self.config = performance_config

        # Core dictionaries for managing audio resources
        self._voice_clients: Dict[int, discord.VoiceClient] = {}
        self._audio_players: Dict[int, AudioPlayer] = {}

        self._tracklists: Dict[int, Tracklist] = {}
        self._stream_refresh_service = stream_refresh_service

        # Thread-safe lock for voice operations
        self._voice_lock = asyncio.Lock()

        logger.info("🎵 AudioService initialized (24/7 mode - no auto-disconnect)")

    async def connect_to_channel(self, channel: Union[discord.VoiceChannel, discord.StageChannel]) -> bool:
        """Connect to voice channel - simplified without ResourceManager"""
        guild_id = channel.guild.id

        async with self._voice_lock:
            try:
                # Check if already in the same channel
                if guild_id in self._voice_clients:
                    current_channel = self._voice_clients[guild_id].channel
                    if current_channel.id == channel.id:
                        logger.info(f"✅ Already connected to {channel.name}")
                        return True

                    # Move to new channel
                    logger.info(f"🔄 Moving from {current_channel.name} to {channel.name}")
                    await self.disconnect_from_guild(guild_id)

                # Connect to channel
                logger.info(f"🔊 Connecting to voice channel: {channel.name}")
                voice_client = await asyncio.wait_for(
                    channel.connect(timeout=VOICE_CONNECTION_TIMEOUT, reconnect=True),
                    timeout=VOICE_CONNECTION_TIMEOUT
                )

                # Save connection
                self._voice_clients[guild_id] = voice_client
                logger.debug(f"✅ Voice client saved for guild {guild_id}")

                # Initialize audio infrastructure
                await self._initialize_audio_player(guild_id, voice_client)

                logger.info(f"✅ Successfully connected to {channel.name} in {channel.guild.name}")
                return True

            except asyncio.TimeoutError:
                logger.error(f"⏱️ Connection timeout for channel {channel.name}")
                return False
            except discord.ClientException as e:
                logger.error(f"❌ Discord client error: {e}")
                return False
            except Exception as e:
                logger.error(f"❌ Failed to connect to voice channel: {e}")
                return False

    async def disconnect_from_guild(self, guild_id: int) -> bool:
        """Disconnect from voice channel and cleanup resources"""
        async with self._voice_lock:
            try:
                # Stop audio player
                if guild_id in self._audio_players:
                    audio_player = self._audio_players[guild_id]
                    audio_player.mark_disconnected()  # Prevent auto-play

                    if audio_player.is_playing:
                        audio_player.stop()
                        logger.debug(f"🛑 Stopped audio player for guild {guild_id}")
                        await asyncio.sleep(FFMPEG_CLEANUP_DELAY)  # Wait for FFmpeg cleanup

                    del self._audio_players[guild_id]

                # Clear tracklist
                if guild_id in self._tracklists:
                    tracklist_size = self._tracklists[guild_id].queue_size
                    await self._tracklists[guild_id].clear()
                    del self._tracklists[guild_id]
                    logger.debug(f"🗑️ Cleared tracklist ({tracklist_size} songs) for guild {guild_id}")

                # Disconnect voice client
                if guild_id in self._voice_clients:
                    voice_client = self._voice_clients[guild_id]
                    if voice_client.is_connected():
                        await voice_client.disconnect(force=True)
                        logger.debug(f"📡 Disconnected voice client for guild {guild_id}")
                    del self._voice_clients[guild_id]

                logger.info(f"👋 Successfully disconnected from guild {guild_id}")
                return True

            except Exception as e:
                logger.error(f"❌ Error disconnecting from guild {guild_id}: {e}")
                return False

    async def ensure_voice_connection(self, guild_id: int, channel_id: int) -> Optional[discord.VoiceClient]:
        """Ensure bot is connected to voice channel, reconnect if needed"""
        async with self._voice_lock:
            try:
                voice_client = self._voice_clients.get(guild_id)

                # Already connected to correct channel
                if voice_client and voice_client.is_connected():
                    if voice_client.channel.id == channel_id:
                        return voice_client

                    # Wrong channel, disconnect first
                    logger.info(f"🔄 Reconnecting to different channel in guild {guild_id}")
                    await self.disconnect_from_guild(guild_id)

                # Get channel and connect
                channel = self._get_channel_by_id(guild_id, channel_id)
                if not channel:
                    logger.error(f"❌ Channel {channel_id} not found in guild {guild_id}")
                    return None

                # Reconnect
                success = await self.connect_to_channel(channel)
                if success:
                    return self._voice_clients.get(guild_id)

                return None

            except Exception as e:
                logger.error(f"❌ Error ensuring voice connection: {e}")
                return None

    def _get_channel_by_id(self, guild_id: int, channel_id: int) -> Optional[Union[discord.VoiceChannel, discord.StageChannel]]:
        """Helper to get channel by ID"""
        voice_client = self._voice_clients.get(guild_id)
        if voice_client and voice_client.guild:
            return voice_client.guild.get_channel(channel_id)
        return None

    # ============================================================================
    # Audio Player Management
    # ============================================================================

    async def _initialize_audio_player(self, guild_id: int, voice_client: discord.VoiceClient) -> bool:
        """Initialize audio player and tracklist manager for guild"""
        try:
            # Create tracklist manager if not exists
            if guild_id not in self._tracklists:
                self._tracklists[guild_id] = Tracklist(guild_id)

            self._audio_players[guild_id] = AudioPlayer(
                stream_refresh_service=self._stream_refresh_service,
                voice_client=voice_client,
                guild_id=guild_id,
                tracklist=self._tracklists[guild_id],
                loop=asyncio.get_event_loop(),
            )

            logger.debug(f"✅ Initialized audio player for guild {guild_id}")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize audio player for guild {guild_id}: {e}")
            return False

    def get_audio_player(self, guild_id: int) -> Optional[AudioPlayer]:
        """Get audio player for guild"""
        return self._audio_players.get(guild_id)

    def get_tracklist(self, guild_id: int) -> Optional[Tracklist]:
        """Get or create tracklist manager for guild"""
        if guild_id not in self._tracklists:
            self._tracklists[guild_id] = Tracklist(guild_id)
            logger.debug(f"📋 Created new tracklist manager for guild {guild_id}")
        return self._tracklists[guild_id]

    def get_voice_client(self, guild_id: int) -> Optional[discord.VoiceClient]:
        """Get voice client for guild"""
        return self._voice_clients.get(guild_id)

    # ============================================================================
    # Playback Control
    # ============================================================================

    async def play_next_song(self, guild_id: int) -> bool:
        """Start playing next song in tracklist"""
        try:
            audio_player = self._audio_players.get(guild_id)
            if not audio_player:
                logger.warning(f"⚠️ No audio player found for guild {guild_id}")
                return False

            if not self._tracklists[guild_id] or self._tracklists[guild_id].queue_size == 0:
                logger.info(f"📭 Tracklist is empty for guild {guild_id}")
                return False

            # Get next song (this advances the position in tracklist)
            next_song = await self._tracklists[guild_id].next_song()
            if not next_song:
                logger.info(f"📭 No more songs in tracklist for guild {guild_id}")
                return False

            # Start playback
            await audio_player.play_song(next_song)
            logger.info(f"▶️ Started playing: {next_song.metadata.title} in guild {guild_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error playing next song in guild {guild_id}: {e}")
            return False

    async def skip_current_song(self, guild_id: int) -> bool:
        """Skip current song"""
        try:
            audio_player = self._audio_players.get(guild_id)
            if not audio_player:
                logger.warning(f"⚠️ No audio player for guild {guild_id}")
                return False

            if not audio_player.is_playing:
                logger.warning(f"⚠️ Nothing is playing in guild {guild_id}")
                return False

            # Stop with auto_play_next=False to prevent callback from playing next
            audio_player.stop(auto_play_next=False)
            logger.info(f"⏭️ Skipped song in guild {guild_id}")

            # Wait for FFmpeg to fully terminate
            await asyncio.sleep(FFMPEG_CLEANUP_DELAY)

            # Manually play next song (callback won't do it)
            await self.play_next_song(guild_id)
            return True

        except Exception as e:
            logger.error(f"❌ Error skipping song in guild {guild_id}: {e}")
            return False

    def pause_playback(self, guild_id: int) -> bool:
        """Pause current playback"""
        audio_player = self._audio_players.get(guild_id)
        if audio_player and audio_player.is_playing:
            audio_player.pause()
            logger.info(f"⏸️ Paused playback in guild {guild_id}")
            return True
        return False

    def resume_playback(self, guild_id: int) -> bool:
        """Resume paused playback"""
        audio_player = self._audio_players.get(guild_id)
        if audio_player and audio_player.is_paused:
            audio_player.resume()
            logger.info(f"▶️ Resumed playback in guild {guild_id}")
            return True
        return False

    async def stop_playback(self, guild_id: int) -> bool:
        """Stop playback and clear tracklist"""
        try:
            # Stop audio player
            audio_player = self._audio_players.get(guild_id)
            if audio_player and audio_player.is_playing:
                audio_player.stop()
                logger.debug(f"🛑 Stopped playback in guild {guild_id}")

            # Clear tracklist
            if self._tracklists[guild_id]:
                await self._tracklists[guild_id].clear()
                logger.debug(f"🗑️ Cleared tracklist in guild {guild_id}")

            logger.info(f"⏹️ Stopped playback and cleared tracklist in guild {guild_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error stopping playback in guild {guild_id}: {e}")
            return False

    def is_playing(self, guild_id: int) -> bool:
        """Check if audio is playing in guild"""
        audio_player = self._audio_players.get(guild_id)
        return audio_player.is_playing if audio_player else False

    # ============================================================================
    # Statistics & Cleanup
    # ============================================================================

    def get_resource_stats(self) -> dict:
        """Get simple resource statistics"""
        active_players = sum(1 for player in self._audio_players.values() if player.is_playing)

        return {
            "voice_connections": len(self._voice_clients),
            "audio_players": len(self._audio_players),
            "active_players": active_players,
            "tracklist_managers": len(self._tracklists),
            "total_queued_songs": sum(qm.queue_size for qm in self._tracklists.values()),
        }

    async def cleanup_all(self):
        """Cleanup all connections on bot shutdown"""
        logger.info("🧹 AudioService: Cleaning up all resources...")

        guild_ids = list(self._voice_clients.keys())
        for guild_id in guild_ids:
            try:
                await self.disconnect_from_guild(guild_id)
            except Exception as e:
                logger.error(f"❌ Error cleaning up guild {guild_id}: {e}")

        logger.info("✅ AudioService cleanup complete")

    async def force_cleanup_idle_connections(self) -> int:
        """
        Force cleanup voice connections considered idle.
        Disconnect guilds where there's no active playback and the tracklist is empty.
        Returns number of disconnected guilds.
        """
        disconnected = 0
        # snapshot keys to avoid runtime dict changes
        guild_ids = list(self._voice_clients.keys())

        for guild_id in guild_ids:
            try:
                audio_player = self._audio_players.get(guild_id)

                is_playing = bool(audio_player and getattr(audio_player, "is_playing", False))
                tracklist_empty = True
                if self._tracklists[guild_id]:
                    # queue_size is a sync property
                    tracklist_empty = self._tracklists[guild_id].queue_size == 0

                # If not playing and tracklist empty -> consider idle
                if not is_playing and tracklist_empty:
                    logger.info(f"🧹 force_cleanup_idle: disconnecting idle guild {guild_id}")
                    success = await self.disconnect_from_guild(guild_id)
                    if success:
                        disconnected += 1

            except Exception as e:
                logger.error(f"❌ Failed to cleanup idle guild {guild_id}: {e}")

        logger.debug(f"🧹 force_cleanup_idle completed: disconnected={disconnected}")
        return disconnected
