"""
Configuration validation using Pydantic
Type-safe, validated configuration with better error messages
"""

from typing import Optional, List
from pathlib import Path
from pydantic import BaseSettings, Field, validator, SecretStr
from enum import Enum


class LogLevel(str, Enum):
    """Valid log levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class BotConfig(BaseSettings):
    """
    Type-safe bot configuration with validation
    
    All settings can be overridden via environment variables
    
    Example .env file:
        BOT_TOKEN=your_token_here
        BOT_NAME=My Music Bot
        COMMAND_PREFIX=!
        LOG_LEVEL=INFO
    """
    
    # Required settings
    bot_token: SecretStr = Field(
        ...,
        min_length=50,
        env="BOT_TOKEN",
        description="Discord bot token (required)"
    )
    
    # Bot settings
    bot_name: str = Field(
        default="Discord Music Bot",
        env="BOT_NAME",
        description="Bot display name"
    )
    
    command_prefix: str = Field(
        default="!",
        min_length=1,
        max_length=5,
        env="COMMAND_PREFIX",
        description="Command prefix for text commands"
    )
    
    # Directories
    playlist_dir: Path = Field(
        default=Path("./playlist"),
        env="PLAYLIST_DIR",
        description="Directory for playlist storage"
    )
    
    cache_dir: Path = Field(
        default=Path("./cache"),
        env="CACHE_DIR",
        description="Directory for cache storage"
    )
    
    # Logging
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        env="LOG_LEVEL",
        description="Logging level"
    )
    
    log_file: Optional[Path] = Field(
        default=None,
        env="LOG_FILE",
        description="Log file path (optional)"
    )
    
    # Features
    stay_connected_24_7: bool = Field(
        default=True,
        env="STAY_CONNECTED_24_7",
        description="Stay connected to voice 24/7"
    )
    
    enable_caching: bool = Field(
        default=True,
        env="ENABLE_CACHING",
        description="Enable smart caching"
    )
    
    # Performance
    max_queue_size: int = Field(
        default=100,
        ge=10,
        le=1000,
        env="MAX_QUEUE_SIZE",
        description="Maximum queue size per guild"
    )
    
    cache_size: int = Field(
        default=100,
        ge=10,
        le=1000,
        env="CACHE_SIZE",
        description="Maximum cache size"
    )
    
    async_workers: int = Field(
        default=3,
        ge=1,
        le=10,
        env="ASYNC_WORKERS",
        description="Number of async workers"
    )
    
    # Network
    connection_timeout: int = Field(
        default=30,
        ge=10,
        le=300,
        env="CONNECTION_TIMEOUT",
        description="Connection timeout in seconds"
    )
    
    # Security
    allowed_domains: List[str] = Field(
        default=[
            "youtube.com",
            "youtu.be",
            "spotify.com",
            "soundcloud.com"
        ],
        env="ALLOWED_DOMAINS",
        description="Allowed domains for URLs"
    )
    
    max_input_length: int = Field(
        default=2048,
        ge=100,
        le=10000,
        env="MAX_INPUT_LENGTH",
        description="Maximum input length"
    )
    
    @validator("playlist_dir", "cache_dir")
    def create_directories(cls, v: Path) -> Path:
        """Create directories if they don't exist"""
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    @validator("log_file")
    def create_log_file_dir(cls, v: Optional[Path]) -> Optional[Path]:
        """Create log file directory if specified"""
        if v:
            v.parent.mkdir(parents=True, exist_ok=True)
        return v
    
    @validator("bot_token")
    def validate_token_format(cls, v: SecretStr) -> SecretStr:
        """Validate token format"""
        token = v.get_secret_value()
        
        # Discord bot tokens have specific format
        if not token or len(token) < 50:
            raise ValueError("Invalid bot token format (too short)")
        
        # Basic format check (Discord tokens usually have dots)
        if "." not in token:
            raise ValueError("Invalid bot token format (no delimiters)")
        
        return v
    
    @validator("command_prefix")
    def validate_prefix(cls, v: str) -> str:
        """Validate command prefix"""
        # Prevent problematic prefixes
        forbidden = [" ", "\n", "\t", "\r"]
        if any(char in v for char in forbidden):
            raise ValueError("Command prefix cannot contain whitespace")
        
        return v
    
    def get_safe_token(self) -> str:
        """Get masked token for logging"""
        token = self.bot_token.get_secret_value()
        return f"{token[:10]}...{token[-4:]}"
    
    def get_ytdl_opts(self) -> dict:
        """Generate yt-dlp options from config"""
        return {
            "format": "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
            "extractaudio": True,
            "audioformat": "mp3",
            "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
            "restrictfilenames": True,
            "noplaylist": True,
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "logtostderr": False,
            "quiet": True,
            "no_warnings": True,
            "default_search": "auto",
            "source_address": "0.0.0.0",
            "socket_timeout": self.connection_timeout,
        }
    
    def get_ffmpeg_opts(self) -> dict:
        """Generate FFmpeg options from config"""
        return {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn -b:a 192k",
        }
    
    class Config:
        """Pydantic config"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
        # Allow extra fields in .env (for backward compatibility)
        extra = "ignore"


# Load and validate config
def load_config() -> BotConfig:
    """
    Load and validate configuration
    
    Returns:
        BotConfig: Validated configuration
        
    Raises:
        ValidationError: If configuration is invalid
    """
    try:
        config = BotConfig()
        
        # Log config (safely)
        from ..pkg.logger import logger
        logger.info("✅ Configuration loaded successfully")
        logger.info(f"   Bot Name: {config.bot_name}")
        logger.info(f"   Token: {config.get_safe_token()}")
        logger.info(f"   Prefix: {config.command_prefix}")
        logger.info(f"   Log Level: {config.log_level.value}")
        logger.info(f"   Playlist Dir: {config.playlist_dir}")
        logger.info(f"   Cache Dir: {config.cache_dir}")
        logger.info(f"   Max Queue Size: {config.max_queue_size}")
        logger.info(f"   Async Workers: {config.async_workers}")
        
        return config
        
    except Exception as e:
        # Log and re-raise
        print(f"❌ Configuration validation failed: {e}")
        raise


# Example usage:
"""
from bot.config.validated_config import load_config

try:
    config = load_config()
    
    # Use config
    bot_token = config.bot_token.get_secret_value()
    ytdl_opts = config.get_ytdl_opts()
    
except ValidationError as e:
    print("Configuration errors:")
    for error in e.errors():
        print(f"  - {error['loc'][0]}: {error['msg']}")
    sys.exit(1)
"""


# Example .env.example file to create:
"""
# Discord Music Bot Configuration

# Required: Your Discord bot token
BOT_TOKEN=your_bot_token_here

# Bot Settings
BOT_NAME=My Music Bot
COMMAND_PREFIX=!

# Directories
PLAYLIST_DIR=./playlist
CACHE_DIR=./cache

# Logging
LOG_LEVEL=INFO
LOG_FILE=bot.log

# Features
STAY_CONNECTED_24_7=true
ENABLE_CACHING=true

# Performance
MAX_QUEUE_SIZE=100
CACHE_SIZE=100
ASYNC_WORKERS=3

# Network
CONNECTION_TIMEOUT=30

# Security
ALLOWED_DOMAINS=youtube.com,youtu.be,spotify.com,soundcloud.com
MAX_INPUT_LENGTH=2048
"""
