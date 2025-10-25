"""YouTube service with integrated smart caching"""

import asyncio
import time
from typing import Tuple, TYPE_CHECKING
import yt_dlp

from ..utils.cache import SmartCache

from ..domain.entities.song import Song
from ..domain.valueobjects.source_type import SourceType
from ..domain.valueobjects.song_metadata import SongMetadata
from ..config.performance import performance_config
from ..pkg.logger import logger


class YouTubeService:
    """YouTube service with integrated smart caching and song processing"""

    def __init__(self):
        self.config = performance_config

        # Integrated SmartCache
        self.cache = SmartCache(
            cache_dir="cache/songs",
            max_size=self.config.cache_size,
            ttl=self.config.cache_duration_minutes * 60,
            persist=True,
        )

        self.yt_dlp_opts = self.config.get_ytdl_opts()
        self._stats = {"hits": 0, "misses": 0, "total": 0}

    async def get_song_info(self, url: str) -> Tuple[dict, bool]:
        """
        Get song info with caching
        Returns:
            (song_data, was_cached) tuple
        """
        try:
            song_data, was_cached = await self.cache.get_or_process(url, self._extract_info)

            # Update stats
            self._stats["total"] += 1
            if was_cached:
                self._stats["hits"] += 1
            else:
                self._stats["misses"] += 1

            return song_data, was_cached

        except Exception as e:
            logger.error(f"Failed to get song info for {url}: {e}")
            raise

    async def _extract_info(self, url: str) -> dict:
        """Extract song info using yt-dlp"""
        loop = asyncio.get_event_loop()

        def extract():
            with yt_dlp.YoutubeDL(self.yt_dlp_opts) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            info = await loop.run_in_executor(None, extract)

            if not info:
                raise ValueError(f"No info extracted from {url}")

            # Return minimal required data
            return {
                "url": url,
                "title": info.get("title", "Unknown"),
                "duration": info.get("duration", 0),
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get("uploader", "Unknown"),
                "stream_url": self._get_best_audio_url(info),
                "source_type": self._detect_source(url),
                "extracted_at": time.time(),
            }

        except Exception as e:
            logger.error(f"yt-dlp extraction failed for {url}: {e}")
            raise

    def _get_best_audio_url(self, info: dict) -> str:
        """Get best audio stream URL"""
        formats = info.get("formats", [])
        audio_formats = [f for f in formats if f.get("acodec") != "none"]

        if audio_formats:
            # Get best quality audio
            best = max(audio_formats, key=lambda x: x.get("abr", 0) or 0)
            return best.get("url", "")

        # Fallback to first format
        if formats:
            return formats[0].get("url", "")

        return info.get("url", "")

    @staticmethod
    def _detect_source(url: str) -> str:
        """Detect source type from URL"""
        if "youtube.com" in url or "youtu.be" in url:
            return SourceType.YOUTUBE.value
        elif "spotify.com" in url:
            return SourceType.SPOTIFY.value
        elif "soundcloud.com" in url:
            return SourceType.SOUNDCLOUD.value
        return SourceType.UNKNOWN.value

    async def create_song(self, url: str, requested_by: str, guild_id: int) -> Tuple[Song, bool]:
        """
        Create Song object from URL with caching

        Returns:
            (song, was_cached) tuple
        """
        try:
            # Get song info with caching
            song_data, was_cached = await self.get_song_info(url)

            # Create metadata
            metadata = SongMetadata(
                title=song_data["title"],
                artist=song_data.get("uploader", "Unknown"),
                duration=song_data["duration"],
                thumbnail_url=song_data.get("thumbnail"),
                release_date=song_data.get("upload_date"),
            )

            # Determine source type
            try:
                source_type = SourceType(song_data.get("source_type", "youtube"))
            except ValueError:
                source_type = SourceType.YOUTUBE

            # Create Song object
            song = Song(
                original_input=url,
                source_type=source_type,
                requested_by=requested_by,
                guild_id=guild_id,
            )

            # Mark as ready
            song.mark_ready(metadata, song_data.get("stream_url", ""))

            return song, was_cached

        except Exception as e:
            logger.error(f"Failed to create song from {url}: {e}")
            raise

    def get_stats(self) -> dict:
        """Get service statistics"""
        total = self._stats["total"]
        hits = self._stats["hits"]
        hit_rate = (hits / total * 100) if total > 0 else 0

        cache_stats = self.cache.get_stats()

        return {
            "hit_rate": f"{hit_rate:.1f}%",
            "total_requests": total,
            "cache_hits": hits,
            "cache_misses": self._stats["misses"],
            **cache_stats,
        }

    async def cleanup(self) -> int:
        """Cleanup expired cache entries"""
        return await self.cache.cleanup_expired()

    async def shutdown(self):
        """Shutdown service"""
        await self.cache.shutdown()


# Global instance
youtube_service = YouTubeService()
