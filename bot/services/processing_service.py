"""
Service layer for external integrations
Clean separation of concerns with proper error handling
"""

import asyncio
import json
import re
from typing import Optional, Dict, Any
import time
from abc import ABC, abstractmethod

from ..domain.valueobjects.source_type import SourceType
from ..config.service_constants import ServiceConstants
from ..utils.retry_strategy import RetryStrategy
from ..pkg.logger import logger

from ..domain.entities.song import Song, SongMetadata


class SongProcessor(ABC):
    """Abstract base for song processors"""

    @abstractmethod
    async def can_process(self, song: Song) -> bool:
        """Check if this processor can handle the song"""
        pass

    @abstractmethod
    async def process(self, song: Song) -> bool:
        """Process the song and update its state"""
        pass


class SpotifyService(SongProcessor):
    """
    Spotify metadata extraction service
    Extracts track information from Spotify URLs
    """

    def __init__(self):
        self._cache: Dict[str, SongMetadata] = {}

    async def can_process(self, song: Song) -> bool:
        """Check if this is a Spotify song"""
        return song.source_type == SourceType.SPOTIFY

    async def process(self, song: Song) -> bool:
        """Extract Spotify metadata"""
        try:
            song.mark_processing()

            # Extract and validate track ID
            track_id = self._extract_track_id(song.original_input)
            if not track_id:
                song.mark_failed("Invalid Spotify URL format")
                return False

            # Check cache first
            cache_key = f"spotify:{track_id}"
            if cache_key in self._cache:
                metadata = self._cache[cache_key]
                song.mark_ready(metadata, "")
                return True

            # Extract metadata using yt-dlp
            metadata = await self._extract_metadata(song.original_input)
            if not metadata:
                song.mark_failed("Failed to extract Spotify metadata")
                return False

            # Cache and mark ready
            self._cache[cache_key] = metadata
            song.mark_ready(metadata, "")

            return True

        except Exception as e:
            logger.error(f"Spotify processing failed: {e}")
            song.mark_failed(f"Spotify error: {str(e)}")
            return False

    def _extract_track_id(self, spotify_url: str) -> Optional[str]:
        """Extract Spotify track ID from URL"""
        try:
            # Input validation
            if not spotify_url or not isinstance(spotify_url, str):
                return None

            # Length check to prevent DoS
            if len(spotify_url) > 500:
                return None

            # Handle different Spotify URL formats
            patterns = [
                r"spotify\.com/track/([a-zA-Z0-9]{22})",
                r"open\.spotify\.com/track/([a-zA-Z0-9]{22})",
                r"spotify:track:([a-zA-Z0-9]{22})",
            ]

            for pattern in patterns:
                match = re.search(pattern, spotify_url)
                if match:
                    track_id = match.group(1)
                    # Validate track ID format (Spotify IDs are 22 chars)
                    if len(track_id) == 22 and track_id.isalnum():
                        return track_id

            return None

        except Exception as e:
            logger.error(f"Error extracting Spotify track ID: {e}")
            return None

    async def _extract_metadata(self, spotify_url: str) -> Optional[SongMetadata]:
        """Extract metadata using yt-dlp"""
        try:
            cmd = [
                "yt-dlp",
                "--dump-json",
                "--no-playlist",
                "--quiet",
                "--no-warnings",
                "--ignore-errors",
                "--skip-download",
                spotify_url,
            ]

            process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

            if process.returncode != 0 or not stdout.strip():
                return None

            # Parse JSON and return metadata
            info = json.loads(stdout.decode())
            return self._parse_spotify_metadata(info)

        except (asyncio.TimeoutError, json.JSONDecodeError, Exception) as e:
            logger.error(f"Spotify metadata extraction failed: {e}")
            return None

    def _parse_spotify_metadata(self, info: Dict[str, Any]) -> Optional[SongMetadata]:
        """Parse Spotify metadata from yt-dlp info"""
        try:
            title = info.get("title", "")
            artist = info.get("uploader", info.get("creator", ""))
            duration = int(info.get("duration", 0) or 0)
            album = info.get("album", "")
            thumbnail = info.get("thumbnail", "")

            if not title:
                logger.warning("Missing title in Spotify metadata")
                return None

            return SongMetadata(
                title=title,
                artist=artist,
                duration=duration,
                album=album,
                thumbnail_url=thumbnail,
            )

        except Exception as e:
            logger.error(f"Error parsing Spotify metadata: {e}")
            return None


