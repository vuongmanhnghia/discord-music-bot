"""
YouTube Error Handler
Utilities for handling YouTube errors and 403 Forbidden issues
"""

import asyncio
import logging
from typing import Optional, Dict, Any
import time

logger = logging.getLogger(__name__)


class YouTubeErrorHandler:
    """Handle YouTube-specific errors and implement retry strategies"""

    def __init__(self):
        self._last_403_time: Dict[str, float] = {}
        self._retry_delays = [1, 2, 5, 10, 30]  # Progressive delay in seconds

    def is_403_error(self, error_msg: str) -> bool:
        """Check if error is a 403 Forbidden error"""
        error_indicators = [
            "403 Forbidden",
            "Server returned 403",
            "HTTP error 403",
            "access denied",
            "Access denied",
        ]
        return any(indicator in error_msg for indicator in error_indicators)

    def should_retry_403(self, url: str, attempt: int) -> bool:
        """Determine if we should retry a 403 error"""
        current_time = time.time()
        last_403 = self._last_403_time.get(url, 0)

        # Don't retry if we got 403 for this URL recently (< 5 minutes)
        if current_time - last_403 < 300:
            return False

        # Update last 403 time
        self._last_403_time[url] = current_time

        # Only retry up to 3 times
        return attempt < 3

    async def get_retry_delay(self, attempt: int) -> int:
        """Get progressive retry delay"""
        if attempt >= len(self._retry_delays):
            return self._retry_delays[-1]
        return self._retry_delays[attempt]

    def get_alternative_format(self, attempt: int) -> str:
        """Get alternative format string based on attempt number"""
        formats = [
            "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",  # Default
            "worst[ext=webm]/worst[ext=m4a]/worst/best",  # Attempt 1: Lower quality
            "bestaudio[protocol^=http]/best[protocol^=http]",  # Attempt 2: HTTP only
            "worst",  # Attempt 3: Absolute worst
        ]

        if attempt >= len(formats):
            return formats[-1]
        return formats[attempt]

    def get_alternative_extractor_args(self, attempt: int) -> Dict[str, Any]:
        """Get alternative extractor arguments based on attempt number"""
        configs = [
            # Default: Skip problematic formats
            {
                "youtube": {
                    "skip": ["hls", "dash"],
                    "player_client": ["android", "web"],
                }
            },
            # Attempt 1: Try web client only
            {
                "youtube": {
                    "skip": ["hls"],
                    "player_client": ["web"],
                }
            },
            # Attempt 2: Try android client only
            {
                "youtube": {
                    "skip": ["dash"],
                    "player_client": ["android"],
                }
            },
            # Attempt 3: Minimal config
            {
                "youtube": {
                    "player_client": ["web"],
                }
            },
        ]

        if attempt >= len(configs):
            return configs[-1]
        return configs[attempt]

    def clean_old_403_records(self, max_age_hours: int = 24):
        """Clean up old 403 records to prevent memory leak"""
        current_time = time.time()
        cutoff_time = current_time - (max_age_hours * 3600)

        urls_to_remove = [
            url
            for url, timestamp in self._last_403_time.items()
            if timestamp < cutoff_time
        ]

        for url in urls_to_remove:
            del self._last_403_time[url]

        if urls_to_remove:
            logger.debug(f"Cleaned up {len(urls_to_remove)} old 403 records")


# Global error handler instance
youtube_error_handler = YouTubeErrorHandler()
