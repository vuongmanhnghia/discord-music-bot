# 🔍 Discord Music Bot - Phân Tích Source Code & Đề Xuất Cải Tiến

## 📊 Tổng Quan

Bot được xây dựng với kiến trúc clean architecture tốt, có phân tách domain/service/utils rõ ràng. Tuy nhiên, có nhiều vấn đề tiềm ẩn về performance, security, error handling và code quality cần được cải thiện.

---

## 🚨 Các Vấn Đề Quan Trọng Cần Khắc Phục Ngay

### 1. **CRITICAL: Duplicate Method `cleanup_all()` trong AudioService**
**File:** `bot/services/audio_service.py`  
**Dòng:** 338 và 368  

**Vấn đề:**
```python
async def cleanup_all(self):
    """Cleanup all resources and connections"""
    # ... implementation ...

async def cleanup_all(self):  # ❌ TRÙNG LẶP!
    """Cleanup all voice connections"""
    # ... different implementation ...
```

**Impact:** Python sẽ chỉ giữ method cuối cùng, gây mất logic cleanup resources.

**Khắc phục:**
```python
async def cleanup_all(self):
    """Cleanup all resources and connections"""
    logger.info("🧹 AudioService: Starting full cleanup...")
    
    guild_ids = list(self._voice_clients.keys())
    
    for guild_id in guild_ids:
        try:
            await self.disconnect_from_guild(guild_id)
        except Exception as e:
            logger.error(f"Error cleaning up guild {guild_id}: {e}")
    
    self._queue_managers.clear()
    await self.resource_manager.shutdown()
    
    logger.info("✅ AudioService cleanup complete")
```

---

### 2. **SECURITY: Hardcoded User Agent & Potential Credential Exposure**
**Files:** `bot/config/performance.py`, `bot/services/processing.py`

**Vấn đề:**
- User agent hardcoded có thể bị block
- Không có validation cho môi trường variables
- BOT_TOKEN có thể leak qua logs

**Khắc phục:**
```python
# bot/config/config.py
class Config:
    def __init__(self):
        self._validate_secrets()
    
    def _validate_secrets(self):
        """Validate sensitive configuration"""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required")
        
        if len(self.BOT_TOKEN) < 50:
            raise ValueError("Invalid BOT_TOKEN format")
        
        # Prevent token leakage in logs
        self._masked_token = f"{self.BOT_TOKEN[:10]}...{self.BOT_TOKEN[-4:]}"
    
    def get_safe_token(self) -> str:
        """Return masked token for logging"""
        return self._masked_token
```

---

### 3. **MEMORY LEAK: Unbounded Cache Growth**
**File:** `bot/utils/smart_cache.py`

**Vấn đề:**
- Cache không có TTL enforcement đúng cách
- `_popular_urls` dict không bao giờ được clean up
- Có thể dẫn đến memory leak trong long-running operation

**Khắc phục:**
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
                
                # Clean expired cache entries
                async with self._cache_lock:
                    expired_count = self._clean_expired_entries()
                    popular_cleaned = self._clean_stale_popular_urls()
                
                logger.info(f"🧹 Periodic cleanup: {expired_count} cache, {popular_cleaned} popular URLs")
            except Exception as e:
                logger.error(f"Periodic cleanup error: {e}")
    
    def _clean_stale_popular_urls(self, ttl: int = 86400) -> int:
        """Remove popular URLs not accessed in TTL seconds"""
        current_time = time.time()
        stale_urls = [
            url for url, (_, last_access) in self._popular_urls.items()
            if current_time - last_access > ttl
        ]
        
        for url in stale_urls:
            del self._popular_urls[url]
        
        return len(stale_urls)
```

---

### 4. **RACE CONDITION: Queue Management**
**File:** `bot/domain/entities/queue.py`

**Vấn đề:**
```python
def next_song(self) -> Optional[Song]:
    if self.current_song and self._current_index < len(self._songs):
        self._history.append(self.current_song)  # ❌ No lock!
        
    self._current_index += 1  # ❌ Race condition in concurrent access
```

**Impact:** Trong multi-guild environment, concurrent access có thể gây data corruption.

**Khắc phục:**
```python
import asyncio
from typing import Optional, List

