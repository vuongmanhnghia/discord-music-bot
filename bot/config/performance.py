"""
Performance Configuration System
Allows dynamic configuration via .env for different hardware specs
"""

import os
from typing import Dict, Any
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()  # Load .env file
except ImportError:
    pass  # dotenv not installed, use system env only


@dataclass
class PerformanceConfig:
    """Performance configuration for different hardware specs"""

    # Async Processing
    async_workers: int = 3
    max_concurrent_processing: int = 3
    enable_background_processing: bool = True

    # Caching
    cache_size: int = 100
    cache_duration_minutes: int = 60
    memory_limit_mb: int = 512

    # Queue Management
    max_queue_size: int = 100
    processing_queue_size: int = 50

    # Audio Processing
    audio_bitrate: str = "192k"
    audio_format: str = "opus"

    # Network & Retry
    connection_timeout: int = 30
    max_retries: int = 3
    fragment_retries: int = 3
    reconnect_delay_max: int = 5

    # Resource Monitoring & Health
    memory_threshold_percent: int = 85
    enable_resource_monitoring: bool = True
    cleanup_interval_seconds: int = 300
    health_check_interval_seconds: int = 60
    health_check_error_retry_seconds: int = 120
    auto_disconnect_delay_seconds: int = 60

    @classmethod
    def load_from_env(cls) -> "PerformanceConfig":
        """Load configuration from environment variables"""
        return cls(
            # Async Processing
            async_workers=int(os.getenv("BOT_ASYNC_WORKERS", "3")),
            max_concurrent_processing=int(os.getenv("BOT_MAX_CONCURRENT", "3")),
            enable_background_processing=os.getenv(
                "BOT_ENABLE_BACKGROUND", "true"
            ).lower()
            == "true",
            # Caching
            cache_size=int(os.getenv("BOT_CACHE_SIZE", "100")),
            cache_duration_minutes=int(os.getenv("BOT_CACHE_DURATION", "60")),
            memory_limit_mb=int(os.getenv("BOT_MEMORY_LIMIT_MB", "512")),
            # Queue Management
            max_queue_size=int(os.getenv("BOT_MAX_QUEUE_SIZE", "100")),
            processing_queue_size=int(os.getenv("BOT_PROCESSING_QUEUE_SIZE", "200")),  # Increased from 50 to handle large playlists
            # Audio Processing
            audio_bitrate=os.getenv("BOT_AUDIO_BITRATE", "192k"),
            audio_format=os.getenv("BOT_AUDIO_FORMAT", "opus"),
            # Network & Retry
            connection_timeout=int(os.getenv("BOT_CONNECTION_TIMEOUT", "30")),
            max_retries=int(os.getenv("BOT_MAX_RETRIES", "3")),
            fragment_retries=int(os.getenv("BOT_FRAGMENT_RETRIES", "3")),
            reconnect_delay_max=int(os.getenv("BOT_RECONNECT_DELAY_MAX", "5")),
            # Resource Monitoring
            memory_threshold_percent=int(os.getenv("BOT_MEMORY_THRESHOLD", "85")),
            enable_resource_monitoring=os.getenv(
                "BOT_ENABLE_MONITORING", "true"
            ).lower()
            == "true",
            cleanup_interval_seconds=int(os.getenv("BOT_CLEANUP_INTERVAL", "300")),
        )

    def get_ytdl_opts(self) -> Dict[str, Any]:
        """Generate yt-dlp options based on current config"""
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
            # Enhanced network options to handle 403 errors
            "socket_timeout": self.connection_timeout,
            "retries": self.max_retries,
            "fragment_retries": self.fragment_retries,
            "retry_sleep_functions": {
                "http": lambda n: min(2**n, self.reconnect_delay_max)
            },
            # Anti-detection measures for YouTube
            "extractor_args": {
                "youtube": {
                    "skip": ["hls", "dash"],  # Skip problematic formats
                    "player_client": ["android", "web"],  # Use multiple clients
                }
            },
            # Concurrent downloads based on hardware
            "concurrent_fragment_downloads": (
                1 if self.async_workers <= 1 else min(self.async_workers, 3)
            ),
            "http_chunk_size": 1024 * 256 if self.async_workers <= 1 else 1024 * 1024,
            # Additional YouTube workarounds
            "youtube_include_dash_manifest": False,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

    def is_low_resource_mode(self) -> bool:
        """Check if running in low resource mode (RPi-like)"""
        return (
            self.async_workers <= 1
            or self.max_concurrent_processing <= 1
            or self.memory_limit_mb <= 256
        )

    def log_config(self):
        """Log current configuration for debugging"""
        from ..pkg.logger import logger

        mode = "LOW-RESOURCE" if self.is_low_resource_mode() else "HIGH-PERFORMANCE"

        logger.info(f"🔧 Performance Mode: {mode}")
        logger.info(f"⚙️  Async Workers: {self.async_workers}")
        logger.info(f"⚙️  Max Concurrent: {self.max_concurrent_processing}")
        logger.info(f"⚙️  Cache Size: {self.cache_size}")
        logger.info(f"⚙️  Memory Limit: {self.memory_limit_mb}MB")
        logger.info(
            f"⚙️  Background Processing: {'ON' if self.enable_background_processing else 'OFF'}"
        )
        logger.info(f"⚙️  Audio Bitrate: {self.audio_bitrate}")


# Global config instance
performance_config = PerformanceConfig.load_from_env()
