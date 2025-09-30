"""
Event-driven architecture for Discord Music Bot
Decouples components and makes system more maintainable
"""

from dataclasses import dataclass
from typing import Callable, List, Any, Dict, Optional
from enum import Enum
import asyncio

from ..pkg.logger import logger


class EventType(Enum):
    """All possible events in the system"""
    
    # Song events
    SONG_ADDED = "song_added"
    SONG_PROCESSING = "song_processing"
    SONG_PROCESSED = "song_processed"
    SONG_FAILED = "song_failed"
    SONG_STARTED = "song_started"
    SONG_FINISHED = "song_finished"
    
    # Queue events
    QUEUE_EMPTY = "queue_empty"
    QUEUE_CLEARED = "queue_cleared"
    QUEUE_SHUFFLED = "queue_shuffled"
    
    # Playback events
    PLAYBACK_STARTED = "playback_started"
    PLAYBACK_PAUSED = "playback_paused"
    PLAYBACK_RESUMED = "playback_resumed"
    PLAYBACK_STOPPED = "playback_stopped"
    PLAYBACK_ERROR = "playback_error"
    
    # Connection events
    VOICE_CONNECTED = "voice_connected"
    VOICE_DISCONNECTED = "voice_disconnected"
    VOICE_ERROR = "voice_error"
    
    # Playlist events
    PLAYLIST_LOADED = "playlist_loaded"
    PLAYLIST_SAVED = "playlist_saved"


@dataclass
class Event:
    """
    Event data structure
    
    Attributes:
        type: Type of event
        guild_id: Guild where event occurred
        data: Event-specific data
        timestamp: When event was created
    """
    type: EventType
    guild_id: int
    data: Any
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            import time
            self.timestamp = time.time()


class EventBus:
    """
    Central event bus for pub/sub pattern
    
    Benefits:
    - Decouples components
    - Easy to add new features
    - Better testing
    - Clear event flow
    
    Example:
        >>> event_bus = EventBus()
        >>> event_bus.subscribe(EventType.SONG_FINISHED, on_song_finished)
        >>> await event_bus.publish(Event(
        ...     type=EventType.SONG_FINISHED,
        ...     guild_id=123,
        ...     data=song
        ... ))
    """
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history_size = 100
        
        # For debugging
        self._event_counts: Dict[EventType, int] = {}
    
    def subscribe(self, event_type: EventType, handler: Callable) -> None:
        """
        Subscribe to an event type
        
        Args:
            event_type: Type of event to listen for
            handler: Async function to handle event
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)
            logger.debug(f"Subscribed handler to {event_type.value}")
    
    def unsubscribe(self, event_type: EventType, handler: Callable) -> None:
        """
        Unsubscribe from an event type
        
        Args:
            event_type: Type of event
            handler: Handler to remove
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
                logger.debug(f"Unsubscribed handler from {event_type.value}")
            except ValueError:
                pass
    
    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers
        
        Args:
            event: Event to publish
        """
        # Track event
        self._event_counts[event.type] = self._event_counts.get(event.type, 0) + 1
        
        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history_size:
            self._event_history.pop(0)
        
        # Get handlers
        handlers = self._subscribers.get(event.type, [])
        
        if not handlers:
            logger.debug(f"No handlers for event: {event.type.value}")
            return
        
        logger.debug(
            f"Publishing event: {event.type.value} to {len(handlers)} handlers "
            f"(guild: {event.guild_id})"
        )
        
        # Call all handlers concurrently
        tasks = []
        for handler in handlers:
            try:
                # Create task for each handler
                task = asyncio.create_task(
                    self._safe_handler_call(handler, event)
                )
                tasks.append(task)
            except Exception as e:
                logger.error(f"Error creating handler task: {e}")
        
        # Wait for all handlers to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _safe_handler_call(self, handler: Callable, event: Event) -> None:
        """
        Safely call handler with error handling
        
        Args:
            handler: Handler function
            event: Event to pass to handler
        """
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                f"Error in event handler for {event.type.value}: {e}",
                exc_info=True
            )
    
    def get_event_history(self, 
                         event_type: Optional[EventType] = None,
                         guild_id: Optional[int] = None,
                         limit: int = 10) -> List[Event]:
        """
        Get recent event history
        
        Args:
            event_type: Filter by event type
            guild_id: Filter by guild
            limit: Maximum events to return
            
        Returns:
            List of recent events
        """
        events = self._event_history
        
        if event_type:
            events = [e for e in events if e.type == event_type]
        
        if guild_id:
            events = [e for e in events if e.guild_id == guild_id]
        
        return events[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get event bus statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_event_types": len(self._subscribers),
            "total_handlers": sum(len(h) for h in self._subscribers.values()),
            "event_counts": {
                event_type.value: count 
                for event_type, count in self._event_counts.items()
            },
            "history_size": len(self._event_history)
        }


# Global event bus instance
event_bus = EventBus()


# Example handlers:

async def on_song_finished_handler(event: Event):
    """Handle song finished event"""
    from ..services.audio_service import audio_service
    
    song = event.data
    guild_id = event.guild_id
    
    logger.info(f"Song finished: {song.display_name} in guild {guild_id}")
    
    # Auto-play next song
    await audio_service.skip_to_next(guild_id)


async def on_playback_error_handler(event: Event):
    """Handle playback error event"""
    error_data = event.data
    guild_id = event.guild_id
    
    logger.error(f"Playback error in guild {guild_id}: {error_data}")
    
    # Could implement retry logic here
    # Could notify users via Discord
    # Could trigger auto-recovery


async def on_queue_empty_handler(event: Event):
    """Handle empty queue event"""
    guild_id = event.guild_id
    
    logger.info(f"Queue empty in guild {guild_id}")
    
    # Could auto-load playlist
    # Could disconnect after timeout
    # Could notify users


# Setup function to register all handlers
def setup_event_handlers():
    """Register all event handlers"""
    event_bus.subscribe(EventType.SONG_FINISHED, on_song_finished_handler)
    event_bus.subscribe(EventType.PLAYBACK_ERROR, on_playback_error_handler)
    event_bus.subscribe(EventType.QUEUE_EMPTY, on_queue_empty_handler)
    
    logger.info("✅ Event handlers registered")


# Example usage in services:
"""
# In AudioPlayer when song finishes:
await event_bus.publish(Event(
    type=EventType.SONG_FINISHED,
    guild_id=self.guild_id,
    data=song
))

# In AudioService when error occurs:
await event_bus.publish(Event(
    type=EventType.PLAYBACK_ERROR,
    guild_id=guild_id,
    data={"error": error, "song": song}
))

# In QueueManager when queue is empty:
await event_bus.publish(Event(
    type=EventType.QUEUE_EMPTY,
    guild_id=self.guild_id,
    data=None
))
"""