class QueueManager:
    def __init__(self, guild_id: int):
        # ... existing code ...
        self._lock = asyncio.Lock()
    
    async def add_song(self, song: Song) -> int:
        """Add song with thread-safety"""
        async with self._lock:
            self._songs.append(song)
            return len(self._songs)
    
    async def next_song(self) -> Optional[Song]:
        """Move to next song with lock"""
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
```

---

### 5. **ERROR HANDLING: Swallowing Exceptions**
**File:** `bot/domain/repositories/playlist_repository.py`

**Vấn đề:**
```python
def save(self, playlist: Playlist) -> bool:
    try:
        # ... save logic ...
        return True
    except Exception as e:
        print(f"Error saving playlist {playlist.name}: {e}")  # ❌ Using print()!
        return False  # ❌ Silently failing!
```

**Khắc phục:**
```python
from ..pkg.logger import logger
from typing import Optional

class PlaylistRepository:
    def save(self, playlist: Playlist) -> bool:
        """Save playlist to file"""
        try:
            file_path = self._get_file_path(playlist.name)
            
            # Create backup before overwriting
            if file_path.exists():
                backup_path = file_path.with_suffix('.json.backup')
                shutil.copy2(file_path, backup_path)
            
            # Atomic write
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
            logger.exception(f"❌ Unexpected error saving playlist {playlist.name}: {e}")
            return False
```

---

## 🎯 Best Practices Cần Áp Dụng

### 6. **Dependency Injection thay vì Global Singletons**

**Vấn đề hiện tại:**
```python
# bot/services/audio_service.py
audio_service = AudioService()  # ❌ Global singleton

# bot/services/playback.py
playback_service = PlaybackService()  # ❌ Global singleton
```

**Tại sao xấu:**
- Khó test
- Tight coupling
- Không thể mock trong unit tests
- Khó scale với multiple instances

**Khắc phục:**
```python
# bot/core/container.py
from dataclasses import dataclass

@dataclass
class ServiceContainer:
    """Dependency injection container"""
    audio_service: AudioService
    playback_service: PlaybackService
    playlist_service: PlaylistService
    
    @classmethod
    def create(cls) -> 'ServiceContainer':
        """Factory method"""
        audio_service = AudioService()
        playback_service = PlaybackService()
        playlist_service = PlaylistService(LibraryManager())
        
        return cls(
            audio_service=audio_service,
            playback_service=playback_service,
            playlist_service=playlist_service
        )

# bot/music_bot.py
class MusicBot(commands.Bot):
    def __init__(self):
        super().__init__(...)
        self.services = ServiceContainer.create()
        self._setup_commands()
```

---

### 7. **Type Hints Consistency**

**Vấn đề:** Một số nơi có type hints, một số không.

**Khắc phục:**
```python
# Sử dụng mypy để enforce
# pyproject.toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true

# Ví dụ cải thiện
from typing import Optional, List, Dict, Any, Tuple
from discord import Guild, VoiceClient

async def connect_to_channel(
    self, 
    channel: Union[discord.VoiceChannel, discord.StageChannel]
) -> bool:
    """Connect to a voice channel with proper error handling"""
    ...
```

---

### 8. **Proper Async Context Managers**

**Vấn đề hiện tại:**
```python
# bot/utils/resource_manager.py
async def start_cleanup_task(self):
    self._cleanup_task = asyncio.create_task(self._cleanup_loop())

async def shutdown(self):
    if self._cleanup_task:
        self._cleanup_task.cancel()
```

**Khắc phục với Context Manager:**
```python
class ResourceManager:
    async def __aenter__(self):
        await self.start_cleanup_task()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.shutdown()
        return False

# Usage
async with ResourceManager() as resource_manager:
    # Bot operations
    ...
# Automatic cleanup
```

---

### 9. **Structured Logging**

**Vấn đề:** Logs không có structure, khó parse và analyze.

**Khắc phục:**
```python
# bot/pkg/logger.py
import json
import structlog

def setup_structured_logger():
    """Setup structured logging for better observability"""
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    return structlog.get_logger()

