"""
Message Update Manager for real-time Discord message updates
Subscribes to song events and updates relevant Discord messages
"""

import discord
from typing import Dict, Optional
import asyncio

from ..utils.song_events import song_event_bus, SongUpdateEvent
from ..pkg.logger import logger


class MessageUpdateManager:
    """
    Manages Discord message updates when song metadata changes
    Tracks messages that need updating and subscribes to song events
    """

    def __init__(self):
        # Store messages to update: {song_id: [(message, guild_id, message_type)]}
        self._tracked_messages: Dict[str, list] = {}
        self._lock = asyncio.Lock()
        self._subscribed = False

    async def initialize(self):
        """Initialize and subscribe to events"""
        if not self._subscribed:
            await song_event_bus.subscribe(
                "song_metadata_updated", self._handle_song_update
            )
            self._subscribed = True
            logger.info("✅ MessageUpdateManager subscribed to song events")

    async def track_message(
        self,
        message: discord.Message,
        song_id: str,
        guild_id: int,
        message_type: str = "queue_add",
    ):
        """
        Track a message for updates when song metadata changes

        Args:
            message: Discord message to update
            song_id: Song ID to track
            guild_id: Guild ID
            message_type: Type of message (queue_add, now_playing, etc.)
        """
        async with self._lock:
            if song_id not in self._tracked_messages:
                self._tracked_messages[song_id] = []

            self._tracked_messages[song_id].append({
                "message": message,
                "guild_id": guild_id,
                "type": message_type,
            })

            logger.debug(
                f"Tracking message {message.id} for song {song_id} (type: {message_type})"
            )

    async def _handle_song_update(self, event: SongUpdateEvent):
        """Handle song metadata update event"""
        try:
            song_id = event.song_id
            guild_id = event.guild_id

            async with self._lock:
                if song_id not in self._tracked_messages:
                    return

                messages = self._tracked_messages[song_id]
                logger.info(
                    f"📝 Song {song_id} updated, refreshing {len(messages)} messages"
                )

                # Update all tracked messages for this song
                for msg_info in messages:
                    if msg_info["guild_id"] == guild_id:
                        await self._update_message(msg_info, song_id)

                # Clean up tracked messages after update
                del self._tracked_messages[song_id]

        except Exception as e:
            logger.error(f"Error handling song update event: {e}")

    async def _update_message(self, msg_info: dict, song_id: str):
        """Update a specific Discord message"""
        try:
            message = msg_info["message"]
            message_type = msg_info["type"]

            # Get updated song info
            from ..services.playback import playback_service

            guild_id = msg_info["guild_id"]
            audio_service = playback_service.audio_service
            queue_manager = audio_service.get_queue_manager(guild_id)

            if not queue_manager:
                return

            # Find the song by ID
            song = None
            for s in queue_manager.get_all_songs():
                if s.id == song_id:
                    song = s
                    break

            if not song or not song.metadata:
                logger.debug(f"Song {song_id} not found or no metadata yet")
                return

            # Update message based on type
            if message_type == "queue_add":
                await self._update_queue_add_message(message, song, queue_manager)
            elif message_type == "now_playing":
                await self._update_now_playing_message(message, song)
            elif message_type == "processing":
                await self._update_processing_message(message, song)

        except discord.NotFound:
            logger.debug(f"Message not found (deleted), skipping update")
        except discord.Forbidden:
            logger.warning(f"No permission to edit message")
        except Exception as e:
            logger.error(f"Error updating message: {e}")

    async def _update_queue_add_message(
        self, message: discord.Message, song, queue_manager
    ):
        """Update 'added to queue' message with full title"""
        try:
            # Find song position in queue
            all_songs = queue_manager.get_all_songs()
            position = None
            for i, s in enumerate(all_songs, 1):
                if s.id == song.id:
                    position = i
                    break

            if position is None:
                return

            # Create updated content
            title = song.metadata.display_name
            status_emoji = "✅"

            content = f"{status_emoji} **Đã thêm vào hàng đợi:**\n**{title}**\n`Vị trí: {position}/{len(all_songs)}`"

            # Try to edit the message
            await message.edit(content=content)
            logger.debug(f"✅ Updated queue add message with title: {title}")

        except Exception as e:
            logger.error(f"Error updating queue add message: {e}")

    async def _update_now_playing_message(self, message: discord.Message, song):
        """Update 'now playing' embed with full metadata"""
        try:
            if not message.embeds:
                return

            embed = message.embeds[0]

            # Update title
            embed.title = f"🎵 Đang phát: {song.metadata.display_name}"

            # Update description with duration
            embed.description = f"⏱️ {song.metadata.duration_formatted}"

            # Update thumbnail if available
            if song.metadata.thumbnail_url:
                embed.set_thumbnail(url=song.metadata.thumbnail_url)

            await message.edit(embed=embed)
            logger.debug(f"✅ Updated now playing message")

        except Exception as e:
            logger.error(f"Error updating now playing message: {e}")

    async def _update_processing_message(self, message: discord.Message, song):
        """Update 'processing' message to show completion"""
        try:
            title = song.metadata.display_name
            content = f"✅ **Xử lý hoàn tất:**\n**{title}**"

            await message.edit(content=content)
            logger.debug(f"✅ Updated processing message")

        except Exception as e:
            logger.error(f"Error updating processing message: {e}")

    async def cleanup_old_tracked_messages(self, max_age_seconds: int = 600):
        """Cleanup old tracked messages (older than 10 minutes by default)"""
        # This would need timestamp tracking, keeping it simple for now
        pass

    async def shutdown(self):
        """Shutdown and unsubscribe"""
        if self._subscribed:
            await song_event_bus.unsubscribe(
                "song_metadata_updated", self._handle_song_update
            )
            self._subscribed = False
            logger.info("MessageUpdateManager unsubscribed from events")


# Global instance
message_update_manager = MessageUpdateManager()
