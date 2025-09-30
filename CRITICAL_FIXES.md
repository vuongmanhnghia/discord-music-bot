# 🚨 CRITICAL FIXES - Cần Khắc Phục Ngay

## 1. Duplicate Method trong AudioService

**File:** `bot/services/audio_service.py`

Có 2 method `cleanup_all()` với implementation khác nhau. Python chỉ giữ method cuối, gây mất logic.

### Fix:

Xóa method duplicate và merge logic:

```python
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
```

---

## 2. Race Condition trong QueueManager

**File:** `bot/domain/entities/queue.py`

Methods không thread-safe, có thể bị race condition trong concurrent access.

### Fix:

Thêm asyncio locks:

```python
import asyncio

class QueueManager:
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self._songs: List[Song] = []
        self._current_index: int = 0
        self._history: List[Song] = []
        self._shuffle_enabled: bool = False
        self._repeat_mode: str = "queue"
        self._lock = asyncio.Lock()  # ADD THIS
    
    async def add_song(self, song: Song) -> int:
        """Add song to queue with thread-safety"""
        async with self._lock:
            self._songs.append(song)
            return len(self._songs)
    
    async def next_song(self) -> Optional[Song]:
        """Move to next song with thread-safety"""
        async with self._lock:
            if self._repeat_mode == "track":
                return self.current_song
            
            if self.current_song and self._current_index < len(self._songs):
                self._history.append(self.current_song)
                if len(self._history) > 50:
                    self._history = self._history[-50:]
            
            self._current_index += 1
            
            if self._current_index >= len(self._songs):
                if self._repeat_mode == "queue" and len(self._songs) > 0:
                    self._current_index = 0
                    return self.current_song
                else:
                    self._current_index = max(0, len(self._songs) - 1) if self._songs else 0
                    return None
            
            return self.current_song
    
    async def remove_at(self, index: int) -> bool:
        """Remove song at index with thread-safety"""
        async with self._lock:
            if 0 <= index < len(self._songs):
                self._songs.pop(index)
                if self._current_index >= len(self._songs) and self._songs:
                    self._current_index = len(self._songs) - 1
                return True
            return False
```

**IMPORTANT:** Cũng cần update tất cả nơi gọi methods này từ sync sang async:

```python
# BEFORE:
position = queue_manager.add_song(song)

# AFTER:
position = await queue_manager.add_song(song)
```

---

## 3. Memory Leak trong SmartCache

**File:** `bot/utils/smart_cache.py`

`_popular_urls` dict không bao giờ được clean up → memory leak.

### Fix:

```python
class SmartCache:
    def __init__(self, ...):
        # ... existing code ...
        self._popular_urls: Dict[str, Tuple[int, float]] = {}  # (count, last_access)
        
        # Start periodic cleanup
        asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """Periodic cleanup of stale data"""
        while True:
            try:
                await asyncio.sleep(3600)  # Every hour
                
                async with self._cache_lock:
                    # Clean expired cache entries
                    expired_count = 0
                    current_time = time.time()
                    
                    keys_to_remove = []
                    for key, cached_song in self._cache.items():
                        if cached_song.is_expired(self.ttl):
                            keys_to_remove.append(key)
                    
                    for key in keys_to_remove:
                        await self._remove_from_cache(key)
                        expired_count += 1
                    
                    # Clean stale popular URLs (not accessed in 24h)
                    stale_urls = []
                    for url, (count, last_access) in self._popular_urls.items():
                        if current_time - last_access > 86400:  # 24 hours
                            stale_urls.append(url)
                    
                    for url in stale_urls:
                        del self._popular_urls[url]
                    
                    logger.info(
                        f"🧹 Periodic cleanup: {expired_count} cache entries, "
                        f"{len(stale_urls)} stale URLs"
                    )
            except Exception as e:
                logger.error(f"Periodic cleanup error: {e}")
    
    async def cache_song(self, url: str, song_data: dict) -> bool:
        """Cache a processed song"""
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
            
            # Track popularity with timestamp
            current_time = time.time()
            if url in self._popular_urls:
                count, _ = self._popular_urls[url]
                self._popular_urls[url] = (count + 1, current_time)
            else:
                self._popular_urls[url] = (1, current_time)
            
            await self._enforce_size_limit()
            
            if self.persist:
                await self._save_to_persistent(key, cached_song)
            
            logger.debug(f"Cached song: {cached_song.title}")
            return True
            
        except Exception as e:
            logger.error(f"Error caching song {url}: {e}")
            return False
```

---

## 4. Error Handling trong PlaylistRepository

**File:** `bot/domain/repositories/playlist_repository.py`

Dùng `print()` thay vì logger, và silent fail.

### Fix:

