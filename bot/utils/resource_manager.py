"""
ResourceManager: Manages bot resources to prevent memory leaks
Handles automatic cleanup of idle connections, caching, and resource limits
"""

import asyncio
import time
from typing import Dict, Any, Optional, Callable
from collections import OrderedDict
import weakref
import logging

from ..pkg.logger import logger


class LRUCache:
    """LRU (Least Recently Used) Cache with TTL support"""

    def __init__(self, max_size: int = 100, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl  # Time to live in seconds
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: Dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache, updating access order"""
        if key not in self._cache:
            return None

        # Check TTL
        if time.time() - self._timestamps[key] > self.ttl:
            self._remove(key)
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return self._cache[key]

    def set(self, key: str, value: Any) -> None:
        """Add/update item in cache"""
        current_time = time.time()

        if key in self._cache:
            # Update existing item
            self._cache[key] = value
            self._timestamps[key] = current_time
            self._cache.move_to_end(key)
        else:
            # Add new item
            if len(self._cache) >= self.max_size:
                # Remove least recently used item
                oldest_key = next(iter(self._cache))
                self._remove(oldest_key)

            self._cache[key] = value
            self._timestamps[key] = current_time

    def _remove(self, key: str) -> None:
        """Remove item from cache"""
        if key in self._cache:
            del self._cache[key]
            del self._timestamps[key]

    def clear_expired(self) -> int:
        """Remove all expired items, return count removed"""
        current_time = time.time()
        expired_keys = [
            key
            for key, timestamp in self._timestamps.items()
            if current_time - timestamp > self.ttl
        ]

        for key in expired_keys:
            self._remove(key)

        return len(expired_keys)

    def size(self) -> int:
        """Get current cache size"""
        return len(self._cache)

    def clear(self) -> None:
        """Clear all cached items"""
        self._cache.clear()
        self._timestamps.clear()


class ResourceManager:
    """Centralized resource management for the Discord Music Bot"""

    def __init__(self, max_connections: int = 10, cleanup_interval: int = 300):
        # Configuration
        self.max_connections = max_connections
        self.cleanup_interval = cleanup_interval  # 5 minutes default

        # Resource tracking
        self._active_connections: Dict[int, Any] = {}  # guild_id -> connection
        self._connection_timestamps: Dict[int, float] = {}
        self._resource_cache = LRUCache(max_size=100, ttl=1800)  # 30 min cache

        # Cleanup tracking
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_running = False

        # Statistics
        self._stats = {
            "connections_created": 0,
            "connections_cleaned": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "memory_cleanups": 0,
        }

        logger.info("🧹 ResourceManager initialized")

    async def start_cleanup_task(self):
        """Start the automatic cleanup background task"""
        if self._cleanup_task and not self._cleanup_task.done():
            return  # Already running

        self._is_running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info(
            f"🔄 ResourceManager cleanup task started (interval: {self.cleanup_interval}s)"
        )

    async def stop_cleanup_task(self):
        """Stop the automatic cleanup task"""
        self._is_running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("⏹️ ResourceManager cleanup task stopped")

    async def _cleanup_loop(self):
        """Background cleanup loop"""
        while self._is_running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.perform_cleanup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ResourceManager cleanup loop: {e}")

    def register_connection(self, guild_id: int, connection: Any) -> None:
        """Register a new audio connection"""
        self._active_connections[guild_id] = connection
        self._connection_timestamps[guild_id] = time.time()
        self._stats["connections_created"] += 1

        # Check connection limit
        if len(self._active_connections) > self.max_connections:
            self._cleanup_oldest_connection()

        logger.debug(
            f"📡 Registered connection for guild {guild_id} "
            f"({len(self._active_connections)}/{self.max_connections})"
        )

    def unregister_connection(self, guild_id: int) -> None:
        """Unregister an audio connection"""
        if guild_id in self._active_connections:
            del self._active_connections[guild_id]
            del self._connection_timestamps[guild_id]
            self._stats["connections_cleaned"] += 1
            logger.debug(f"📡 Unregistered connection for guild {guild_id}")

    def get_connection(self, guild_id: int) -> Optional[Any]:
        """Get active connection for guild"""
        return self._active_connections.get(guild_id)

    def _cleanup_oldest_connection(self):
        """Remove the oldest connection to stay under limit"""
        if not self._connection_timestamps:
            return

        oldest_guild = min(self._connection_timestamps.items(), key=lambda x: x[1])[0]
        connection = self._active_connections.get(oldest_guild)

        if connection:
            # Gracefully disconnect
            asyncio.create_task(self._disconnect_safely(oldest_guild, connection))
            logger.info(
                f"🧹 Cleaned up oldest connection (guild {oldest_guild}) to enforce limit"
            )

    async def _disconnect_safely(self, guild_id: int, connection: Any):
        """Safely disconnect an audio connection"""
        try:
            if hasattr(connection, "disconnect"):
                await connection.disconnect()
            elif hasattr(connection, "cleanup"):
                await connection.cleanup()
        except Exception as e:
            logger.warning(f"Error disconnecting guild {guild_id}: {e}")
        finally:
            self.unregister_connection(guild_id)

    # Cache Management
    def cache_get(self, key: str) -> Optional[Any]:
        """Get item from resource cache"""
        result = self._resource_cache.get(key)
        if result is not None:
            self._stats["cache_hits"] += 1
        else:
            self._stats["cache_misses"] += 1
        return result

    def cache_set(self, key: str, value: Any) -> None:
        """Set item in resource cache"""
        self._resource_cache.set(key, value)

    async def perform_cleanup(self) -> Dict[str, int]:
        """Perform comprehensive resource cleanup"""
        cleanup_stats = {
            "expired_cache_items": 0,
            "idle_connections": 0,
            "total_connections": len(self._active_connections),
        }

        # Clean expired cache items
        cleanup_stats["expired_cache_items"] = self._resource_cache.clear_expired()

        # Clean idle connections (older than 1 hour)
        current_time = time.time()
        idle_threshold = 3600  # 1 hour
        idle_guilds = []

        for guild_id, timestamp in self._connection_timestamps.items():
            if current_time - timestamp > idle_threshold:
                idle_guilds.append(guild_id)

        # Disconnect idle connections
        for guild_id in idle_guilds:
            connection = self._active_connections.get(guild_id)
            if connection:
                await self._disconnect_safely(guild_id, connection)
                cleanup_stats["idle_connections"] += 1

        self._stats["memory_cleanups"] += 1

        if (
            cleanup_stats["expired_cache_items"] > 0
            or cleanup_stats["idle_connections"] > 0
        ):
            logger.info(f"🧹 Cleanup completed: {cleanup_stats}")

        return cleanup_stats

    async def force_cleanup_guild(self, guild_id: int) -> bool:
        """Force cleanup resources for a specific guild"""
        connection = self._active_connections.get(guild_id)
        if connection:
            await self._disconnect_safely(guild_id, connection)
            logger.info(f"🧹 Force cleaned guild {guild_id}")
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get resource management statistics"""
        return {
            **self._stats,
            "active_connections": len(self._active_connections),
            "cache_size": self._resource_cache.size(),
            "cache_hit_rate": (
                self._stats["cache_hits"]
                / max(1, self._stats["cache_hits"] + self._stats["cache_misses"])
            )
            * 100,
        }

    async def shutdown(self):
        """Clean shutdown of ResourceManager"""
        logger.info("🛑 ResourceManager shutting down...")

        # Stop cleanup task
        await self.stop_cleanup_task()

        # Disconnect all connections
        guild_ids = list(self._active_connections.keys())
        for guild_id in guild_ids:
            connection = self._active_connections.get(guild_id)
            if connection:
                await self._disconnect_safely(guild_id, connection)

        # Clear caches
        self._resource_cache.clear()

        logger.info("✅ ResourceManager shutdown complete")