# Usage
logger.info("song_processed", 
    song_id=song.id,
    duration=song.metadata.duration,
    guild_id=guild_id,
    processing_time=elapsed_time
)
```

---

### 10. **Configuration Validation với Pydantic**

**Vấn đề:** Config validation thủ công, dễ sai.

**Khắc phục:**
```python
# bot/config/config.py
from pydantic import BaseSettings, Field, validator
from pathlib import Path

class BotConfig(BaseSettings):
    """Type-safe configuration with validation"""
    
    bot_token: str = Field(..., min_length=50, env="BOT_TOKEN")
    bot_name: str = Field(default="Discord Music Bot", env="BOT_NAME")
    command_prefix: str = Field(default="!", max_length=5, env="COMMAND_PREFIX")
    playlist_dir: Path = Field(default=Path("./playlist"), env="PLAYLIST_DIR")
    stay_connected_24_7: bool = Field(default=True, env="STAY_CONNECTED_24_7")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: Optional[Path] = Field(default=None, env="LOG_FILE")
    
    @validator("log_level")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of {valid_levels}")
        return v.upper()
    
    @validator("playlist_dir")
    def create_playlist_dir(cls, v):
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Usage
try:
    config = BotConfig()
except ValidationError as e:
    logger.error(f"Configuration validation failed: {e}")
    sys.exit(1)
```

---

## 🏗️ Architecture Improvements

### 11. **Implement Repository Pattern Properly**

**Hiện tại:** Repository pattern chưa đầy đủ.

**Đề xuất:**
```python
# bot/domain/repositories/base.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List

T = TypeVar('T')

class Repository(ABC, Generic[T]):
    """Base repository interface"""
    
    @abstractmethod
    async def get(self, id: str) -> Optional[T]:
        """Get entity by ID"""
        pass
    
    @abstractmethod
    async def save(self, entity: T) -> bool:
        """Save entity"""
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Delete entity"""
        pass
    
    @abstractmethod
    async def list_all(self) -> List[T]:
        """List all entities"""
        pass

# bot/domain/repositories/playlist_repository.py
class PlaylistRepository(Repository[Playlist]):
    """Async playlist repository"""
    
    async def get(self, playlist_name: str) -> Optional[Playlist]:
        """Load playlist asynchronously"""
        return await asyncio.to_thread(self._load_sync, playlist_name)
    
    def _load_sync(self, playlist_name: str) -> Optional[Playlist]:
        """Synchronous load operation"""
        try:
            file_path = self._get_file_path(playlist_name)
            if not file_path.exists():
                return None
            
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return Playlist.from_dict(data)
        except Exception as e:
            logger.error(f"Error loading playlist {playlist_name}: {e}")
            return None
```

---

### 12. **Event-Driven Architecture với Event Bus**

**Đề xuất:** Thay vì callbacks phức tạp, dùng event bus.

```python
# bot/core/events.py
from dataclasses import dataclass
from typing import Callable, List, Any
from enum import Enum

class EventType(Enum):
    SONG_FINISHED = "song_finished"
    SONG_FAILED = "song_failed"
    SONG_PROCESSED = "song_processed"
    QUEUE_EMPTY = "queue_empty"
    PLAYBACK_ERROR = "playback_error"

@dataclass
class Event:
    type: EventType
    data: Any
    guild_id: int

class EventBus:
    """Simple event bus for decoupling components"""
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """Subscribe to an event"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    async def publish(self, event: Event):
        """Publish an event to all subscribers"""
        handlers = self._subscribers.get(event.type, [])
        
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")

# Usage
event_bus = EventBus()

# Subscribe
event_bus.subscribe(EventType.SONG_FINISHED, on_song_finished_handler)

# Publish
await event_bus.publish(Event(
    type=EventType.SONG_FINISHED,
    data=song,
    guild_id=guild_id
))
```

---

## ⚡ Performance Optimizations

### 13. **Connection Pooling cho yt-dlp**

```python
# bot/services/ytdlp_pool.py
import asyncio
from typing import Dict, Any

