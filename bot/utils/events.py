"""Event bus, message updates, and state management"""

import asyncio
import discord
from typing import Callable, Dict, List, Optional
from ..pkg.logger import logger


class SongUpdateEvent:
    """Event fired when song metadata is updated"""
    def __init__(self, song_id: str, guild_id: int):
        self.song_id = song_id
        self.guild_id = guild_id


class EventBus:
    """Event bus for song updates - pub/sub pattern"""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = asyncio.Lock()
    
    async def subscribe(self, event_type: str, handler: Callable):
        async with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)
            logger.debug(f"Subscribed handler to event: {event_type}")
    
    async def unsubscribe(self, event_type: str, handler: Callable):
        async with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(handler)
                    logger.debug(f"Unsubscribed handler from event: {event_type}")
                except ValueError:
                    pass
    
    async def publish(self, event_type: str, event: SongUpdateEvent):
        handlers = []
        async with self._lock:
            handlers = self._subscribers.get(event_type, []).copy()
        
        if handlers:
            logger.debug(f"Publishing event {event_type} to {len(handlers)} handlers")
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}")
    
    def has_subscribers(self, event_type: str) -> bool:
        return event_type in self._subscribers and len(self._subscribers[event_type]) > 0


event_bus = EventBus()
song_event_bus = event_bus  # Alias for backward compatibility


class MessageUpdateManager:
    """Real-time Discord message updates when song metadata changes"""
    
    def __init__(self):
        self._tracked_messages: Dict[str, list] = {}
        self._lock = asyncio.Lock()
        self._subscribed = False
    
    async def initialize(self):
        if not self._subscribed:
            await event_bus.subscribe("song_metadata_updated", self._handle_song_update)
            self._subscribed = True
            logger.info("✅ MessageUpdateManager subscribed to song events")
    
    async def track_message(self, message: discord.Message, song_id: str, guild_id: int, message_type: str = "queue_add"):
        async with self._lock:
            if song_id not in self._tracked_messages:
                self._tracked_messages[song_id] = []
            
            self._tracked_messages[song_id].append({"message": message, "guild_id": guild_id, "type": message_type})
            logger.debug(f"Tracking message {message.id} for song {song_id} (type: {message_type})")
    
    async def _handle_song_update(self, event: SongUpdateEvent):
        try:
            song_id = event.song_id
            guild_id = event.guild_id
            
            async with self._lock:
                if song_id not in self._tracked_messages:
                    return
                
                messages = self._tracked_messages[song_id]
                logger.info(f"📝 Song {song_id} updated, refreshing {len(messages)} messages")
                
                for msg_info in messages:
                    if msg_info["guild_id"] == guild_id:
                        await self._update_message(msg_info, song_id)
                
                del self._tracked_messages[song_id]
        
        except Exception as e:
            logger.error(f"Error handling song update event: {e}")
    
    async def _update_message(self, msg_info: dict, song_id: str):
        try:
            message = msg_info["message"]
            message_type = msg_info["type"]
            
            from ..services.playback import playback_service
            
            guild_id = msg_info["guild_id"]
            audio_service = playback_service.audio_service
            queue_manager = audio_service.get_queue_manager(guild_id)
            
            if not queue_manager:
                return
            
            song = None
            for s in queue_manager.get_all_songs():
                if s.id == song_id:
                    song = s
                    break
            
            if not song or not song.metadata:
                logger.debug(f"Song {song_id} not found or no metadata yet")
                return
            
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
    
    async def _update_queue_add_message(self, message: discord.Message, song, queue_manager):
        try:
            all_songs = queue_manager.get_all_songs()
            position = None
            for i, s in enumerate(all_songs, 1):
                if s.id == song.id:
                    position = i
                    break
            
            if position is None:
                return
            
            title = song.metadata.display_name
            status_emoji = "✅"
            content = f"{status_emoji} **Đã thêm vào hàng đợi:**\n**{title}**\n`Vị trí: {position}/{len(all_songs)}`"
            
            await message.edit(content=content)
            logger.debug(f"✅ Updated queue add message with title: {title}")
        
        except Exception as e:
            logger.error(f"Error updating queue add message: {e}")
    
    async def _update_now_playing_message(self, message: discord.Message, song):
        try:
            if not message.embeds:
                return
            
            embed = message.embeds[0]
            embed.title = f"🎵 Đang phát: {song.metadata.display_name}"
            embed.description = f"⏱️ {song.metadata.duration_formatted}"
            
            if song.metadata.thumbnail_url:
                embed.set_thumbnail(url=song.metadata.thumbnail_url)
            
            await message.edit(embed=embed)
            logger.debug(f"✅ Updated now playing message")
        
        except Exception as e:
            logger.error(f"Error updating now playing message: {e}")
    
    async def _update_processing_message(self, message: discord.Message, song):
        try:
            title = song.metadata.display_name
            content = f"✅ **Xử lý hoàn tất:**\n**{title}**"
            
            await message.edit(content=content)
            logger.debug(f"✅ Updated processing message")
        
        except Exception as e:
            logger.error(f"Error updating processing message: {e}")
    
    async def cleanup_old_tracked_messages(self, max_age_seconds: int = 600):
        pass
    
    async def shutdown(self):
        if self._subscribed:
            await event_bus.unsubscribe("song_metadata_updated", self._handle_song_update)
            self._subscribed = False
            logger.info("MessageUpdateManager unsubscribed from events")


message_update_manager = MessageUpdateManager()
