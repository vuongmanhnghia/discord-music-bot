"""Cache and resource management utilities"""

import asyncio
import hashlib
import json
import os
import time
import pickle
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import OrderedDict
from ..pkg.logger import logger


@dataclass
class CachedSong:
    """Cached song with metadata and access tracking"""

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
        self.access_count += 1
        self.last_accessed = time.time()

    def is_expired(self, ttl: int) -> bool:
        return (time.time() - self.cached_at) > ttl

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CachedSong":
        return cls(**data)


class SmartCache:
    """Intelligent caching with LRU eviction, TTL expiration, and persistence"""

    def __init__(
        self,
        cache_dir: str = "cache",
        max_size: int = 1000,
        ttl: int = 7200,
        persist: bool = True,
    ):
        self.cache_dir = Path(cache_dir)
        self.max_size = max_size
        self.ttl = ttl
        self.persist = persist

        self._cache: Dict[str, CachedSong] = {}
        self._access_order: List[str] = []
        self._cache_lock = asyncio.Lock()

        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "cache_saves": 0,
            "cache_loads": 0,
            "processing_time_saved": 0.0,
        }

        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 600

        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if self.persist:
            self._load_persistent_cache()

        logger.info(f"🚄 SmartCache initialized: {len(self._cache)} cached items")

    def _url_to_key(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()

    async def get_cached_song(self, url: str) -> Optional[CachedSong]:
        self._ensure_cleanup_task()
        key = self._url_to_key(url)

        async with self._cache_lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                logger.debug(f"Cache miss: {url}")
                return None

            cached_song = self._cache[key]

            if cached_song.is_expired(self.ttl):
                logger.debug(f"Cache expired: {url}")
                await self._remove_from_cache(key)
                self._stats["misses"] += 1
                return None

            self._update_lru(key)
            cached_song.update_access()
            self._stats["hits"] += 1
            logger.debug(f"Cache hit: {cached_song.title}")

            return cached_song

    async def cache_song(self, url: str, song_data: dict) -> bool:
        self._ensure_cleanup_task()

        try:
            key = self._url_to_key(url)

            cached_song = CachedSong(
                url=url,
                title=song_data.get("title", "Unknown"),
                duration=song_data.get("duration", 0),
                thumbnail=song_data.get("thumbnail", ""),
                source_type=song_data.get("source_type", "UNKNOWN"),
                file_path=song_data.get("file_path"),
            )

            self._cache[key] = cached_song
            self._update_lru(key)

            await self._enforce_size_limit()

            if self.persist:
                await self._save_to_persistent(key, cached_song)

            logger.debug(f"Cached song: {cached_song.title}")
            return True

        except Exception as e:
            logger.error(f"Error caching song {url}: {e}")
            return False

    def _update_lru(self, key: str):
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    async def _enforce_size_limit(self):
        while len(self._cache) > self.max_size:
            if not self._access_order:
                break
            lru_key = self._access_order.pop(0)
            await self._remove_from_cache(lru_key)
            self._stats["evictions"] += 1

    async def _remove_from_cache(self, key: str):
        if key in self._cache:
            cached_song = self._cache[key]
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
        try:
            if self._cleanup_task is None or self._cleanup_task.done():
                loop = asyncio.get_running_loop()
                self._cleanup_task = loop.create_task(self._background_cleanup())
                logger.info(
                    f"🧹 Started background cleanup task (interval: {self._cleanup_interval}s)"
                )
        except RuntimeError:
            pass

    async def _background_cleanup(self):
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                logger.debug("Running periodic cache cleanup...")

                expired_count = await self.cleanup_expired()
                stats = self.get_stats()
                logger.info(
                    f"🧹 Cache cleanup: removed {expired_count} expired entries, current size: {stats['cache_size']}/{stats['max_size']}, hit rate: {stats['hit_rate']:.1f}%"
                )

            except asyncio.CancelledError:
                logger.info("Background cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in background cleanup task: {e}")

    async def get_or_process(self, url: str, process_func) -> Tuple[dict, bool]:
        start_time = time.time()

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

        try:
            song_data = await process_func(url)
            if song_data:
                await self.cache_song(url, song_data)
            return song_data, False
        except Exception as e:
            logger.error(f"Error processing song {url}: {e}")
            raise

    async def cleanup_expired(self) -> int:
        expired_keys = []

        async with self._cache_lock:
            for key, cached_song in self._cache.items():
                if cached_song.is_expired(self.ttl):
                    expired_keys.append(key)

        for key in expired_keys:
            async with self._cache_lock:
                await self._remove_from_cache(key)

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

        return len(expired_keys)

    def get_stats(self) -> dict:
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / max(total_requests, 1)) * 100

        return {
            **self._stats,
            "total_requests": total_requests,
            "hit_rate": hit_rate,
            "cache_size": len(self._cache),
            "max_size": self.max_size,
        }

    def _get_persistent_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.cache"

    def _get_index_path(self) -> Path:
        return self.cache_dir / "cache_index.json"

    async def _save_to_persistent(self, key: str, cached_song: CachedSong):
        try:
            cache_file = self._get_persistent_path(key)
            with open(cache_file, "wb") as f:
                pickle.dump(cached_song.to_dict(), f)
            self._stats["cache_saves"] += 1
        except Exception as e:
            logger.warning(f"Failed to save cache to disk: {e}")

    def _load_persistent_cache(self):
        try:
            index_path = self._get_index_path()
            if index_path.exists():
                with open(index_path, "r") as f:
                    index_data = json.load(f)
                    self._popular_urls = index_data.get("popular_urls", {})

            loaded_count = 0
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    with open(cache_file, "rb") as f:
                        song_data = pickle.load(f)
                        cached_song = CachedSong.from_dict(song_data)

                        if not cached_song.is_expired(self.ttl):
                            key = cache_file.stem
                            self._cache[key] = cached_song
                            self._access_order.append(key)
                            loaded_count += 1
                        else:
                            cache_file.unlink()

                except Exception as e:
                    logger.warning(f"Failed to load cache file {cache_file}: {e}")
                    cache_file.unlink()

            self._stats["cache_loads"] += loaded_count
            logger.info(f"Loaded {loaded_count} cached songs from disk")

        except Exception as e:
            logger.error(f"Error loading persistent cache: {e}")

    async def save_cache_index(self):
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
        cleared_count = len(self._cache)

        for key in list(self._cache.keys()):
            await self._remove_from_cache(key)

        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()

            index_path = self._get_index_path()
            if index_path.exists():
                index_path.unlink()
        except Exception as e:
            logger.error(f"Error clearing persistent cache: {e}")

        self._popular_urls.clear()
        logger.info(f"Cleared {cleared_count} cache entries")
        return cleared_count

    async def shutdown(self):
        logger.info("🛑 SmartCache shutting down...")

        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("✅ Background cleanup task stopped")

        if self.persist:
            await self.save_cache_index()

        await self.cleanup_expired()
        logger.info("✅ SmartCache shutdown complete")


class LRUCache:
    """LRU Cache with TTL support"""

    def __init__(self, max_size: int = 100, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: Dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            return None

        if time.time() - self._timestamps[key] > self.ttl:
            self._remove(key)
            return None

        self._cache.move_to_end(key)
        return self._cache[key]

    def set(self, key: str, value: Any) -> None:
        current_time = time.time()

        if key in self._cache:
            self._cache[key] = value
            self._timestamps[key] = current_time
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                self._remove(oldest_key)

            self._cache[key] = value
            self._timestamps[key] = current_time

    def _remove(self, key: str) -> None:
        if key in self._cache:
            del self._cache[key]
            del self._timestamps[key]

    def clear_expired(self) -> int:
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
        return len(self._cache)

    def clear(self) -> None:
        self._cache.clear()
        self._timestamps.clear()
