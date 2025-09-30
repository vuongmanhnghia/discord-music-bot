"""
SmartCache: Intelligent caching system for processed songs
Provides instant responses for cached content and intelligent cache warming
"""

import asyncio
import hashlib
import json
import os
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import pickle

from ..pkg.logger import logger


@dataclass
class CachedSong:
    """Represents a cached song with metadata"""

    url: str
    title: str
    duration: int
    thumbnail: str
    source_type: str
    file_path: Optional[str] = None
    cached_at: float = 0.0
    access_count: int = 0
    last_accessed: float = 0.0

    def __post_init__(self):
        if self.cached_at == 0.0:
            self.cached_at = time.time()
        if self.last_accessed == 0.0:
            self.last_accessed = time.time()

    def update_access(self):
        """Update access tracking"""
        self.access_count += 1
        self.last_accessed = time.time()

    def is_expired(self, ttl: int) -> bool:
        """Check if cache entry is expired"""
        return (time.time() - self.cached_at) > ttl

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CachedSong":
        """Create from dictionary"""
        return cls(**data)


class SmartCache:
    """
    Intelligent caching system for music bot
    Features:
    - LRU eviction with access tracking
    - TTL-based expiration
    - Intelligent cache warming
    - Persistent cache across restarts
    - Performance analytics
    """

    def __init__(
        self,
        cache_dir: str = "cache",
        max_size: int = 1000,
        ttl: int = 7200,  # 2 hours default
        persist: bool = True,
    ):

        self.cache_dir = Path(cache_dir)
        self.max_size = max_size
        self.ttl = ttl
        self.persist = persist

        # In-memory cache
        self._cache: Dict[str, CachedSong] = {}
        self._access_order: List[str] = []  # LRU tracking

        # Thread-safe lock for cache operations
        self._cache_lock = asyncio.Lock()

        # Performance tracking
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "cache_saves": 0,
            "cache_loads": 0,
            "processing_time_saved": 0.0,
        }

        # Popular content tracking
        self._popular_urls: Dict[str, int] = {}  # url -> access count
        self._warming_queue: List[str] = []
        self._max_popular_urls = 500  # Limit popular URLs tracking

        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 600  # Cleanup every 10 minutes

        # Ensure cache directory exists (create parents if needed)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load persistent cache if enabled
        if self.persist:
            self._load_persistent_cache()

        # Note: Background cleanup task will be started lazily on first use
        # (cannot create task here as event loop may not be running yet)

        logger.info(f"🚄 SmartCache initialized: {len(self._cache)} cached items")

    def _url_to_key(self, url: str) -> str:
        """Convert URL to cache key"""
        return hashlib.md5(url.encode()).hexdigest()

    async def get_cached_song(self, url: str) -> Optional[CachedSong]:
        """Get song from cache with LRU update"""
        # Ensure cleanup task is running (lazy start)
        self._ensure_cleanup_task()
        
        key = self._url_to_key(url)

        async with self._cache_lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                logger.debug(f"Cache miss: {url}")
                return None

            cached_song = self._cache[key]

            # Check TTL expiration
            if cached_song.is_expired(self.ttl):
                logger.debug(f"Cache expired: {url}")
                await self._remove_from_cache(key)
                self._stats["misses"] += 1
                return None

            # Update LRU and access tracking
            self._update_lru(key)
            cached_song.update_access()

            self._stats["hits"] += 1
            logger.debug(f"Cache hit: {cached_song.title}")

            return cached_song

    async def cache_song(self, url: str, song_data: dict) -> bool:
        """Cache a processed song"""
        # Ensure cleanup task is running (lazy start)
        self._ensure_cleanup_task()
        
        try:
            key = self._url_to_key(url)

            # Create cached song object
            cached_song = CachedSong(
                url=url,
                title=song_data.get("title", "Unknown"),
                duration=song_data.get("duration", 0),
                thumbnail=song_data.get("thumbnail", ""),
                source_type=song_data.get("source_type", "UNKNOWN"),
                file_path=song_data.get("file_path"),
            )

            # Add to cache
            self._cache[key] = cached_song
            self._update_lru(key)

            # Track popularity
            self._popular_urls[url] = self._popular_urls.get(url, 0) + 1

            # Enforce popular URLs limit
            self._enforce_popular_urls_limit()

            # Enforce size limit
            await self._enforce_size_limit()

            # Save to persistent storage if enabled
            if self.persist:
                await self._save_to_persistent(key, cached_song)

            logger.debug(f"Cached song: {cached_song.title}")
            return True

        except Exception as e:
            logger.error(f"Error caching song {url}: {e}")
            return False

    def _update_lru(self, key: str):
        """Update LRU order for a key"""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def _enforce_popular_urls_limit(self):
        """Enforce popular URLs tracking limit to prevent unbounded growth"""
        if len(self._popular_urls) > self._max_popular_urls:
            # Keep only top 80% by access count
            sorted_urls = sorted(
                self._popular_urls.items(), key=lambda x: x[1], reverse=True
            )
            cutoff = int(self._max_popular_urls * 0.8)
            self._popular_urls = dict(sorted_urls[:cutoff])
            logger.debug(
                f"Pruned popular URLs tracking from {len(sorted_urls)} to {len(self._popular_urls)}"
            )

    async def _enforce_size_limit(self):
        """Enforce cache size limit using LRU eviction"""
        while len(self._cache) > self.max_size:
            if not self._access_order:
                break

            # Remove least recently used
            lru_key = self._access_order.pop(0)
            await self._remove_from_cache(lru_key)
            self._stats["evictions"] += 1

    async def _remove_from_cache(self, key: str):
        """Remove item from cache and cleanup"""
        if key in self._cache:
            cached_song = self._cache[key]

            # Cleanup file if exists
            if cached_song.file_path and os.path.exists(cached_song.file_path):
                try:
                    os.remove(cached_song.file_path)
                except Exception as e:
                    logger.warning(
                        f"Failed to remove cached file {cached_song.file_path}: {e}"
                    )

            del self._cache[key]

        if key in self._access_order:
            self._access_order.remove(key)

    def _ensure_cleanup_task(self):
        """Ensure background cleanup task is running (lazy start)"""
        try:
            # Only start if we have a running event loop and task isn't already running
            if self._cleanup_task is None or self._cleanup_task.done():
                loop = asyncio.get_running_loop()
                self._cleanup_task = loop.create_task(self._background_cleanup())
                logger.info(
                    f"🧹 Started background cleanup task (interval: {self._cleanup_interval}s)"
                )
        except RuntimeError:
            # No event loop running yet, will try again later
            pass

    async def _background_cleanup(self):
        """Background task to periodically cleanup expired entries"""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                logger.debug("Running periodic cache cleanup...")

                # Cleanup expired entries
                expired_count = await self.cleanup_expired()

                # Log statistics
                stats = self.get_stats()
                logger.info(
                    f"🧹 Cache cleanup: removed {expired_count} expired entries, "
                    f"current size: {stats['cache_size']}/{stats['max_size']}, "
                    f"hit rate: {stats['hit_rate']:.1f}%"
                )

            except asyncio.CancelledError:
                logger.info("Background cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in background cleanup task: {e}")
                # Continue running despite errors

    async def get_or_process(self, url: str, process_func) -> Tuple[dict, bool]:
        """
        Get cached song or process if not cached
        Returns: (song_data, was_cached)
        """
        start_time = time.time()

        # Try cache first
        cached_song = await self.get_cached_song(url)
        if cached_song:
            processing_time_saved = time.time() - start_time
            self._stats["processing_time_saved"] += processing_time_saved

            return {
                "title": cached_song.title,
                "duration": cached_song.duration,
                "thumbnail": cached_song.thumbnail,
                "source_type": cached_song.source_type,
                "file_path": cached_song.file_path,
                "url": cached_song.url,
            }, True

        # Process if not cached
        try:
            song_data = await process_func(url)

            # Cache the result
            if song_data:
                await self.cache_song(url, song_data)

            return song_data, False

        except Exception as e:
            logger.error(f"Error processing song {url}: {e}")
            raise

    async def warm_cache(self, urls: List[str], process_func) -> int:
        """Warm cache with popular URLs"""
        warmed_count = 0

        for url in urls[:10]:  # Limit to top 10
            try:
                cached_song = await self.get_cached_song(url)
                if not cached_song:  # Only process if not already cached
                    song_data = await process_func(url)
                    if song_data:
                        await self.cache_song(url, song_data)
                        warmed_count += 1
                        logger.debug(f"Cache warmed: {song_data.get('title', url)}")
            except Exception as e:
                logger.warning(f"Failed to warm cache for {url}: {e}")

        return warmed_count

    def get_popular_urls(self, limit: int = 20) -> List[Tuple[str, int]]:
        """Get most popular URLs by access count"""
        return sorted(self._popular_urls.items(), key=lambda x: x[1], reverse=True)[
            :limit
        ]

    async def cleanup_expired(self) -> int:
        """Remove expired cache entries"""
        expired_keys = []

        async with self._cache_lock:
            for key, cached_song in self._cache.items():
                if cached_song.is_expired(self.ttl):
                    expired_keys.append(key)

        # Remove expired entries
        for key in expired_keys:
            async with self._cache_lock:
                await self._remove_from_cache(key)

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

        return len(expired_keys)

    def get_stats(self) -> dict:
        """Get cache performance statistics"""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / max(total_requests, 1)) * 100

        return {
            **self._stats,
            "total_requests": total_requests,
            "hit_rate": hit_rate,
            "cache_size": len(self._cache),
            "max_size": self.max_size,
            "popular_count": len(self._popular_urls),
        }

    # Persistent Cache Management

    def _get_persistent_path(self, key: str) -> Path:
        """Get path for persistent cache file"""
        return self.cache_dir / f"{key}.cache"

    def _get_index_path(self) -> Path:
        """Get path for cache index file"""
        return self.cache_dir / "cache_index.json"

    async def _save_to_persistent(self, key: str, cached_song: CachedSong):
        """Save cache entry to persistent storage"""
        try:
            cache_file = self._get_persistent_path(key)
            with open(cache_file, "wb") as f:
                pickle.dump(cached_song.to_dict(), f)
            self._stats["cache_saves"] += 1
        except Exception as e:
            logger.warning(f"Failed to save cache to disk: {e}")

    def _load_persistent_cache(self):
        """Load cache from persistent storage"""
        try:
            # Load cache index if it exists
            index_path = self._get_index_path()
            if index_path.exists():
                with open(index_path, "r") as f:
                    index_data = json.load(f)
                    self._popular_urls = index_data.get("popular_urls", {})

            # Load individual cache files
            loaded_count = 0
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    with open(cache_file, "rb") as f:
                        song_data = pickle.load(f)
                        cached_song = CachedSong.from_dict(song_data)

                        # Skip expired entries
                        if not cached_song.is_expired(self.ttl):
                            key = cache_file.stem
                            self._cache[key] = cached_song
                            self._access_order.append(key)
                            loaded_count += 1
                        else:
                            # Remove expired file
                            cache_file.unlink()

                except Exception as e:
                    logger.warning(f"Failed to load cache file {cache_file}: {e}")
                    # Remove corrupted cache file
                    cache_file.unlink()

            self._stats["cache_loads"] += loaded_count
            logger.info(f"Loaded {loaded_count} cached songs from disk")

        except Exception as e:
            logger.error(f"Error loading persistent cache: {e}")

    async def save_cache_index(self):
        """Save cache index and statistics"""
        try:
            index_data = {
                "popular_urls": self._popular_urls,
                "stats": self._stats,
                "saved_at": time.time(),
            }

            index_path = self._get_index_path()
            with open(index_path, "w") as f:
                json.dump(index_data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save cache index: {e}")

    async def clear_cache(self) -> int:
        """Clear all cached data"""
        cleared_count = len(self._cache)

        # Clear in-memory cache
        for key in list(self._cache.keys()):
            await self._remove_from_cache(key)

        # Clear persistent cache files
        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()

            index_path = self._get_index_path()
            if index_path.exists():
                index_path.unlink()
        except Exception as e:
            logger.error(f"Error clearing persistent cache: {e}")

        # Reset stats and popular tracking
        self._popular_urls.clear()

        logger.info(f"Cleared {cleared_count} cache entries")
        return cleared_count

    async def shutdown(self):
        """Clean shutdown of cache system"""
        logger.info("🛑 SmartCache shutting down...")

        # Cancel background cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("✅ Background cleanup task stopped")

        # Save current state
        if self.persist:
            await self.save_cache_index()

        # Cleanup expired entries
        await self.cleanup_expired()

        logger.info("✅ SmartCache shutdown complete")
