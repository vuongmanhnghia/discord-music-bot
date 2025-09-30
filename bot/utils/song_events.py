"""
Song update events for real-time title updates in queue
Allows queue display to reflect updated metadata when processing completes
"""

from typing import Callable, Dict, List
import asyncio

from ..pkg.logger import logger


class SongUpdateEvent:
    """Event fired when a song's metadata is updated"""

    def __init__(self, song_id: str, guild_id: int):
        self.song_id = song_id
        self.guild_id = guild_id


class SongEventBus:
    """
    Event bus for song updates
    Allows components to subscribe to song metadata changes
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to an event type"""
        async with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)
            logger.debug(f"Subscribed handler to event: {event_type}")

    async def unsubscribe(self, event_type: str, handler: Callable):
        """Unsubscribe from an event type"""
        async with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(handler)
                    logger.debug(f"Unsubscribed handler from event: {event_type}")
                except ValueError:
                    pass

    async def publish(self, event_type: str, event: SongUpdateEvent):
        """Publish an event to all subscribers"""
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
        """Check if event type has any subscribers"""
        return event_type in self._subscribers and len(self._subscribers[event_type]) > 0


# Global event bus instance
song_event_bus = SongEventBus()