class YouTubeService(SongProcessor):
    """
    YouTube processing service
    Handles YouTube URLs and search queries
    """

    def __init__(self):
        self._cache: Dict[str, tuple[SongMetadata, str]] = {}

    async def can_process(self, song: Song) -> bool:
        """Check if this is a YouTube song or search query"""
        return song.source_type in [SourceType.YOUTUBE, SourceType.SEARCH_QUERY]

    async def process(self, song: Song) -> bool:
        """Process YouTube URL or search query"""
        logger.info(f"⏳ Processing YouTube/search: {song.original_input}")

        try:
            song.mark_processing()

            # Prepare search query
            if song.source_type == SourceType.SEARCH_QUERY:
                search_query = f"ytsearch1:{song.original_input}"
            else:
                search_query = song.original_input

            # Check cache
            cache_key = f"youtube:{hash(search_query)}"
            if cache_key in self._cache:
                logger.debug(f"Using cached YouTube data: {song.original_input}")
                metadata, stream_url = self._cache[cache_key]
                song.mark_ready(metadata, stream_url)

                # Set stream URL timestamp for cached items too
                import time

                song.stream_url_timestamp = time.time()
                return True

            # Extract metadata and stream URL
            result = await self._extract_youtube_data(search_query)

            if result:
                metadata, stream_url = result
                self._cache[cache_key] = result
                song.mark_ready(metadata, stream_url)

                # Set stream URL timestamp for refresh tracking
                import time

                song.stream_url_timestamp = time.time()
                return True

            # Fallback: Basic info extraction
            logger.warning("Full extraction failed, trying basic extraction...")
            basic_result = await self._extract_basic_info(search_query)

            if basic_result:
                song.mark_ready(basic_result, "")  # No stream URL yet
                return True

            song.mark_failed("Failed to extract YouTube data")
            return False

        except Exception as e:
            import traceback

            logger.error(f"Error processing YouTube {song.original_input}: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            song.mark_failed(f"YouTube processing error: {str(e)}")
            return False

    async def search_for_spotify_song(self, song: Song) -> bool:
        """Search YouTube for a Spotify song"""
        if not song.metadata:
            logger.error("Cannot search YouTube: Song has no metadata")
            return False

        try:
            search_query = f"ytsearch1:{song.metadata.search_query}"
            result = await self._extract_youtube_data(search_query)

            if not result:
                song.mark_failed("Failed to find YouTube equivalent")
                return False

            metadata, stream_url = result
            song.stream_url = stream_url
            song.status = song.status

            song.stream_url_timestamp = time.time()

            return True

        except Exception as e:
            logger.error(f"Error searching YouTube for Spotify song: {e}")
            song.mark_failed(f"YouTube search error: {str(e)}")
            return False

    async def _extract_youtube_data(self, query: str, max_retries: int = 3) -> Optional[tuple[SongMetadata, str]]:
        """Extract both metadata and stream URL from YouTube with retries"""

        async def _extract() -> tuple[SongMetadata, str]:
            timeout = ServiceConstants.YOUTUBE_EXTRACT_TIMEOUT_BASE

            metadata_cmd = [
                "yt-dlp",
                "--dump-json",
                "--no-playlist",
                "--quiet",
                "--no-warnings",
                "--ignore-errors",
                "--skip-download",
                "--no-check-certificate",
                "--socket-timeout",
                "30",  # Increased from 20
                "--fragment-retries",
                "5",  # Increased from 3
                "--retries",
                "5",  # Increased from 3
                "--concurrent-fragments",
                "2",  # Increased from 1 for faster download
                "--sleep-requests",
                "1",  # 1 second delay between requests to avoid rate limit
                "--extractor-retries",
                "3",  # Retry extractor on failure
                query,
            ]

            process = await asyncio.create_subprocess_exec(
                *metadata_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)

            if process.returncode != 0 or not stdout.strip():
                raise Exception(f"Extraction failed: {stderr.decode()}")

            info = json.loads(stdout.decode())
            metadata = self._parse_youtube_metadata(info)
            if not metadata:
                raise Exception("Failed to parse metadata")

            stream_url = await self._get_stream_url(query)
            if not stream_url:
                raise Exception("Failed to get stream URL")

            return (metadata, stream_url)

        retry_strategy = RetryStrategy(max_attempts=max_retries, base_delay=1.0, backoff_factor=2.0, timeout=ServiceConstants.YOUTUBE_EXTRACT_TIMEOUT_BASE)

        try:
            return await retry_strategy.execute(_extract, "Extract YouTube data")
        except Exception as e:
            logger.error(f"YouTube data extraction failed: {e}")
            return None

    async def _get_stream_url(self, query: str) -> Optional[str]:
        """Extract stream URL with 403 handling"""

        async def _extract_url() -> str:
            stream_cmd = [
                "yt-dlp",
                "--get-url",
                "--no-playlist",
                "--quiet",
                "--no-warnings",
                "--format",
                "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
                "--no-check-certificate",
                "--socket-timeout",
                "30",
                "--retries",
                "5",
                "--fragment-retries",
                "5",
                "--sleep-requests",
                "1",  # Add delay between requests
                "--extractor-retries",
                "3",  # Retry extractor on failure
                "--user-agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "--extractor-args",
                "youtube:skip=hls,dash;player_client=android,web",
                query,
            ]

            process = await asyncio.create_subprocess_exec(
                *stream_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=ServiceConstants.YOUTUBE_STREAM_TIMEOUT)

            if process.returncode == 0 and stdout.strip():
                return stdout.decode().strip()

            error_msg = stderr.decode()

            # Try auto-recovery on 403 errors (only on first attempt)
            # if youtube_error_handler.is_403_error(error_msg):
            #     await auto_recovery_service.check_and_recover_if_needed(error_msg)
            #     await asyncio.sleep(ServiceConstants.STREAM_REFRESH_RETRY_DELAY)

            raise Exception(f"Stream URL extraction failed: {error_msg}")

        retry_strategy = RetryStrategy(
            max_attempts=3,
            base_delay=2.0,
            backoff_factor=1.5,
            timeout=ServiceConstants.YOUTUBE_STREAM_TIMEOUT,
        )

        try:
            return await retry_strategy.execute(_extract_url, "Get stream URL")
        except Exception as e:
            logger.error(f"Failed to extract stream URL: {e}")
            return None

    def _parse_youtube_metadata(self, info: Dict[str, Any]) -> Optional[SongMetadata]:
        """Parse YouTube metadata from yt-dlp info"""
        try:
            title = info.get("title", "")
            uploader = info.get("uploader", info.get("channel", ""))
            duration = int(info.get("duration", 0) or 0)
            thumbnail = info.get("thumbnail", "")

            if not title:
                logger.warning("Missing title in YouTube metadata")
                return None

            # Try to extract artist from title (common format: "Artist - Title")
            artist = uploader
            if " - " in title:
                parts = title.split(" - ", 1)
                if len(parts) == 2:
                    artist = parts[0].strip()
                    title = parts[1].strip()

            return SongMetadata(title=title, artist=artist, duration=duration, thumbnail_url=thumbnail)

        except Exception as e:
            logger.error(f"Error parsing YouTube metadata: {e}")
            return None

    async def _extract_basic_info(self, query: str) -> Optional[SongMetadata]:
        """Fallback: Extract basic info when full extraction fails"""
        try:
            # Simplified extraction with basic format
            cmd = [
                "yt-dlp",
                "--dump-json",
                "--no-playlist",
                "--quiet",
                "--no-warnings",
                "--ignore-errors",
                "--skip-download",
                "--format",
                "worst",  # Use worst quality for basic info
                "--socket-timeout",
                "20",  # Increased from 15
                "--retries",
                "3",
                "--sleep-requests",
                "1",  # Add delay
                query,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=ServiceConstants.BASIC_INFO_TIMEOUT,  # Use config constant (30s)
                )
            except asyncio.TimeoutError:
                logger.error(f"Basic info extraction timeout after {ServiceConstants.BASIC_INFO_TIMEOUT}s for {query}")
                process.kill()
                raise

            if stderr:
                stderr_text = stderr.decode().strip()
                if stderr_text:
                    logger.warning(f"yt-dlp stderr: {stderr_text[:200]}")

            if process.returncode == 0 and stdout.strip():
                try:
                    info = json.loads(stdout.decode())
                    metadata = self._parse_youtube_metadata(info)
                    if metadata:
                        return metadata
                except json.JSONDecodeError as je:
                    logger.error(f"JSON decode error: {je}. Output: {stdout.decode()[:200]}")

            # Ultimate fallback: create basic metadata from URL
            logger.warning(f"Creating basic metadata from URL: {query}")
            # Extract video ID from URL
            video_id = query
            if "youtube.com" in query or "youtu.be" in query:
                import re

                match = re.search(r"(?:v=|/)([a-zA-Z0-9_-]{11})", query)
                if match:
                    video_id = match.group(1)

            return SongMetadata(
                title=f"YouTube Video {video_id}",
                artist="Unknown Artist",
                duration=0,
                thumbnail_url="",
            )

        except asyncio.TimeoutError:
            logger.error(f"Basic info extraction timeout for: {query}")
            # Return minimal metadata instead of None
            return SongMetadata(
                title="YouTube Video (Timeout)",
                artist="Unknown",
                duration=0,
                thumbnail_url="",
            )
        except Exception as e:
            import traceback

            error_msg = str(e) if str(e) else type(e).__name__
            logger.error(f"Basic info extraction failed: {error_msg}")
            logger.error(f"Query: {query}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Last resort: minimal metadata
            return SongMetadata(
                title="YouTube Video (Error)",
                artist="Unknown",
                duration=0,
                thumbnail_url="",
            )


class ProcessingService:
    """
    Main service for processing songs
    Orchestrates different processors based on song type
    """

    def __init__(self):
        self.spotify_service = SpotifyService()
        self.youtube_service = YouTubeService()
        self._processors = [self.spotify_service, self.youtube_service]

    async def process_song(self, song: Song) -> bool:
        """Process a song using appropriate processor"""
        try:
            # Find and use appropriate processor
            processor = None
            for p in self._processors:
                if await p.can_process(song):
                    processor = p
                    break

            if not processor:
                logger.error(f"No processor found for: {song.original_input}")
                song.mark_failed("Unsupported song source")
                return False

            success = await processor.process(song)

            # Spotify songs need YouTube stream URL
            if success and song.source_type == SourceType.SPOTIFY and not song.stream_url:
                return await self.youtube_service.search_for_spotify_song(song)

            return success

        except Exception as e:
            import traceback

            logger.error(f"Error processing {song.original_input}: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            song.mark_failed(f"Processing error: {str(e)}")
            return False