```python
import shutil
from pathlib import Path
from ..pkg.logger import logger

class PlaylistRepository:
    def save(self, playlist: Playlist) -> bool:
        """Save playlist to file with atomic write"""
        try:
            file_path = self._get_file_path(playlist.name)
            
            # Create backup before overwriting
            if file_path.exists():
                backup_path = file_path.with_suffix('.json.backup')
                try:
                    shutil.copy2(file_path, backup_path)
                except Exception as e:
                    logger.warning(f"Could not create backup: {e}")
            
            # Atomic write using temp file
            temp_path = file_path.with_suffix('.json.tmp')
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(playlist.to_dict(), f, indent=2, ensure_ascii=False)
            
            # Rename for atomicity
            temp_path.replace(file_path)
            
            logger.info(f"✅ Saved playlist: {playlist.name}")
            return True
            
        except PermissionError as e:
            logger.error(f"❌ Permission denied saving playlist {playlist.name}: {e}")
            return False
        except OSError as e:
            logger.error(f"❌ Disk error saving playlist {playlist.name}: {e}")
            return False
        except Exception as e:
            logger.exception(f"❌ Unexpected error saving playlist {playlist.name}")
            return False
    
    def load(self, playlist_name: str) -> Optional[Playlist]:
        """Load playlist from file"""
        try:
            file_path = self._get_file_path(playlist_name)
            if not file_path.exists():
                logger.debug(f"Playlist file not found: {playlist_name}")
                return None
            
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            logger.info(f"✅ Loaded playlist: {playlist_name}")
            return Playlist.from_dict(data)
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in playlist {playlist_name}: {e}")
            return None
        except OSError as e:
            logger.error(f"❌ Error reading playlist {playlist_name}: {e}")
            return None
        except Exception as e:
            logger.exception(f"❌ Unexpected error loading playlist {playlist_name}")
            return None
    
    def delete(self, playlist_name: str) -> bool:
        """Delete playlist file"""
        try:
            file_path = self._get_file_path(playlist_name)
            if not file_path.exists():
                logger.warning(f"Playlist file not found: {playlist_name}")
                return False
            
            # Move to trash instead of permanent delete
            trash_path = file_path.with_suffix('.json.deleted')
            file_path.rename(trash_path)
            
            logger.info(f"🗑️ Deleted playlist: {playlist_name}")
            return True
            
        except OSError as e:
            logger.error(f"❌ Error deleting playlist {playlist_name}: {e}")
            return False
        except Exception as e:
            logger.exception(f"❌ Unexpected error deleting playlist {playlist_name}")
            return False
    
    def list_all(self) -> List[str]:
        """List all available playlists"""
        try:
            playlist_names = []
            for file_path in self.base_path.glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    playlist_names.append(data["name"])
                except Exception as e:
                    logger.warning(f"Could not read playlist {file_path}: {e}")
                    continue
            
            return sorted(playlist_names)
            
        except Exception as e:
            logger.error(f"❌ Error listing playlists: {e}")
            return []
```

---

## 5. BOT_TOKEN Security

**File:** `bot/config/config.py`

Token có thể leak qua logs.

### Fix:

```python
class Config:
    """Centralized configuration with validation"""
    
    def __init__(self):
        self.BOT_TOKEN: str = os.getenv("BOT_TOKEN") or ""
        self.BOT_NAME: str = os.getenv("BOT_NAME", "Discord Music Bot")
        self.COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "!")
        self.PLAYLIST_DIR: str = os.getenv("PLAYLIST_DIR", "./playlist")
        self.STAY_CONNECTED_24_7: bool = os.getenv("STAY_CONNECTED_24_7", "true").lower() in [
            "true", "1", "yes"
        ]
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FILE: str = os.getenv("LOG_FILE", "")
        
        # Validate and mask token
        self._validate_and_mask_token()
        
        # Validate other config
        self._validate_config()
    
    def _validate_and_mask_token(self):
        """Validate token and create masked version for logging"""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is required")
        
        if len(self.BOT_TOKEN) < 50:
            raise ValueError("Invalid BOT_TOKEN format (too short)")
        
        # Create masked version for safe logging
        self._masked_token = f"{self.BOT_TOKEN[:10]}...{self.BOT_TOKEN[-4:]}"
    
    def _validate_config(self):
        """Validate configuration"""
        # Ensure directories exist
        Path(self.PLAYLIST_DIR).mkdir(parents=True, exist_ok=True)
        
        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.LOG_LEVEL.upper() not in valid_levels:
            raise ValueError(f"Invalid LOG_LEVEL. Must be one of {valid_levels}")
    
    def get_safe_token_display(self) -> str:
        """Return masked token for logging"""
        return self._masked_token
    
    @property
    def playlist_path(self) -> Path:
        return Path(self.PLAYLIST_DIR)

# Global config instance
try:
    config = Config()
    logger.info(f"✅ Config loaded successfully (Token: {config.get_safe_token_display()})")
except Exception as e:
    logger.error(f"❌ Failed to load config: {e}")
    raise
```

---

## Priority Order

1. **Fix duplicate cleanup_all()** - Ngay lập tức
2. **Add locks to QueueManager** - Ngay lập tức (nhưng cần test kỹ)
3. **Fix PlaylistRepository error handling** - Ngay lập tức
4. **Add BOT_TOKEN masking** - Ngay lập tức
5. **Fix SmartCache memory leak** - Trong ngày hôm nay

## Testing Plan

Sau khi fix, cần test:

```bash
# 1. Test cleanup
pytest tests/test_audio_service.py::test_cleanup_all -v

# 2. Test concurrent queue access
pytest tests/test_queue_manager.py::test_concurrent_access -v

# 3. Test playlist operations
pytest tests/test_playlist_repository.py -v

# 4. Test cache cleanup
pytest tests/test_smart_cache.py::test_periodic_cleanup -v
```

## Rollout Strategy

1. Create feature branch: `git checkout -b fix/critical-issues`
2. Apply fixes one by one
3. Test each fix
4. Commit with descriptive messages
5. Deploy to staging first
6. Monitor for 24h
7. Deploy to production

## Monitoring Post-Fix

Sau khi deploy, monitor:

- Memory usage (should stabilize)
- Error logs (should decrease)
- Queue operation timing
- Cache hit rates
