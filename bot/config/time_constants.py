"""Time-related constants for the bot"""


class TimeIntervals:
    """Time interval constants (in seconds)"""

    # Base units
    SECOND = 1
    MINUTE = 60
    HOUR = 3600
    DAY = 86400

    # Health checks
    HEALTH_CHECK_INTERVAL = 60  # 1 minute
    VOICE_CONNECTION_CHECK = 60  # 1 minute
    PLAYBACK_HEALTH_CHECK = 60  # 1 minute

    # Maintenance
    MAINTENANCE_INITIAL_DELAY = 5 * MINUTE  # 5 minutes
    MAINTENANCE_INTERVAL = 6 * HOUR  # 6 hours
    CACHE_CLEANUP_INTERVAL = 1 * HOUR  # 1 hour

    # Auto-disconnect
    AUTO_DISCONNECT_DELAY = 60  # 1 minute when alone
    IDLE_DISCONNECT_TIMEOUT = 5 * MINUTE  # 5 minutes of inactivity

    # Retry and backoff
    RATE_LIMIT_RETRY_DELAY = 5  # 5 seconds
    RECONNECT_DELAY = 3  # 3 seconds
    ERROR_RETRY_DELAY = 10  # 10 seconds

    # Stream URL refresh
    STREAM_URL_TTL = 5 * HOUR  # 5 hours before expiry
    STREAM_URL_REFRESH_THRESHOLD = 4 * HOUR  # Refresh if < 4 hours left

    # Cache
    CACHE_DEFAULT_TTL = 2 * HOUR  # 2 hours
    CACHE_SONG_TTL = 24 * HOUR  # 24 hours for songs

    # Timeouts
    YOUTUBE_EXTRACTION_TIMEOUT = 30  # 30 seconds
    VOICE_CONNECTION_TIMEOUT = 10  # 10 seconds
    COMMAND_RESPONSE_TIMEOUT = 3  # 3 seconds


class Limits:
    """Various limits for the bot"""

    # Queue limits
    MAX_QUEUE_SIZE = 500
    MAX_PLAYLIST_SIZE = 100

    # Song limits
    MAX_SONG_DURATION = 2 * TimeIntervals.HOUR  # 2 hours
    MIN_SONG_DURATION = 1  # 1 second

    # Cache limits
    MAX_CACHE_SIZE = 1000
    MAX_CACHE_SIZE_MB = 512  # 512 MB

    # Processing limits
    MAX_CONCURRENT_PROCESSING = 5
    MAX_ASYNC_WORKERS = 5

    # Rate limits
    MAX_COMMANDS_PER_MINUTE = 20
    MAX_SONGS_PER_USER_PER_HOUR = 50

    # String lengths
    MAX_SONG_TITLE_LENGTH = 100
    MAX_PLAYLIST_NAME_LENGTH = 50
    MAX_URL_LENGTH = 2000


class Defaults:
    """Default values"""

    # Audio
    DEFAULT_VOLUME = 0.5  # 50%
    MIN_VOLUME = 0.0
    MAX_VOLUME = 2.0

    # Bitrate
    DEFAULT_BITRATE = "192k"
    HIGH_QUALITY_BITRATE = "320k"
    LOW_QUALITY_BITRATE = "128k"

    # Format
    DEFAULT_AUDIO_FORMAT = "opus"

    # Queue
    DEFAULT_REPEAT_MODE = "off"  # off, one, queue

    # Processing
    DEFAULT_PRIORITY = "normal"  # low, normal, high
