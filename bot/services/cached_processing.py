"""
Enhanced Song Processing Service with Smart Caching
Provides intelligent caching and faster song processing
"""

import asyncio
import time
from typing import Dict, Any, Optional, Tuple
import yt_dlp
import json

from ..utils.smart_cache import SmartCache
from ..domain.valueobjects.source_type import SourceType
from ..domain.entities.song import Song, SongMetadata
from ..pkg.logger import logger


class CachedSongProcessor:
    """
    Enhanced song processor with intelligent caching
    Provides instant responses for cached songs and optimized processing
    """

    def __init__(self, cache_dir: str = "cache/songs"):
        # Initialize SmartCache
        self.smart_cache = SmartCache(
            cache_dir=cache_dir,
            max_size=1000,  # Cache up to 1000 songs
            ttl=7200,  # 2 hour TTL
            persist=True,  # Survive restarts
        )

        # YT-DLP configuration for processing
        self.yt_dlp_opts = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "extractaudio": True,
            "audioformat": "mp3",
            "audioquality": "192K",
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        # Statistics tracking
        self._processing_stats = {
            "total_processed": 0,
            "cache_hits": 0,
            "processing_time_saved": 0.0,
            "average_processing_time": 0.0,
        }

        logger.info("🚄 CachedSongProcessor initialized with SmartCache")

    async def process_song(
        self, url: str, source_type: SourceType = None
    ) -> Tuple[dict, bool]:
        """
        Process song with smart caching
        Returns: (song_data, was_cached)
        """
        start_time = time.time()

        try:
            # Use SmartCache's get_or_process method
            song_data, was_cached = await self.smart_cache.get_or_process(
                url, self._extract_song_info
            )

            processing_time = time.time() - start_time

            # Update statistics
            self._processing_stats["total_processed"] += 1
            if was_cached:
                self._processing_stats["cache_hits"] += 1
                self._processing_stats["processing_time_saved"] += processing_time
                logger.info(
                    f"⚡ Cache hit: {song_data.get('title', 'Unknown')} ({processing_time:.2f}s saved)"
                )
            else:
                # Update average processing time for non-cached items
                self._update_average_processing_time(processing_time)
                logger.info(
                    f"🔄 Processed: {song_data.get('title', 'Unknown')} ({processing_time:.2f}s)"
                )

            return song_data, was_cached

        except Exception as e:
            logger.error(f"Error processing song {url}: {e}")
            raise

    async def _extract_song_info(self, url: str) -> dict:
        """Extract song information using yt-dlp"""
        try:
            # Use asyncio to run yt-dlp in thread pool to avoid blocking
            loop = asyncio.get_event_loop()

            def extract_info():
                with yt_dlp.YoutubeDL(self.yt_dlp_opts) as ydl:
                    return ydl.extract_info(url, download=False)

            info = await loop.run_in_executor(None, extract_info)

            if not info:
                raise ValueError("No information extracted from URL")

            # Extract relevant data
            song_data = {
                "url": url,
                "title": info.get("title", "Unknown Title"),
                "duration": info.get("duration", 0),
                "thumbnail": info.get("thumbnail", ""),
                "source_type": self._detect_source_type(url),
                "uploader": info.get("uploader", ""),
                "view_count": info.get("view_count", 0),
                "upload_date": info.get("upload_date", ""),
                "stream_url": self._get_best_stream_url(info),
                "extracted_at": time.time(),
            }

            return song_data

        except Exception as e:
            logger.error(f"Failed to extract info for {url}: {e}")
            raise

    def _detect_source_type(self, url: str) -> str:
        """Detect source type from URL"""
        if "youtube.com" in url or "youtu.be" in url:
            return SourceType.YOUTUBE.value
        elif "spotify.com" in url:
            return SourceType.SPOTIFY.value
        elif "soundcloud.com" in url:
            return SourceType.SOUNDCLOUD.value
        else:
            return SourceType.UNKNOWN.value

    def _get_best_stream_url(self, info: dict) -> str:
        """Extract best quality stream URL"""
        formats = info.get("formats", [])
        if not formats:
            return info.get("url", "")

        # Find best audio format
        audio_formats = [f for f in formats if f.get("acodec") != "none"]
        if audio_formats:
            # Sort by audio bitrate, prefer higher quality
            best_audio = max(audio_formats, key=lambda x: x.get("abr", 0) or 0)
            return best_audio.get("url", "")

        # Fallback to first available format
        return formats[0].get("url", "")

    def _update_average_processing_time(self, processing_time: float):
        """Update running average of processing times"""
        current_avg = self._processing_stats["average_processing_time"]
        total_processed = self._processing_stats["total_processed"]
        non_cached = total_processed - self._processing_stats["cache_hits"]

        if non_cached > 0:
            self._processing_stats["average_processing_time"] = (
                current_avg * (non_cached - 1) + processing_time
            ) / non_cached

    async def batch_process(self, urls: list, max_concurrent: int = 3) -> list:
        """Process multiple songs concurrently with rate limiting"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_semaphore(url):
            async with semaphore:
                try:
                    return await self.process_song(url)
                except Exception as e:
                    logger.error(f"Failed to process {url}: {e}")
                    return None, False

        # Process all URLs concurrently
        results = await asyncio.gather(*[process_with_semaphore(url) for url in urls])

        # Filter out failed results
        successful_results = [r for r in results if r[0] is not None]

        logger.info(f"Batch processed {len(successful_results)}/{len(urls)} songs")
        return successful_results

    async def warm_popular_cache(self) -> int:
        """Warm cache with popular songs"""
        popular_urls = self.smart_cache.get_popular_urls(limit=20)

        if not popular_urls:
            logger.info("No popular URLs to warm cache with")
            return 0

        urls_to_warm = [
            url for url, count in popular_urls if count > 2
        ]  # Only URLs accessed more than twice

        if urls_to_warm:
            warmed_count = await self.smart_cache.warm_cache(
                urls_to_warm, self._extract_song_info
            )
            logger.info(f"🔥 Cache warmed with {warmed_count} popular songs")
            return warmed_count

        return 0

    async def create_song_from_data(
        self, song_data: dict, requested_by: str, guild_id: int
    ) -> Song:
        """Create Song object from processed data"""
        # Create metadata
        metadata = SongMetadata(
            title=song_data["title"],
            duration=song_data["duration"],
            thumbnail=song_data["thumbnail"],
            uploader=song_data.get("uploader", ""),
            upload_date=song_data.get("upload_date", ""),
        )

        # Determine source type
        source_type_str = song_data.get("source_type", "UNKNOWN")
        source_type = (
            SourceType(source_type_str)
            if source_type_str in SourceType._value2member_map_
            else SourceType.UNKNOWN
        )

        # Create song
        song = Song(
            original_input=song_data["url"],
            source_type=source_type,
            requested_by=requested_by,
            guild_id=guild_id,
        )

        # Set as ready with metadata and stream URL
        song.mark_ready(metadata, song_data.get("stream_url", ""))

        return song

    async def get_cache_stats(self) -> dict:
        """Get comprehensive caching statistics"""
        cache_stats = self.smart_cache.get_stats()

        # Combine with processing stats
        combined_stats = {
            **cache_stats,
            **self._processing_stats,
            "efficiency_ratio": self._processing_stats["cache_hits"]
            / max(self._processing_stats["total_processed"], 1)
            * 100,
        }

        return combined_stats

    async def cleanup_cache(self) -> dict:
        """Perform cache cleanup and return statistics"""
        expired_count = await self.smart_cache.cleanup_expired()

        cleanup_stats = {
            "expired_entries_removed": expired_count,
            "current_cache_size": len(self.smart_cache._cache),
            "cleanup_performed_at": time.time(),
        }

        logger.info(f"🧹 Cache cleanup: removed {expired_count} expired entries")
        return cleanup_stats

    async def clear_all_cache(self) -> int:
        """Clear all cached data"""
        cleared_count = await self.smart_cache.clear_cache()

        # Reset processing stats
        self._processing_stats = {
            "total_processed": 0,
            "cache_hits": 0,
            "processing_time_saved": 0.0,
            "average_processing_time": 0.0,
        }

        logger.info(f"🗑️ Cleared all cache: {cleared_count} entries removed")
        return cleared_count

    async def shutdown(self):
        """Clean shutdown of processor"""
        logger.info("🛑 CachedSongProcessor shutting down...")
        await self.smart_cache.shutdown()
        logger.info("✅ CachedSongProcessor shutdown complete")
