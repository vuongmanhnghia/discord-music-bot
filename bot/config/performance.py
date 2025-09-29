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

    # Resource Monitoring
    memory_threshold_percent: int = 85
    enable_resource_monitoring: bool = True
    cleanup_interval_seconds: int = 300

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
            processing_queue_size=int(os.getenv("BOT_PROCESSING_QUEUE_SIZE", "50")),
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
            "format": "bestaudio/best",
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
            # Dynamic network options
            "socket_timeout": self.connection_timeout,
            "retries": self.max_retries,
            "fragment_retries": self.fragment_retries,
            "retry_sleep_functions": {
                "http": lambda n: min(2**n, self.reconnect_delay_max)
            },
            # Concurrent downloads based on hardware
            "concurrent_fragment_downloads": (
                1 if self.async_workers <= 1 else min(self.async_workers, 3)
            ),
            "http_chunk_size": 1024 * 256 if self.async_workers <= 1 else 1024 * 1024,
        }

    def get_ffmpeg_opts(self) -> Dict[str, str]:
        """Generate FFmpeg options based on current config"""
        return {
            "before_options": f"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max {self.reconnect_delay_max} -thread_queue_size 512",
            "options": f"-vn -b:a {self.audio_bitrate}",
        }

    def is_low_resource_mode(self) -> bool:
        """Check if running in low resource mode (RPi-like)"""
        return (
            self.async_workers <= 1
            or self.max_concurrent_processing <= 1
            or self.memory_limit_mb <= 256
        )

    def get_preset_rpi4(self) -> "PerformanceConfig":
        """Get optimized preset for Raspberry Pi 4"""
        config = PerformanceConfig(
            # Minimal async processing
            async_workers=1,
            max_concurrent_processing=1,
            enable_background_processing=False,
            # Conservative caching
            cache_size=30,
            cache_duration_minutes=30,
            memory_limit_mb=200,
            # Limited queues
            max_queue_size=20,
            processing_queue_size=10,
            # Lower quality audio to save bandwidth/CPU
            audio_bitrate="128k",
            audio_format="opus",
            # Aggressive timeouts
            connection_timeout=20,
            max_retries=2,
            fragment_retries=2,
            reconnect_delay_max=3,
            # Frequent monitoring
            memory_threshold_percent=75,
            enable_resource_monitoring=True,
            cleanup_interval_seconds=180,
        )
        return config

    def get_preset_powerful(self) -> "PerformanceConfig":
        """Get optimized preset for powerful servers"""
        config = PerformanceConfig(
            # Full async processing
            async_workers=5,
            max_concurrent_processing=5,
            enable_background_processing=True,
            # Aggressive caching
            cache_size=200,
            cache_duration_minutes=120,
            memory_limit_mb=1024,
            # Large queues
            max_queue_size=200,
            processing_queue_size=100,
            # High quality audio
            audio_bitrate="320k",
            audio_format="opus",
            # Generous timeouts
            connection_timeout=45,
            max_retries=5,
            fragment_retries=5,
            reconnect_delay_max=10,
            # Less frequent monitoring
            memory_threshold_percent=90,
            enable_resource_monitoring=True,
            cleanup_interval_seconds=600,
        )
        return config

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