class YTDLPPool:
    """Connection pool for yt-dlp operations"""
    
    def __init__(self, max_workers: int = 3):
        self._semaphore = asyncio.Semaphore(max_workers)
        self._active_tasks = {}
    
    async def extract_info(self, url: str, opts: Dict[str, Any]) -> Dict[str, Any]:
        """Extract info with connection pooling"""
        async with self._semaphore:
            # Create unique task ID
            task_id = hashlib.md5(url.encode()).hexdigest()
            
            # Check if already processing
            if task_id in self._active_tasks:
                return await self._active_tasks[task_id]
            
            # Create new task
            task = asyncio.create_task(self._extract_info_impl(url, opts))
            self._active_tasks[task_id] = task
            
            try:
                result = await task
                return result
            finally:
                del self._active_tasks[task_id]
    
    async def _extract_info_impl(self, url: str, opts: Dict[str, Any]) -> Dict[str, Any]:
        """Actual extraction implementation"""
        # ... implementation ...
```

---

### 14. **Batch Processing cho Playlists**

```python
# bot/services/batch_processor.py
from typing import List, Tuple
import asyncio

class BatchProcessor:
    """Process songs in batches for better performance"""
    
    async def process_batch(
        self, 
        urls: List[str], 
        batch_size: int = 5
    ) -> List[Tuple[bool, str, Optional[Song]]]:
        """Process multiple URLs in batches"""
        results = []
        
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            
            # Process batch concurrently
            tasks = [
                self._process_single(url) 
                for url in batch
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            results.extend(batch_results)
            
            # Rate limiting between batches
            if i + batch_size < len(urls):
                await asyncio.sleep(0.5)
        
        return results
```

---

## 🧪 Testing Improvements

### 15. **Unit Tests với Proper Mocking**

```python
# tests/test_audio_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from bot.services.audio_service import AudioService

@pytest.fixture
def audio_service():
    return AudioService()

@pytest.fixture
def mock_voice_client():
    client = AsyncMock()
    client.is_connected.return_value = True
    return client

@pytest.mark.asyncio
async def test_connect_to_channel_success(audio_service, mock_voice_client):
    """Test successful voice channel connection"""
    mock_channel = MagicMock()
    mock_channel.guild.id = 123456
    mock_channel.connect = AsyncMock(return_value=mock_voice_client)
    
    result = await audio_service.connect_to_channel(mock_channel)
    
    assert result is True
    assert 123456 in audio_service._voice_clients
    mock_channel.connect.assert_called_once()

@pytest.mark.asyncio
async def test_connect_to_channel_timeout(audio_service):
    """Test connection timeout handling"""
    mock_channel = MagicMock()
    mock_channel.guild.id = 123456
    
    async def timeout_connect():
        await asyncio.sleep(100)
    
    mock_channel.connect = timeout_connect
    
    result = await audio_service.connect_to_channel(mock_channel)
    
    assert result is False
```

---

## 📚 Documentation Improvements

### 16. **API Documentation với Sphinx**

```python
# bot/services/audio_service.py
class AudioService:
    """
    Audio service for managing voice connections and playback.
    
    This service handles all audio-related operations including:
    - Voice channel connections
    - Audio playback
    - Queue management
    - Resource cleanup
    
    Attributes:
        config (PerformanceConfig): Performance configuration
        resource_manager (ResourceManager): Resource management system
    
    Example:
        >>> audio_service = AudioService()
        >>> await audio_service.connect_to_channel(voice_channel)
        >>> await audio_service.play_next_song(guild_id)
    
    Thread Safety:
        All public methods are thread-safe and can be called from
        multiple concurrent contexts.
    
    Note:
        This is a singleton service. Use the global `audio_service` instance.
    """
    
    async def connect_to_channel(
        self, 
        channel: Union[discord.VoiceChannel, discord.StageChannel]
    ) -> bool:
        """
        Connect to a Discord voice channel.
        
        Args:
            channel: The voice channel to connect to
        
        Returns:
            True if connection successful, False otherwise
        
        Raises:
            asyncio.TimeoutError: If connection times out (>30s)
            discord.ClientException: If already connected
        
        Example:
            >>> success = await audio_service.connect_to_channel(voice_channel)
            >>> if success:
            ...     print("Connected!")
        """
        ...
```

---

## 🔒 Security Hardening

### 17. **Rate Limiting**

```python
# bot/utils/rate_limiter.py
import time
from collections import deque
from typing import Dict

class RateLimiter:
    """Rate limiter for API calls"""
    
    def __init__(self, max_calls: int, period: int):
        self.max_calls = max_calls
        self.period = period
        self._calls: Dict[str, deque] = {}
    
    def is_allowed(self, key: str) -> bool:
        """Check if call is allowed"""
        now = time.time()
        
        if key not in self._calls:
            self._calls[key] = deque()
        
        calls = self._calls[key]
        
        # Remove old calls
        while calls and calls[0] < now - self.period:
            calls.popleft()
        
        if len(calls) >= self.max_calls:
            return False
        
        calls.append(now)
        return True

# Usage in commands
rate_limiter = RateLimiter(max_calls=5, period=60)

@bot.tree.command(name="play")
async def play_command(interaction: discord.Interaction, query: str):
    user_id = str(interaction.user.id)
    
    if not rate_limiter.is_allowed(user_id):
        await interaction.response.send_message(
            "⏰ Bạn đang gửi lệnh quá nhanh! Hãy đợi 1 phút.",
            ephemeral=True
        )
        return
    
    # Process command
    ...
```

---

### 18. **Input Sanitization**

```python
# bot/utils/sanitizer.py
import re
from urllib.parse import urlparse

class InputSanitizer:
    """Sanitize user inputs"""
    
    @staticmethod
    def sanitize_url(url: str) -> Optional[str]:
        """Validate and sanitize URL"""
        if not url or len(url) > 2048:
            return None
        
        # Check for valid URL
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ['http', 'https']:
                return None
            
            # Check for allowed domains
            allowed_domains = [
                'youtube.com', 'youtu.be', 'spotify.com',
                'soundcloud.com', 'twitch.tv'
            ]
            
            if not any(domain in parsed.netloc for domain in allowed_domains):
                return None
            
            return url
            
        except Exception:
            return None
    
    @staticmethod
    def sanitize_search_query(query: str) -> str:
        """Sanitize search query"""
        # Remove special characters
        query = re.sub(r'[^\w\s-]', '', query)
        
        # Limit length
        query = query[:200]
        
        # Remove extra whitespace
        query = ' '.join(query.split())
        
        return query
```

---

## 📊 Monitoring & Observability

### 19. **Metrics Collection**

```python
# bot/monitoring/metrics.py
from dataclasses import dataclass
from typing import Dict
import time

@dataclass
class Metrics:
    """Application metrics"""
    total_songs_processed: int = 0
    total_errors: int = 0
    total_playback_time: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    active_guilds: int = 0
    active_connections: int = 0
    
    def to_dict(self) -> Dict[str, any]:
        return {
            "total_songs_processed": self.total_songs_processed,
            "total_errors": self.total_errors,
            "total_playback_time": self.total_playback_time,
            "cache_hit_rate": self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0,
            "active_guilds": self.active_guilds,
            "active_connections": self.active_connections
        }

class MetricsCollector:
    """Collect and expose metrics"""
    
    def __init__(self):
        self.metrics = Metrics()
        self._start_time = time.time()
    
    def record_song_processed(self):
        self.metrics.total_songs_processed += 1
    
    def record_error(self):
        self.metrics.total_errors += 1
    
    def record_cache_hit(self):
        self.metrics.cache_hits += 1
    
    def record_cache_miss(self):
        self.metrics.cache_misses += 1
    
    def get_uptime(self) -> float:
        return time.time() - self._start_time
    
    async def export_metrics(self) -> Dict[str, any]:
        """Export metrics for monitoring"""
        metrics_dict = self.metrics.to_dict()
        metrics_dict["uptime_seconds"] = self.get_uptime()
        return metrics_dict

# Add metrics endpoint
@bot.tree.command(name="metrics")
@app_commands.checks.has_permissions(administrator=True)
async def metrics_command(interaction: discord.Interaction):
    """Show bot metrics (Admin only)"""
    metrics = await metrics_collector.export_metrics()
    
    embed = discord.Embed(title="📊 Bot Metrics", color=discord.Color.blue())
    embed.add_field(name="Songs Processed", value=metrics["total_songs_processed"])
    embed.add_field(name="Cache Hit Rate", value=f"{metrics['cache_hit_rate']:.2%}")
    embed.add_field(name="Uptime", value=f"{metrics['uptime_seconds'] / 3600:.1f}h")
    
    await interaction.response.send_message(embed=embed)
```

---

## 🚀 Deployment Best Practices

### 20. **Health Checks**

```python
# bot/health.py
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class HealthCheck:
    """Health check result"""
    status: HealthStatus
    message: str
    details: Optional[Dict] = None

class HealthChecker:
    """Perform health checks"""
    
    def __init__(self, bot, audio_service):
        self.bot = bot
        self.audio_service = audio_service
    
    async def check_discord_connection(self) -> HealthCheck:
        """Check Discord connection"""
        try:
            if not self.bot.is_ready():
                return HealthCheck(
                    status=HealthStatus.UNHEALTHY,
                    message="Bot not ready"
                )
            
            latency = self.bot.latency * 1000
            if latency > 500:
                return HealthCheck(
                    status=HealthStatus.DEGRADED,
                    message="High latency",
                    details={"latency_ms": latency}
                )
            
            return HealthCheck(
                status=HealthStatus.HEALTHY,
                message="Connected",
                details={"latency_ms": latency}
            )
        except Exception as e:
            return HealthCheck(
                status=HealthStatus.UNHEALTHY,
                message=f"Error: {e}"
            )
    
    async def check_voice_connections(self) -> HealthCheck:
        """Check voice connections"""
        try:
            stats = self.audio_service.get_resource_stats()
            active = stats.get("total_voice_clients", 0)
            
            if active == 0:
                return HealthCheck(
                    status=HealthStatus.HEALTHY,
                    message="No active connections"
                )
            
            return HealthCheck(
                status=HealthStatus.HEALTHY,
                message=f"{active} active connections",
                details=stats
            )
        except Exception as e:
            return HealthCheck(
                status=HealthStatus.UNHEALTHY,
                message=f"Error: {e}"
            )
    
    async def perform_health_check(self) -> Dict[str, HealthCheck]:
        """Perform all health checks"""
        return {
            "discord": await self.check_discord_connection(),
            "voice": await self.check_voice_connections()
        }
```

---

## 📋 Checklist - Ưu Tiên Triển Khai

### 🔴 High Priority (Ngay lập tức)
- [ ] Fix duplicate `cleanup_all()` method
- [ ] Add proper error handling to PlaylistRepository
- [ ] Implement asyncio locks for QueueManager
- [ ] Fix memory leak in SmartCache popular_urls
- [ ] Add BOT_TOKEN masking in logs

### 🟡 Medium Priority (Tuần tới)
- [ ] Implement dependency injection container
- [ ] Add structured logging
- [ ] Add type hints consistency (mypy)
- [ ] Implement rate limiting
- [ ] Add input sanitization

### 🟢 Low Priority (Khi có thời gian)
- [ ] Refactor to event-driven architecture
- [ ] Add comprehensive unit tests
- [ ] Implement metrics collection
- [ ] Add API documentation
- [ ] Setup CI/CD pipeline

---

## 🎓 Kết Luận

Code base có foundation tốt với clean architecture, nhưng cần cải thiện về:

1. **Error Handling**: Nhiều nơi silent fail
2. **Concurrency**: Thiếu thread-safety
3. **Resource Management**: Memory leaks tiềm ẩn
4. **Security**: Input validation không đủ
5. **Testing**: Thiếu unit tests
6. **Monitoring**: Không có observability

Ưu tiên khắc phục các vấn đề High Priority trước, sau đó dần refactor theo các best practices đề xuất.

## 📚 Tài Liệu Tham Khảo

- [Python AsyncIO Best Practices](https://docs.python.org/3/library/asyncio.html)
- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [Clean Architecture in Python](https://www.cosmicpython.com/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [Pytest AsyncIO](https://pytest-asyncio.readthedocs.io/)
