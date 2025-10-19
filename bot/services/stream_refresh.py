"""
Stream URL refresh service for 24/7 bot operation
Handles automatic refresh of expired YouTube stream URLs
"""

import asyncio
import time
from typing import Dict, Tuple

from ..utils.youtube import YouTubePlaylistHandler
from ..domain.entities.song import Song
from ..config.constants import STREAM_URL_MAX_AGE
from ..config.service_constants import ServiceConstants
from ..pkg.logger import logger


class StreamRefreshService:
    """Service to handle automatic stream URL refresh for 24/7 operation"""

    def __init__(self):
        self.enabled = True
        self.refresh_count = 0
        self.last_refresh_time = 0
        self.url_cache: Dict[str, Tuple[str, float]] = (
            {}
        )  # original_input -> (stream_url, timestamp)
        self.youtube_handler = YouTubePlaylistHandler()
        self.URL_MAX_AGE = 5 * 3600  # 5 hours in seconds

    async def should_refresh_url(self, song: Song) -> bool:
        """Check if stream URL needs refresh"""
        if not song.stream_url:
            return True

        # Check age of URL
        if hasattr(song, "stream_url_timestamp"):
            age = time.time() - song.stream_url_timestamp
            if age > self.URL_MAX_AGE:
                logger.info(
                    f"🕐 URL expired for {song.display_name} (age: {age//60}min)"
                )
                return True

        return False

    async def refresh_stream_url(self, song: Song) -> bool:
        """Refresh stream URL using yt-dlp"""
        try:
            logger.info(f"🔄 Refreshing stream URL for: {song.display_name}")

            # Re-extract info
            info = await self.youtube_handler.extract_info(song.original_input)
            if not info or "url" not in info:
                logger.error(f"❌ Failed to extract new URL for: {song.display_name}")
                return False

            # Update song with new URL
            old_url = song.stream_url
            song.stream_url = info["url"]
            song.stream_url_timestamp = time.time()  # ✅ Track timestamp

            logger.info(f"✅ URL refreshed for: {song.display_name}")
            logger.debug(f"Old URL: {old_url[:100]}...")
            logger.debug(f"New URL: {song.stream_url[:100]}...")

            return True

        except Exception as e:
            logger.error(f"❌ Error refreshing URL for {song.display_name}: {e}")
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
                    await asyncio.sleep(ServiceConstants.STREAM_REFRESH_DELAY)

        return refreshed_count

    def enable_refresh(self):
        """Enable stream URL refresh"""
        self.enabled = True

    def disable_refresh(self):
        """Disable stream URL refresh"""
        self.enabled = False

    def clear_cache(self):
        """Clear URL cache"""
        self.url_cache.clear()


# Global service instance
stream_refresh_service = StreamRefreshService()
