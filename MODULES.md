# 🏗️ Discord Music Bot - Module Architecture

> **Phân tích chi tiết kiến trúc dự án cho Migration**  
> Cập nhật: 13/12/2025  
> **🚀 Go Migration Status**: Phase 1-3 Complete (Foundation + Repository) ✅  
> **📊 Progress**: 26 tests passing | Build successful | Ready for Audio Service

---

## 📋 Table of Contents

1. [Tổng quan kiến trúc](#1-tổng-quan-kiến-trúc)
2. [Chi tiết các modules](#2-chi-tiết-các-modules)
3. [Dependencies giữa các modules](#3-dependencies-giữa-các-modules)
4. [Migration Strategy](#4-migration-strategy)
5. [Data Flow](#5-data-flow)

---

## 1. Tổng quan kiến trúc

### 1.1 Architecture Pattern

Dự án sử dụng **Clean Architecture** với **Domain-Driven Design (DDD)**:

```
┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                    │
│                    (Discord Commands)                    │
├─────────────────────────────────────────────────────────┤
│                    Application Layer                     │
│                    (Services/Use Cases)                  │
├─────────────────────────────────────────────────────────┤
│                      Domain Layer                        │
│              (Entities, Value Objects, Repos)            │
├─────────────────────────────────────────────────────────┤
│                  Infrastructure Layer                    │
│               (Discord.py, yt-dlp, FFmpeg)               │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Công nghệ chính

#### Python Version (Current - Stable)

-   **Framework**: Discord.py
-   **Audio Processing**: FFmpeg, PyNaCl
-   **Media Extraction**: yt-dlp
-   **Async Processing**: asyncio, ThreadPoolExecutor
-   **Storage**: JSON-based file system
-   **Deployment**: Docker, Docker Compose

#### Go Version (Migration In Progress 🚧)

-   **Framework**: discordgo
-   **Audio Processing**: FFmpeg, gopus, DCA encoder
-   **Media Extraction**: yt-dlp (CLI) + youtube-go
-   **Concurrency**: Goroutines, channels, sync package
-   **Storage**: JSON-based file system (same format)
-   **Deployment**: Single binary, Docker

**Migration Status**: See [GO_MIGRATION_PROGRESS.md](GO_MIGRATION_PROGRESS.md) for details

---

## 2. Chi tiết các modules

### 🎯 MODULE 1: Core Bot Module

**Path**: `bot/music_bot.py`, `run_bot.py`

#### Mục đích

-   Entry point và lifecycle management
-   Bot initialization và configuration
-   Command registration
-   Event bus setup

#### Components

```python
# Main Bot Class
class MusicBot(commands.Bot)
    - __init__(): Initialize services và dependencies
    - setup_hook(): Async initialization
    - on_ready(): Bot startup event
    - _setup_commands(): Register all command handlers

# Opus Loader
class OpusLoader
    - get_opus_paths(): Platform-specific Opus paths
    - load_opus(): Load Opus library cho audio processing
```

#### Dependencies

-   Tất cả services (PlaybackService, AudioService, etc.)
-   All command handlers
-   Configuration module
-   Logger

#### Migration Priority

⭐⭐⭐⭐⭐ **CRITICAL** - Migrate cuối cùng, sau khi tất cả dependencies sẵn sàng

---

### 🎵 MODULE 2: Domain Entities

**Path**: `bot/domain/entities/`

#### 2.1 Song Entity

**File**: `song.py`

```python
@dataclass
class Song:
    # Identity
    - id: str (UUID)
    - original_input: str
    - source_type: SourceType

    # State Management
    - status: SongStatus (PENDING → PROCESSING → READY/FAILED)
    - metadata: Optional[SongMetadata]
    - stream_url: Optional[str]

    # Methods
    - mark_processing()
    - mark_ready(metadata, stream_url)
    - mark_failed(error)
    - refresh_stream_url()
```

**Đặc điểm**:

-   Rich domain object với state machine
-   Immutable identity (UUID)
-   Event publishing cho updates

#### 2.2 Tracklist Entity

**File**: `tracklist.py`

```python
class Tracklist:
    # Core State
    - _songs: List[Song]
    - _current_index: int
    - _history: deque[Song] (max 50)

    # Playback Modes
    - _shuffle_enabled: bool
    - _repeat_mode: str (none/track/queue)

    # Thread Safety
    - _lock: asyncio.Lock

    # Methods
    - add_song(song) → position
    - next_song() → Optional[Song]
    - previous_song() → Optional[Song]
    - skip_to(position)
    - clear()
    - remove_song(position)
```

**Đặc điểm**:

-   Thread-safe với asyncio.Lock
-   O(1) operations với deque
-   Auto-repeat queue logic
-   History management

#### 2.3 Playlist Entity

**File**: `playlist.py`

```python
@dataclass
class Playlist:
    - name: str
    - entries: List[PlaylistEntry]
    - created_at: datetime
    - updated_at: datetime

    # Methods
    - add_entry(original_input, source_type, title)
    - remove_entry(original_input)
    - has_entry(original_input) → bool
    - to_dict() / from_dict()
```

#### 2.4 Library Entity

**File**: `library.py`

```python
class Library:
    - _repository: PlaylistRepository
    - _cache: dict[str, Playlist]

    # CRUD Operations
    - create_playlist(name)
    - get_playlist(name) → Optional[Playlist]
    - save_playlist(playlist)
    - delete_playlist(name)
    - list_playlists() → List[str]
    - add_to_playlist(...)
    - remove_from_playlist(...)
```

#### Migration Priority

⭐⭐⭐⭐⭐ **CRITICAL** - Migrate đầu tiên (no external dependencies)

---

### 🔧 MODULE 3: Value Objects

**Path**: `bot/domain/valueobjects/`

#### 3.1 SourceType

```python
class SourceType(Enum):
    YOUTUBE = "youtube"
    YOUTUBE_PLAYLIST = "youtube_playlist"
    SPOTIFY = "spotify"
    SOUNDCLOUD = "soundcloud"
    URL = "url"
    SEARCH = "search"
```

#### 3.2 SongStatus

```python
class SongStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
```

#### 3.3 SongMetadata

```python
@dataclass
class SongMetadata:
    - title: str
    - artist: Optional[str]
    - duration: int
    - thumbnail: Optional[str]
    - uploader: Optional[str]

    # Computed Properties
    - display_name: str
    - duration_formatted: str
```

#### Migration Priority

⭐⭐⭐⭐⭐ **CRITICAL** - Migrate đầu tiên (pure value objects)

---

### 💾 MODULE 4: Repository Layer

**Path**: `bot/domain/repositories/`

#### PlaylistRepository

**File**: `playlist_repository.py`

```python
class PlaylistRepository:
    - base_path: Path

    # Persistence Methods
    - save(playlist) → bool (atomic write với backup)
    - load(playlist_name) → Optional[Playlist]
    - delete(playlist_name) → bool (soft delete)
    - exists(playlist_name) → bool
    - list_all() → List[str]

    # Private Helpers
    - _get_file_path(playlist_name) → Path
    - _sanitize_filename(name) → str
```

**Đặc điểm**:

-   Atomic writes với temp files
-   Auto-backup trước khi overwrite
-   Soft delete (rename to .deleted)
-   JSON serialization với UTF-8

#### Migration Priority

⭐⭐⭐⭐ **HIGH** - Migrate sau Domain Entities

---

### 🎮 MODULE 5: Audio Service

**Path**: `bot/services/audio/`

#### 5.1 AudioService

**File**: `audio_service.py`

```python
class AudioService:
    # Resource Management
    - _voice_clients: Dict[int, VoiceClient]
    - _audio_players: Dict[int, AudioPlayer]
    - _tracklists: Dict[int, Tracklist]

    # Core Methods
    - connect_to_channel(channel) → bool
    - disconnect_from_guild(guild_id) → bool
    - play_song(guild_id, song)
    - stop_playback(guild_id)
    - pause_playback(guild_id)
    - resume_playback(guild_id)

    # State Queries
    - is_playing(guild_id) → bool
    - is_paused(guild_id) → bool
    - get_tracklist(guild_id) → Tracklist
    - get_current_song(guild_id) → Optional[Song]
```

**Đặc điểm**:

-   Thread-safe với asyncio.Lock
-   24/7 mode (không auto-disconnect)
-   FFmpeg cleanup delays
-   Stream refresh integration

#### 5.2 AudioPlayer

**File**: `audio_player.py`

```python
class AudioPlayer:
    - voice_client: VoiceClient
    - guild_id: int
    - _is_stopping: bool

    # Playback Control
    - play(song, after_callback)
    - stop()
    - pause()
    - resume()

    # State Management
    - mark_disconnected()
    - is_playing: bool
    - is_paused: bool
```

**Đặc điểm**:

-   FFmpeg options optimized
-   Auto-callback sau khi play xong
-   Graceful stop với cleanup

#### Migration Priority

⭐⭐⭐⭐⭐ **CRITICAL** - Core playback functionality

---

### 🎬 MODULE 6: Playback Service

**Path**: `bot/services/playback_service.py`

#### Trách nhiệm chính

1. **User Input Processing**: Analyze URL/search query
2. **Song Creation**: Create Song objects
3. **Async Processing**: Queue songs cho processing workers
4. **Tracklist Management**: Add songs to queue
5. **Playback Control**: Start/stop/skip playback

```python
class PlaybackService:
    # Dependencies
    - audio_service: AudioService
    - library: Library
    - playlist_service: PlaylistService
    - processing_service: ProcessingService
    - async_processor: AsyncSongProcessor
    - youtube_service: YouTubeService

    # Public API
    - play_request(user_input, guild_id, requested_by)
        → (success, message, song)

    - play_playlist(playlist_name, guild_id, requested_by)
        → (success, message, songs_added)

    - play_next(guild_id)
    - play_previous(guild_id)
    - skip_to_position(guild_id, position)
    - stop_playback(guild_id)

    # Internal Flow
    - _add_to_tracklist(song, guild_id)
    - _try_start_playback(guild_id)
    - _playback_loop(guild_id)  # Main loop
    - _handle_song_end(guild_id)
```

**Complete Playback Flow**:

```
1. play_request()
   ↓
2. Input.create_song() [Domain logic]
   ↓
3. async_processor.queue_song() [Background processing]
   ↓
4. tracklist.add_song()
   ↓
5. _try_start_playback() [If not playing]
   ↓
6. _playback_loop() [Main loop]
   ├─→ Wait for song ready
   ├─→ audio_service.play_song()
   ├─→ Wait for song end
   └─→ tracklist.next_song() [Auto-loop]
```

#### Migration Priority

⭐⭐⭐⭐⭐ **CRITICAL** - Core business logic

---

### 🔄 MODULE 7: Processing Service

**Path**: `bot/services/processing_service.py`, `bot/utils/async_processor.py`

#### 7.1 ProcessingService

```python
class ProcessingService:
    - youtube_service: YouTubeService

    # Main Processing
    - process_song(song) → bool
        1. Extract metadata với yt-dlp
        2. Get stream URL
        3. Update song.metadata
        4. Mark song as READY/FAILED
```

#### 7.2 AsyncSongProcessor

**Advanced async processing với worker pool**

```python
class AsyncSongProcessor:
    # Worker Pool
    - _workers: List[asyncio.Task]
    - _queue: asyncio.PriorityQueue
    - _tasks: Dict[str, ProcessingTask]

    # Statistics
    - _worker_stats: Dict[str, WorkerStats]
    - _circuit_breaker: CircuitBreaker

    # Public API
    - queue_song(song, priority, callback) → task_id
    - cancel_task(task_id)
    - get_task_status(task_id) → ProcessingStatus
    - get_statistics() → dict

    # Worker Management
    - _background_worker(worker_id)
    - _process_task(task) → bool
    - start_workers(count=3)
    - stop_workers()
```

**Features**:

-   ✅ 3 parallel workers
-   ✅ Priority queue (URGENT → HIGH → NORMAL → LOW)
-   ✅ Retry với exponential backoff (max 3 retries)
-   ✅ Circuit breaker pattern
-   ✅ Real-time progress callbacks
-   ✅ Worker statistics tracking

#### Migration Priority

⭐⭐⭐⭐ **HIGH** - Core async infrastructure

---

### 🎥 MODULE 8: YouTube Service

**Path**: `bot/services/youtube_service.py`, `bot/utils/youtube.py`

#### 8.1 YouTubeService

```python
class YouTubeService:
    - cache: SmartCache
    - yt_dlp_opts: dict
    - _stats: dict

    # Core Methods
    - get_song_info(url) → (song_data, was_cached)
    - _extract_info(url) → dict
    - _get_best_audio_url(info) → str
    - _detect_source(url) → SourceType

    # Statistics
    - get_cache_stats() → dict
    - clear_cache()
```

#### 8.2 YouTubeHandler (Utils)

```python
class YouTubeHandler:
    # URL Processing
    - is_youtube_url(url) → bool
    - is_youtube_playlist(url) → bool
    - is_spotify_url(url) → bool
    - normalize_youtube_url(url) → str
    - extract_video_id(url) → Optional[str]
    - extract_playlist_id(url) → Optional[str]

    # Playlist Processing
    - get_playlist_videos(playlist_url) → List[dict]
    - process_playlist(url, progress_callback)
```

**Đặc điểm**:

-   Smart caching với TTL
-   Automatic cache invalidation
-   Playlist pagination support
-   Error retry strategy

#### Migration Priority

⭐⭐⭐⭐ **HIGH** - Critical cho song processing

---

### 💿 MODULE 9: Playlist Service

**Path**: `bot/services/playlist_service.py`

```python
class PlaylistService:
    - library: Library

    # Playlist Management
    - create_playlist(name) → (success, message)
    - load_playlist(name) → (success, message)
    - get_playlist_content(name) → (success, songs)
    - add_to_playlist(playlist_name, input, source_type, title)
    - remove_from_playlist(playlist_name, original_input)
    - delete_playlist(name)
    - list_playlists() → List[str]

    # Validation
    - _validate_youtube_url(url) → tuple[bool, str]
    - _sanitize_input(input) → str
```

#### Migration Priority

⭐⭐⭐ **MEDIUM** - Business logic cho playlists

---

### 🔄 MODULE 10: Stream Refresh Service

**Path**: `bot/services/stream_refresh.py`

```python
class StreamRefreshService:
    - _refresh_tasks: Dict[str, asyncio.Task]
    - youtube_service: YouTubeService

    # Core Methods
    - schedule_refresh(song, callback)
        → Refresh stream URL trước khi expire (5 giờ)

    - cancel_refresh(song_id)
    - _refresh_task(song, callback)
    - is_stream_expired(song) → bool
```

**Đặc điểm**:

-   YouTube stream URLs expire sau 6 giờ
-   Auto-refresh sau 5 giờ
-   Callback để update playing song
-   Prevent playback interruption

#### Migration Priority

⭐⭐⭐ **MEDIUM** - Important cho 24/7 bot

---

### 🎨 MODULE 11: Discord UI Utilities

**Path**: `bot/utils/discord_ui.py`

```python
class EmbedFactory:
    # Embed Creators
    - success(title, description, **kwargs) → discord.Embed
    - error(title, description, **kwargs)
    - warning(title, description, **kwargs)
    - info(title, description, **kwargs)
    - now_playing(song, position, queue_size)
    - queue_display(songs, current_position)
    - playlist_display(playlist_name, songs)
    - processing_status(task, progress)

class InteractionManager:
    # Message Management
    - _message_cache: Dict[str, discord.Message]

    - send_and_cache(interaction, embed, key)
    - update_cached(key, embed)
    - delete_cached(key)
    - cleanup_old_messages(guild_id)

class EnhancedProgressCallback:
    # Real-time Progress Updates
    - __init__(bot, guild_id, message_key)
    - update_progress(task: ProcessingTask)
    - notify_complete(task)
    - notify_failed(task)
```

#### Migration Priority

⭐⭐⭐ **MEDIUM** - UI layer, ít dependencies

---

### 🎯 MODULE 12: Event System

**Path**: `bot/utils/events.py`

```python
class SongUpdateEvent:
    - song_id: str
    - guild_id: int

class EventBus:
    # Pub/Sub Pattern
    - _subscribers: Dict[str, List[Callable]]
    - _lock: asyncio.Lock

    - subscribe(event_type, handler)
    - unsubscribe(event_type, handler)
    - publish(event_type, event)

class EventBusManager:
    # Auto-update Now Playing Messages
    - event_bus: EventBus
    - audio_service: AudioService
    - _message_tasks: Dict

    - subscribe_to_events()
    - _handle_song_update(event)
    - update_now_playing_message(guild_id, song)
    - cleanup()
```

**Use Case**:

-   Auto-update "Now Playing" khi metadata được load
-   Real-time UI updates without polling

#### Migration Priority

⭐⭐ **LOW** - Nice-to-have feature

---

### 📦 MODULE 13: Cache System

**Path**: `bot/utils/cache.py`

```python
class SmartCache:
    # LRU Cache với TTL
    - cache_dir: Path
    - max_size: int  # MB
    - ttl: int  # seconds
    - _cache: Dict[str, CachedSong]

    # Methods
    - get_or_process(url, processor_func) → (data, was_cached)
    - set(url, data)
    - get(url) → Optional[data]
    - clear_expired()
    - get_size() → int  # bytes
    - _evict_oldest()  # LRU eviction
    - save_to_disk() / load_from_disk()

@dataclass
class CachedSong:
    - url: str
    - data: dict
    - timestamp: float
    - access_count: int
    - last_access: float
    - size: int  # bytes
```

**Features**:

-   ✅ LRU eviction khi đầy
-   ✅ TTL-based expiration
-   ✅ Disk persistence
-   ✅ Size management
-   ✅ Access statistics

#### Migration Priority

⭐⭐⭐ **MEDIUM** - Performance optimization

---

### ⚙️ MODULE 14: Configuration

**Path**: `bot/config/`

#### 14.1 Config

**File**: `config.py`

```python
class Config:
    # Singleton Pattern
    _instance: Optional[Config]

    # Environment Variables
    - BOT_TOKEN: str (required)
    - BOT_NAME: str
    - VERSION: str
    - COMMAND_PREFIX: str
    - PLAYLIST_DIR: str
    - STAY_CONNECTED_24_7: bool
    - LOG_LEVEL: str
    - LOG_FILE: str

    # Methods
    - _validate()
    - _setup_directories()
    - get_safe_token() → str  # masked
```

#### 14.2 Performance Config

**File**: `performance.py`

```python
class PerformanceConfig:
    # Detection
    - platform: str  # x86_64, aarch64, arm
    - cpu_count: int
    - total_ram: int  # GB

    # Optimized Settings
    - worker_count: int
    - max_queue_size: int
    - cache_size: int  # MB
    - cache_duration_minutes: int
    - async_timeout: int

    # FFmpeg Options
    - get_ffmpeg_opts() → dict
    - get_ytdl_opts() → dict

    # Auto-tuning
    - _detect_platform()
    - _optimize_for_platform()
    - _auto_tune_cache()
```

**Platform Optimization**:

```
x86_64:  workers=3, cache=100MB, queue=100
aarch64: workers=2, cache=50MB,  queue=50  (Raspberry Pi)
arm:     workers=1, cache=30MB,  queue=30  (Older ARM)
```

#### 14.3 Constants

**Files**: `constants.py`, `service_constants.py`

```python
# Bot Constants
EMBED_COLOR_SUCCESS = 0x2ECC71
EMBED_COLOR_ERROR = 0xE74C3C
VOICE_CONNECTION_TIMEOUT = 10.0
FFMPEG_CLEANUP_DELAY = 0.5

# Error Messages
class ErrorMessages:
    @staticmethod
    def user_not_in_voice() → str
    @staticmethod
    def bot_not_connected() → str
    # ... more error messages
```

#### Migration Priority

⭐⭐⭐⭐ **HIGH** - Required by all modules

---

### 🎮 MODULE 15: Commands

**Path**: `bot/commands/`

#### Base Command Handler

**File**: `__init__.py`

```python
class BaseCommandHandler:
    - bot: MusicBot

    # Validation Helpers
    - ensure_guild_context(interaction) → bool
    - ensure_user_in_voice(interaction) → bool
    - ensure_bot_connected(interaction) → bool
    - ensure_same_voice_channel(interaction) → bool
    - handle_command_error(interaction, error, command)

class CommandRegistry:
    # Register all handlers
    @staticmethod
    - register_all(bot)
```

#### 15.1 Basic Commands

**File**: `basic_commands.py`

```python
class BasicCommandHandler(BaseCommandHandler):
    # Commands
    - /ping: Check bot latency
    - /join: Join voice channel
    - /leave: Leave voice channel
```

#### 15.2 Playback Commands

**File**: `playback_commands.py`

```python
class PlaybackCommandHandler(BaseCommandHandler):
    # Commands
    - /play <url|search>: Play song
    - /pause: Pause playback
    - /resume: Resume playback
    - /stop: Stop and clear queue
    - /skip [amount]: Skip songs
    - /back: Previous song
    - /now: Show now playing
```

#### 15.3 Queue Commands

**File**: `queue_commands.py`

```python
class QueueCommandHandler(BaseCommandHandler):
    # Commands
    - /queue: Show queue
    - /remove <position>: Remove from queue
    - /clear: Clear entire queue
    - /shuffle: Toggle shuffle mode
    - /repeat <mode>: Set repeat mode
    - /skipto <position>: Jump to position
```

#### 15.4 Playlist Commands

**File**: `playlist_commands.py`

```python
class PlaylistCommandHandler(BaseCommandHandler):
    # Commands
    - /playlists: List all playlists
    - /playlist <name>: Show playlist content
    - /create <name>: Create playlist
    - /delete <name>: Delete playlist
    - /add <song>: Add to active playlist
    - /removesong <url>: Remove from playlist
    - /loadplaylist <name>: Activate playlist
    - /playplaylist <name>: Load and play
```

#### 15.5 Advanced Commands

**File**: `advanced_commands.py`

```python
class AdvancedCommandHandler(BaseCommandHandler):
    # Commands
    - /stats: Bot statistics
    - /cache: Cache statistics
    - /health: System health check
```

#### Migration Priority

⭐⭐ **LOW** - Migrate cuối, sau khi services sẵn sàng

---

### 📊 MODULE 16: Utilities

**Path**: `bot/utils/`

#### 16.1 Core Utilities

**File**: `core.py`

```python
class Validator:
    # Input Validation
    - is_valid_url(url) → bool
    - is_youtube_url(url) → bool
    - validate_playlist_name(name) → tuple[bool, str]

class VoiceStateHelper:
    # Voice State Checks
    - get_user_voice_channel(member) → Optional[VoiceChannel]
    - is_in_same_channel(bot, member) → bool
    - can_join_channel(channel) → bool

class ErrorEmbedFactory:
    - from_exception(exception) → discord.Embed
```

#### 16.2 Decorators

**File**: `decorators.py`

```python
# Performance Decorators
- @measure_time: Log execution time
- @retry_on_error: Auto retry với backoff
- @rate_limit: Rate limiting cho commands
- @require_voice: Check user in voice channel
```

#### 16.3 Exceptions

**File**: `exceptions.py`

```python
class MusicBotException(Exception): pass

class VoiceConnectionError(MusicBotException): pass
class UserNotInVoiceChannelError(MusicBotException): pass
class ProcessingError(MusicBotException): pass
class PlaylistError(MusicBotException): pass
class CacheError(MusicBotException): pass
```

#### Migration Priority

⭐⭐⭐ **MEDIUM** - Support utilities

---

### 📝 MODULE 17: Logger

**Path**: `bot/pkg/logger.py`

```python
def setup_logger(name, level=None) → logging.Logger:
    # Features
    - Colored console output
    - File logging (optional)
    - JSON formatting cho production
    - Rotation policy
    - Performance logging

# Usage
logger = setup_logger(__name__)
logger.info("Message")
logger.error("Error", exc_info=True)
```

#### Migration Priority

⭐⭐⭐⭐⭐ **CRITICAL** - Required by all modules

---

## 3. Dependencies giữa các modules

### 3.1 Dependency Graph

```
┌───────────────────────────────────────────────────────────┐
│                       MusicBot (Core)                     │
│  ┌──────────────────────────────────────────────────┐    │
│  │              Command Handlers (15)                │    │
│  └────────────────────┬─────────────────────────────┘    │
│                       ↓                                    │
│  ┌──────────────────────────────────────────────────┐    │
│  │             PlaybackService (6)                   │    │
│  │  ┌──────────────────────────────────────────┐    │    │
│  │  │     AudioService (5)                     │    │    │
│  │  │  ┌─────────────────────────────────┐    │    │    │
│  │  │  │   AudioPlayer (5.2)             │    │    │    │
│  │  │  │   ├─ Tracklist (2.2)            │    │    │    │
│  │  │  │   └─ Song (2.1)                 │    │    │    │
│  │  │  └─────────────────────────────────┘    │    │    │
│  │  └──────────────────────────────────────────┘    │    │
│  │                                                   │    │
│  │  ┌──────────────────────────────────────────┐    │    │
│  │  │   ProcessingService (7)                  │    │    │
│  │  │   ├─ AsyncSongProcessor (7.2)           │    │    │
│  │  │   └─ YouTubeService (8)                 │    │    │
│  │  │       └─ Cache (13)                     │    │    │
│  │  └──────────────────────────────────────────┘    │    │
│  │                                                   │    │
│  │  ┌──────────────────────────────────────────┐    │    │
│  │  │   PlaylistService (9)                    │    │    │
│  │  │   └─ Library (2.4)                       │    │    │
│  │  │       └─ PlaylistRepository (4)          │    │    │
│  │  │           └─ Playlist (2.3)              │    │    │
│  │  └──────────────────────────────────────────┘    │    │
│  │                                                   │    │
│  │  ┌──────────────────────────────────────────┐    │    │
│  │  │   StreamRefreshService (10)              │    │    │
│  │  └──────────────────────────────────────────┘    │    │
│  └───────────────────────────────────────────────────┘    │
│                                                            │
│  ┌──────────────────────────────────────────────────┐    │
│  │         Support Modules                          │    │
│  │  - EventBus (12)                                 │    │
│  │  - Discord UI (11)                               │    │
│  │  - Config (14)                                   │    │
│  │  - Logger (17)                                   │    │
│  │  - Utils (16)                                    │    │
│  └──────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────┘
```

### 3.2 Module Dependency Matrix

| Module                      | Depends On                                             | Used By                            |
| --------------------------- | ------------------------------------------------------ | ---------------------------------- |
| **Value Objects (3)**       | -                                                      | Song, SongMetadata                 |
| **Song (2.1)**              | Value Objects (3)                                      | Tracklist, AudioPlayer, Processing |
| **Tracklist (2.2)**         | Song (2.1)                                             | AudioService                       |
| **Playlist (2.3)**          | -                                                      | Library, Repository                |
| **PlaylistRepository (4)**  | Playlist (2.3), Logger                                 | Library                            |
| **Library (2.4)**           | PlaylistRepository (4)                                 | PlaylistService                    |
| **AudioPlayer (5.2)**       | Song (2.1), Logger                                     | AudioService                       |
| **AudioService (5.1)**      | AudioPlayer (5.2), Tracklist (2.2), StreamRefresh (10) | PlaybackService, Commands          |
| **YouTubeService (8)**      | Cache (13), Config (14), Logger                        | ProcessingService                  |
| **ProcessingService (7.1)** | YouTubeService (8), Song (2.1)                         | AsyncProcessor, PlaybackService    |
| **AsyncProcessor (7.2)**    | ProcessingService (7.1), Song (2.1)                    | PlaybackService                    |
| **PlaylistService (9)**     | Library (2.4)                                          | PlaybackService, Commands          |
| **PlaybackService (6)**     | ALL above services + Song + Tracklist                  | Commands                           |
| **Commands (15)**           | PlaybackService (6), AudioService (5), UI (11)         | MusicBot                           |
| **MusicBot (1)**            | ALL modules                                            | -                                  |

---

## 4. Migration Strategy

### 4.1 Migration Phases

#### **Phase 1: Foundation (Week 1)**

**Modules**: Value Objects, Domain Entities, Logger, Config

```
1. Value Objects (3) ⭐⭐⭐⭐⭐
   - SourceType, SongStatus, SongMetadata
   - Pure Python, no dependencies

2. Logger (17) ⭐⭐⭐⭐⭐
   - Setup logging infrastructure
   - Required by all modules

3. Config (14) ⭐⭐⭐⭐⭐
   - Environment variable management
   - Platform detection

4. Song Entity (2.1) ⭐⭐⭐⭐⭐
   - Core domain object
   - Depends only on Value Objects

5. Tracklist Entity (2.2) ⭐⭐⭐⭐⭐
   - Queue management
   - Depends on Song

6. Playlist + Library (2.3, 2.4) ⭐⭐⭐⭐⭐
   - Playlist management
   - Repository pattern
```

**Validation**:

-   ✅ Unit tests cho tất cả entities
-   ✅ Integration tests cho Repository
-   ✅ Config validation

---

#### **Phase 2: Core Services (Week 2)**

**Modules**: Audio Service, YouTube Service, Cache

```
7. Cache System (13) ⭐⭐⭐
   - LRU cache với TTL
   - Required by YouTubeService

8. YouTubeService (8) ⭐⭐⭐⭐
   - yt-dlp integration
   - Smart caching

9. ProcessingService (7.1) ⭐⭐⭐⭐
   - Song metadata extraction
   - Stream URL extraction

10. AsyncProcessor (7.2) ⭐⭐⭐⭐
    - Background worker pool
    - Priority queue

11. AudioPlayer (5.2) ⭐⭐⭐⭐⭐
    - FFmpeg integration
    - Basic playback

12. AudioService (5.1) ⭐⭐⭐⭐⭐
    - Voice connection management
    - Tracklist management
    - Playback control
```

**Validation**:

-   ✅ Test audio playback end-to-end
-   ✅ Test cache hit/miss
-   ✅ Test worker pool với multiple songs
-   ✅ Test stream URL extraction

---

#### **Phase 3: Business Logic (Week 3)**

**Modules**: Playback Service, Playlist Service, Stream Refresh

```
13. StreamRefreshService (10) ⭐⭐⭐
    - Auto-refresh expired streams
    - Important cho 24/7 bot

14. PlaylistService (9) ⭐⭐⭐
    - Playlist CRUD operations
    - Validation logic

15. PlaybackService (6) ⭐⭐⭐⭐⭐
    - Main business logic
    - Complete playback flow
    - Playlist integration
```

**Validation**:

-   ✅ Test complete playback flow
-   ✅ Test playlist loading + playback
-   ✅ Test stream refresh
-   ✅ Test error scenarios

---

#### **Phase 4: UI & Commands (Week 4)**

**Modules**: Discord UI, Event System, Commands

```
16. Utils (16) ⭐⭐⭐
    - Core utilities
    - Validators
    - Decorators
    - Exceptions

17. Discord UI (11) ⭐⭐⭐
    - Embed factory
    - Message management
    - Progress callbacks

18. EventBus (12) ⭐⭐
    - Event system
    - Auto-update messages

19. Commands (15) ⭐⭐
    - All Discord slash commands
    - Command handlers
```

**Validation**:

-   ✅ Test all commands manually
-   ✅ Test error handling
-   ✅ Test UI updates
-   ✅ Test event propagation

---

#### **Phase 5: Integration (Week 5)**

**Modules**: Core Bot, Final Integration

```
20. MusicBot Core (1) ⭐⭐⭐⭐⭐
    - Bot initialization
    - Service wiring
    - Command registration
    - Event bus setup

21. Opus Loader
    - Platform-specific loading
    - Error handling

22. Entry Point (run_bot.py)
    - Main entry
    - Graceful shutdown
```

**Validation**:

-   ✅ Full integration test
-   ✅ Test on multiple platforms (x86_64, ARM64)
-   ✅ Load testing (multiple guilds)
-   ✅ 24/7 stability test (24+ hours)
-   ✅ Memory leak detection

---

### 4.2 Testing Strategy

#### Unit Tests

```python
# tests/unit/
- test_song_entity.py ✅ (exists)
- test_tracklist.py ✅ (exists)
- test_playlist.py
- test_library.py
- test_cache.py
- test_validators.py
```

#### Integration Tests

```python
# tests/integration/
- test_playback_flow.py ✅ (exists)
- test_audio_service.py
- test_youtube_service.py
- test_playlist_service.py
- test_async_processor.py
```

#### E2E Tests

```python
# tests/e2e/
- test_bot_commands.py
- test_complete_flow.py
- test_24_7_stability.py
```

---

### 4.3 Migration Checklist

#### Pre-Migration

-   [ ] Backup current database (playlists)
-   [ ] Document current bot behavior
-   [ ] Setup test environment
-   [ ] Create migration branch

#### Per Module

-   [ ] Create new module structure
-   [ ] Migrate code with minimal changes
-   [ ] Add type hints
-   [ ] Write unit tests
-   [ ] Update imports
-   [ ] Test in isolation
-   [ ] Integration test với existing modules
-   [ ] Code review
-   [ ] Merge to migration branch

#### Post-Migration

-   [ ] Full integration test
-   [ ] Performance benchmarking
-   [ ] Memory profiling
-   [ ] Load testing
-   [ ] Documentation update
-   [ ] Deployment plan
-   [ ] Rollback plan

---

## 5. Data Flow

### 5.1 Play Song Flow

```
User: /play <url>
    ↓
[PlaybackCommandHandler]
    ├─ Validate: user in voice, bot permissions
    ├─ Send: "🔍 Processing..." message
    └─ Call: playback_service.play_request()
        ↓
[PlaybackService]
    ├─ Analyze input → Input.create_song()
    │   └─ Detect: URL type, search query
    │       → Create Song (PENDING status)
    │
    ├─ Queue for processing
    │   └─ async_processor.queue_song(song, priority=NORMAL)
    │       ↓
    │   [AsyncSongProcessor]
    │       ├─ Add to priority queue
    │       ├─ Background worker picks up task
    │       └─ Call: processing_service.process_song()
    │           ↓
    │       [ProcessingService]
    │           ├─ Call: youtube_service.get_song_info()
    │           │   ↓
    │           │   [YouTubeService]
    │           │       ├─ Check cache
    │           │       ├─ If miss: yt-dlp extract
    │           │       ├─ Save to cache
    │           │       └─ Return: (metadata, stream_url)
    │           │
    │           ├─ Update song.metadata
    │           ├─ Update song.stream_url
    │           └─ Mark song.status = READY
    │               ↓
    │               Publish SongUpdateEvent
    │               ↓
    │           [EventBus]
    │               └─ Notify: Update "Now Playing" message
    │
    ├─ Add to tracklist
    │   └─ tracklist.add_song(song) → position
    │
    ├─ Update UI: "Added to queue at #X"
    │
    └─ Start playback (if not playing)
        └─ _playback_loop(guild_id)
            ↓
        [Playback Loop]
            ├─ Get current song from tracklist
            ├─ Wait until song.is_ready
            ├─ Call: audio_service.play_song(song)
            │   ↓
            │   [AudioService]
            │       ├─ Get FFmpeg options
            │       ├─ Create PCMVolumeTransformer
            │       └─ voice_client.play(audio_source, after=callback)
            │           ↓
            │           [Discord.py]
            │               └─ Stream audio to voice channel
            │
            ├─ Update UI: "🎵 Now Playing"
            ├─ Wait for song end (callback)
            │
            ├─ Schedule stream refresh (after 5 hours)
            │   └─ stream_refresh_service.schedule_refresh()
            │
            ├─ Song ended → Call: tracklist.next_song()
            │   ├─ If repeat_track: stay on same song
            │   ├─ If repeat_queue && end: goto first song
            │   └─ Else: increment index
            │
            └─ Loop back to start
                (Auto-play next song)
```

---

### 5.2 Playlist Play Flow

```
User: /playplaylist <name>
    ↓
[PlaylistCommandHandler]
    ├─ Load playlist from library
    ├─ For each entry in playlist:
    │   ├─ Create Song (PENDING)
    │   ├─ Queue for processing (priority=LOW)
    │   └─ Add to tracklist
    │       └─ await asyncio.sleep(0.2)  # Rate limiting
    │
    ├─ Update UI: "Loading playlist... X/Y songs"
    │
    └─ Background workers process songs in parallel
        ├─ Worker 1: Song 1, 4, 7, ...
        ├─ Worker 2: Song 2, 5, 8, ...
        └─ Worker 3: Song 3, 6, 9, ...
```

---

### 5.3 Cache Flow

```
[YouTubeService.get_song_info(url)]
    ↓
[SmartCache.get_or_process(url, extractor)]
    ├─ Check cache
    │   ├─ Hit:
    │   │   ├─ Check TTL (expired?)
    │   │   ├─ Update access stats
    │   │   └─ Return cached data
    │   │
    │   └─ Miss:
    │       ├─ Call: extractor(url)
    │       │   └─ yt-dlp.extract_info()
    │       │
    │       ├─ Check cache size
    │       │   └─ If full: evict oldest (LRU)
    │       │
    │       ├─ Save to cache
    │       └─ Return fresh data
    │
    └─ Background task: cleanup_expired()
        └─ Every 1 hour: remove expired entries
```

---

### 5.4 Stream Refresh Flow

```
[AudioService.play_song(song)]
    ↓
    ├─ Play audio
    │
    └─ Schedule refresh
        └─ stream_refresh_service.schedule_refresh(song)
            ↓
        [StreamRefreshService]
            ├─ Calculate: 5 hours from now
            ├─ Create asyncio.Task
            │   └─ await asyncio.sleep(5 * 3600)
            │       ↓
            │   [Refresh Task]
            │       ├─ Check: is song still playing?
            │       ├─ Call: youtube_service.get_song_info(url)
            │       ├─ Update: song.stream_url
            │       └─ If currently playing:
            │           └─ Seamless stream URL swap
            │
            └─ Store task in _refresh_tasks dict
                (Cleanup on song end)
```

---

### 5.5 Event Flow

```
[Song.mark_ready(metadata, stream_url)]
    ↓
    └─ Publish SongUpdateEvent
        ↓
    [EventBus.publish('song_update', event)]
        ↓
        ├─ Notify all subscribers
        │
        └─ [EventBusManager._handle_song_update()]
            ↓
            ├─ Get current song from audio_service
            ├─ Check: is this the playing song?
            │
            └─ If yes: Update "Now Playing" message
                └─ interaction_manager.update_cached()
                    ↓
                    [Discord API]
                        └─ message.edit(embed=new_embed)
                            (User sees updated title instantly)
```

---

## 6. Key Design Patterns

### 6.1 Patterns Used

| Pattern             | Where                           | Why                          |
| ------------------- | ------------------------------- | ---------------------------- |
| **Singleton**       | Config, Logger                  | Single instance toàn app     |
| **Repository**      | PlaylistRepository              | Persist playlists to JSON    |
| **Factory**         | EmbedFactory, ErrorEmbedFactory | Create Discord embeds        |
| **Observer**        | EventBus                        | Pub/Sub cho song updates     |
| **State Machine**   | Song.status                     | PENDING → PROCESSING → READY |
| **Strategy**        | RetryStrategy                   | Configurable retry logic     |
| **Command**         | Discord Commands                | Encapsulate user actions     |
| **Facade**          | PlaybackService                 | Simplify complex subsystems  |
| **Worker Pool**     | AsyncSongProcessor              | Parallel processing          |
| **Circuit Breaker** | AsyncSongProcessor              | Fault tolerance              |
| **LRU Cache**       | SmartCache                      | Optimize YouTube API calls   |

---

### 6.2 SOLID Principles

#### Single Responsibility

-   ✅ Each service has ONE clear purpose
-   ✅ AudioService: Voice connections + playback
-   ✅ YouTubeService: Media extraction only
-   ✅ PlaylistService: Playlist management only

#### Open/Closed

-   ✅ Easy to add new SourceTypes
-   ✅ Easy to add new commands
-   ✅ Easy to add new event handlers

#### Liskov Substitution

-   ✅ All command handlers extend BaseCommandHandler
-   ✅ Can swap YouTubeService với SpotifyService

#### Interface Segregation

-   ✅ Small, focused interfaces
-   ✅ Services expose only needed methods

#### Dependency Inversion

-   ✅ Services depend on abstractions (interfaces)
-   ✅ Dependency injection in constructors

---

## 7. Performance Considerations

### 7.1 Optimizations

1. **Async Processing**

    - 3 parallel workers
    - Priority queue
    - Non-blocking I/O

2. **Smart Caching**

    - LRU eviction
    - TTL-based expiration
    - Disk persistence

3. **Platform-Specific Tuning**

    - ARM64: reduced workers, smaller cache
    - x86_64: maximum performance

4. **Stream Refresh**

    - Prevent URL expiration
    - No playback interruption

5. **Memory Management**
    - Deque với maxlen (auto-evict)
    - Cache size limits
    - Periodic cleanup tasks

### 7.2 Bottlenecks

⚠️ **Potential Issues**:

1. YouTube rate limiting → Cache helps
2. FFmpeg memory usage → Cleanup delays
3. Disk I/O cho playlists → Atomic writes
4. Network latency → Async processing

---

## 8. Security Considerations

### 8.1 Input Validation

```python
# URL Validation
- Validator.is_valid_url()
- YouTubeHandler.normalize_youtube_url()

# Filename Sanitization
- PlaylistRepository._sanitize_filename()

# Command Validation
- BaseCommandHandler.ensure_*()
```

### 8.2 Error Handling

```python
# Graceful Degradation
- Circuit breaker cho repeated failures
- Retry với exponential backoff
- Fallback to cached data

# Safe Failures
- Never expose internal errors to users
- Log detailed errors for debugging
- Show user-friendly error messages
```

---

## 9. Future Improvements

### 9.1 Planned Features

1. **Spotify Integration** ⭐⭐⭐⭐

    - Direct Spotify playback
    - Spotify playlist support

2. **SoundCloud Support** ⭐⭐⭐

    - SoundCloud URLs
    - SoundCloud playlists

3. **Database Migration** ⭐⭐⭐⭐

    - PostgreSQL cho playlists
    - User preferences
    - Play history

4. **Web Dashboard** ⭐⭐⭐

    - Remote control
    - Statistics
    - Playlist management

5. **Voice Effects** ⭐⭐
    - Bass boost
    - Nightcore
    - Equalizer

### 9.2 Technical Debt

1. **Testing Coverage**

    - [ ] Increase to 80%+
    - [ ] More integration tests
    - [ ] E2E test suite

2. **Documentation**

    - [ ] API documentation
    - [ ] Architecture diagrams
    - [ ] Deployment guide

3. **Monitoring**
    - [ ] Prometheus metrics
    - [ ] Grafana dashboards
    - [ ] Alert system

---

## 10. Deployment

### 10.1 Docker Support

```yaml
# docker-compose.yml
services:
    bot:
        build: .
        environment:
            - BOT_TOKEN=${BOT_TOKEN}
            - STAY_CONNECTED_24_7=true
        volumes:
            - ./playlist:/app/playlist
            - ./cache:/app/cache
        restart: unless-stopped
```

### 10.2 Platform Support

| Platform            | Status          | Notes               |
| ------------------- | --------------- | ------------------- |
| Linux x86_64        | ✅ Full Support | Optimal performance |
| Linux ARM64         | ✅ Full Support | Raspberry Pi 4/5    |
| Linux ARMv7         | ✅ Full Support | Raspberry Pi 3      |
| macOS Intel         | ✅ Via Docker   | Docker Desktop      |
| macOS Apple Silicon | ✅ Native ARM64 | Docker Desktop      |

---

## 11. Conclusion

### 11.1 Strengths

✅ **Clean Architecture**: Well-separated concerns  
✅ **Async-First**: Non-blocking I/O throughout  
✅ **Scalable**: Worker pool, caching, optimizations  
✅ **Maintainable**: SOLID principles, clear structure  
✅ **Portable**: Multi-platform Docker support  
✅ **Reliable**: Error handling, retries, circuit breakers

### 11.2 Migration Success Criteria

-   [ ] All 20 modules migrated and tested
-   [ ] 80%+ test coverage
-   [ ] Zero breaking changes for users
-   [ ] Performance equal or better
-   [ ] Documentation complete
-   [ ] Deployed successfully

### 11.3 Contact & Support

**Migration Team**:

-   Lead: [Your Name]
-   Start Date: [TBD]
-   Target Completion: 5 weeks

**Resources**:

-   GitHub: [Repository URL]
-   Documentation: [Docs URL]
-   Discord: [Support Server]

---

**Document Version**: 1.0.0  
**Last Updated**: December 13, 2025  
**Status**: ✅ Ready for Migration
