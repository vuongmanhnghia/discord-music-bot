"""
Stream URL refresh service for 24/7 bot operation
Handles automatic refresh of expired YouTube stream URLs
"""

import asyncio
import time
from typing import Optional, Dict, Tuple
import logging

from ..domain.entities.song import Song
from ..pkg.logger import logger
from ..config.constants import STREAM_URL_REFRESH_INTERVAL, STREAM_URL_MAX_AGE


class StreamRefreshService:
    """Service to handle automatic stream URL refresh for 24/7 operation"""

    def __init__(self):
        self.enabled = True
        self.refresh_count = 0
        self.last_refresh_time = 0
        self.url_cache: Dict[str, Tuple[str, float]] = (
            {}
        )  # original_input -> (stream_url, timestamp)

    async def should_refresh_url(self, song: Song) -> bool:
        """Check if stream URL should be refreshed"""
        if not self.enabled or not song.stream_url:
            return False

        # Check if URL is older than max age (default 5 hours to be safe)
        if hasattr(song, "stream_url_timestamp") and song.stream_url_timestamp is not None:
            age = time.time() - song.stream_url_timestamp
            if age > STREAM_URL_MAX_AGE:
                logger.info(
                    f"🔄 Stream URL for '{song.display_name}' is {age/3600:.1f} hours old, needs refresh"
                )
                return True

        return False

    async def refresh_stream_url(self, song: Song) -> bool:
        """Refresh stream URL for a song"""
        try:
            if not song.original_input:
                return False

            # Import here to avoid circular imports
            from ..services.processing import YouTubeService

            # Create new processor instance for refresh
            processor = YouTubeService()

            # Get fresh stream URL
            logger.info(f"🔄 Refreshing stream URL for: {song.display_name}")
            new_stream_url = await processor._get_stream_url(song.original_input)

            if new_stream_url:
                # Update song with new URL
                old_url = song.stream_url
                song.stream_url = new_stream_url
                song.stream_url_timestamp = time.time()

                # Update cache
                self.url_cache[song.original_input] = (new_stream_url, time.time())

                self.refresh_count += 1
                self.last_refresh_time = time.time()

                logger.info(
                    f"✅ Stream URL refreshed for '{song.display_name}' (#{self.refresh_count})"
                )
                logger.debug(f"Old URL: {old_url[:50]}...")
                logger.debug(f"New URL: {new_stream_url[:50]}...")

                return True
            else:
                logger.error(
                    f"❌ Failed to refresh stream URL for '{song.display_name}'"
                )
                return False

        except Exception as e:
            logger.error(
                f"❌ Error refreshing stream URL for '{song.display_name}': {e}"
            )
            return False

    async def refresh_current_song_if_needed(self, song: Song) -> bool:
        """Refresh current playing song if needed"""
        if await self.should_refresh_url(song):
            return await self.refresh_stream_url(song)
        return False

    async def preemptive_refresh_queue(self, queue_songs: list) -> int:
        """Preemptively refresh URLs in queue that will expire soon"""
        refreshed_count = 0

        for song in queue_songs:
            if await self.should_refresh_url(song):
                success = await self.refresh_stream_url(song)
                if success:
                    refreshed_count += 1
                    # Small delay to avoid rate limiting
                    await asyncio.sleep(2)

        return refreshed_count

    def get_refresh_stats(self) -> dict:
        """Get refresh statistics"""
        current_time = time.time()

        return {
            "enabled": self.enabled,
            "refresh_count": self.refresh_count,
            "last_refresh_time": self.last_refresh_time,
            "cached_urls": len(self.url_cache),
            "time_since_last_refresh": (
                current_time - self.last_refresh_time
                if self.last_refresh_time > 0
                else 0
            ),
        }

    def enable_refresh(self):
        """Enable stream URL refresh"""
        self.enabled = True
        logger.info("🔄 Stream URL refresh enabled")

    def disable_refresh(self):
        """Disable stream URL refresh"""
        self.enabled = False
        logger.info("🔒 Stream URL refresh disabled")

    def clear_cache(self):
        """Clear URL cache"""
        self.url_cache.clear()
        logger.info("🧹 Stream URL cache cleared")


# Global service instance
stream_refresh_service = StreamRefreshService()
