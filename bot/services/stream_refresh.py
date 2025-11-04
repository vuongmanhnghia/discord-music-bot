"""
Stream URL refresh service for 24/7 bot operation
Handles automatic refresh of expired YouTube stream URLs
"""

import asyncio
import time
from typing import Dict, Tuple

from ..utils.youtube import YouTubeHandler

from ..domain.entities.song import Song
from ..config.service_constants import ServiceConstants
from ..pkg.logger import logger


class StreamRefreshService:
    """Service to handle automatic stream URL refresh for 24/7 operation"""

    def __init__(self):
        self.enabled = True
        self.refresh_count = 0
        self.last_refresh_time = 0
        self.url_cache: Dict[str, Tuple[str, float]] = {}  # original_input -> (stream_url, timestamp)
        self.youtube_handler = YouTubeHandler()
        self.URL_MAX_AGE = 5 * 3600  # 5 hours in seconds

    async def should_refresh_url(self, song: Song) -> bool:
        """Check if stream URL needs refresh"""
        if not song.stream_url:
            logger.info(f"🆕 No stream URL for {song.display_name}, needs refresh")
            return True

        # Check age of URL
        if hasattr(song, "stream_url_timestamp"):
            age = time.time() - song.stream_url_timestamp
            if age > self.URL_MAX_AGE:
                logger.info(f"🕐 URL expired for {song.display_name} (age: {age//60}min)")
                return True

        return False

    async def refresh_stream_url(self, song: Song) -> bool:
        """Refresh stream URL using yt-dlp (non-blocking) with smart retry"""
        try:
            logger.info(f"🔄 Refreshing stream URL for: {song.display_name}")

            # Store old URL for comparison
            old_url = song.stream_url if hasattr(song, 'stream_url') else None

            # First try: strip playlist params (faster, avoids timeout on Radio/Mix URLs)
            info = await self.youtube_handler.extract_info(
                song.original_input,
                timeout=60.0,
                strip_playlist=True  # Strip playlist/radio params for faster extraction
            )

            # Second try: if stripped version fails, try original URL with longer timeout
            if not info or "url" not in info:
                logger.warning(f"⚠️ Stripped URL failed, retrying with original URL...")
                info = await self.youtube_handler.extract_info(
                    song.original_input,
                    timeout=90.0,  # Longer timeout for full URL
                    strip_playlist=False
                )

            if not info or "url" not in info:
                logger.error(f"❌ Failed to extract new URL for: {song.display_name}")
                logger.info(f"💡 Tip: Old URL will be used as fallback (may still work temporarily)")
                return False

            # Update song with new URL
            new_url = info["url"]
            song.stream_url = new_url
            song.stream_url_timestamp = time.time()  # Track timestamp

            # Log if URL actually changed
            if old_url and old_url != new_url:
                logger.info(f"✅ URL refreshed for: {song.display_name} (URL changed)")
            else:
                logger.info(f"✅ URL refreshed for: {song.display_name} (same URL)")

            return True

        except Exception as e:
            logger.error(f"❌ Error refreshing URL for {song.display_name}: {type(e).__name__}: {e}")
            return False

    async def refresh_queue(self, queue_songs: list) -> int:
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
