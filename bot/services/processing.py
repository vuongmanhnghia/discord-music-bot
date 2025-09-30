"""
Service layer for external integrations
Clean separation of concerns with proper error handling
"""

import asyncio
import json
import re
from typing import Optional, Dict, Any

from ..domain.valueobjects.source_type import SourceType
from ..domain.entities.song import Song, SongMetadata
from ..domain.valueobjects.song_processor import SongProcessor
from ..utils.youtube_error_handler import youtube_error_handler
from .auto_recovery import auto_recovery_service
from ..pkg.logger import logger


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
        logger.info(f"Processing Spotify track: {song.original_input}")

        try:
            song.mark_processing()

            # Extract Spotify track ID
            track_id = self._extract_track_id(song.original_input)
            if not track_id:
                song.mark_failed("Invalid Spotify URL format")
                return False

            # Check cache first
            cache_key = f"spotify:{track_id}"
            if cache_key in self._cache:
                logger.debug(f"Using cached Spotify metadata: {track_id}")
                metadata = self._cache[cache_key]
                # Note: No stream URL for Spotify, will be handled by YouTube search
                song.mark_ready(metadata, "")
                return True

            # Extract metadata using yt-dlp (for metadata only)
            metadata = await self._extract_metadata(song.original_input)
            if not metadata:
                song.mark_failed("Failed to extract Spotify metadata")
                return False

            # Cache the metadata
            self._cache[cache_key] = metadata

            # Mark as ready (no stream URL yet, will be handled by YouTube search)
            song.mark_ready(metadata, "")

            logger.info(
                f"Successfully processed Spotify track: {metadata.display_name}"
            )
            return True

        except Exception as e:
            logger.error(f"Error processing Spotify track {song.original_input}: {e}")
            song.mark_failed(f"Spotify processing error: {str(e)}")
            return False

    def _extract_track_id(self, spotify_url: str) -> Optional[str]:
        """Extract Spotify track ID from URL"""
        try:
            # Input validation
            if not spotify_url or not isinstance(spotify_url, str):
                logger.warning("Invalid Spotify URL: not a string")
                return None

            # Length check to prevent DoS
            if len(spotify_url) > 500:
                logger.warning(f"Spotify URL too long: {len(spotify_url)} chars")
                return None

            # Handle different Spotify URL formats
            patterns = [
                r"spotify\.com/track/([a-zA-Z0-9]{22})",  # Exact 22 chars
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

            logger.warning(
                f"Could not extract valid Spotify track ID from: {spotify_url[:100]}"
            )
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

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

            if process.returncode != 0:
                logger.warning(f"yt-dlp failed for Spotify URL: {stderr.decode()}")
                return None

            if not stdout.strip():
                logger.warning("Empty response from yt-dlp for Spotify URL")
                return None

            # Parse JSON
            info = json.loads(stdout.decode())
            return self._parse_spotify_metadata(info)

        except asyncio.TimeoutError:
            logger.error("Timeout extracting Spotify metadata")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Spotify metadata JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error extracting Spotify metadata: {e}")
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
        logger.info(f"Processing YouTube/search: {song.original_input}")

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
                return True

            # Extract metadata and stream URL
            result = await self._extract_youtube_data(search_query)

            if result:
                metadata, stream_url = result
                self._cache[cache_key] = result
                song.mark_ready(metadata, stream_url)
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
            logger.error(f"Error processing YouTube {song.original_input}: {e}")
            song.mark_failed(f"YouTube processing error: {str(e)}")
            return False

    async def search_for_spotify_song(self, song: Song) -> bool:
        """Search YouTube for a Spotify song"""
        if not song.metadata:
            logger.error("Cannot search YouTube: Song has no metadata")
            return False

        logger.info(
            f"Searching YouTube for Spotify track: {song.metadata.display_name}"
        )

        try:
            # Create search query from metadata
            search_query = f"ytsearch1:{song.metadata.search_query}"

            # Get YouTube data
            result = await self._extract_youtube_data(search_query)
            if not result:
                song.mark_failed("Failed to find YouTube equivalent")
                return False

            metadata, stream_url = result

            # Update song with stream URL (keep original Spotify metadata)
            song.stream_url = stream_url
            song.status = song.status  # Keep current status

            logger.info(
                f"Found YouTube stream for Spotify track: {song.metadata.display_name}"
            )
            return True

        except Exception as e:
            logger.error(f"Error searching YouTube for Spotify song: {e}")
            song.mark_failed(f"YouTube search error: {str(e)}")
            return False

    async def _extract_youtube_data(
        self, query: str, max_retries: int = 3
    ) -> Optional[tuple[SongMetadata, str]]:
        """Extract both metadata and stream URL from YouTube with retries"""

        for attempt in range(max_retries):
            try:
                # Increase timeout based on attempt
                timeout = 30 + (attempt * 15)  # 30s, 45s, 60s

                # Faster metadata extraction
                metadata_cmd = [
                    "yt-dlp",
                    "--dump-json",
                    "--no-playlist",
                    "--quiet",
                    "--no-warnings",
                    "--ignore-errors",
                    "--skip-download",
                    "--no-check-certificate",  # Skip cert checks
                    "--socket-timeout",
                    "20",  # Socket timeout
                    "--fragment-retries",
                    "3",  # Retry fragments
                    "--retries",
                    "3",  # Retry requests
                    "--concurrent-fragments",
                    "1",  # Reduce concurrency
                    query,
                ]

                metadata_process = await asyncio.create_subprocess_exec(
                    *metadata_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await asyncio.wait_for(
                    metadata_process.communicate(), timeout=timeout
                )

                if metadata_process.returncode != 0:
                    logger.warning(
                        f"yt-dlp metadata extraction failed: {stderr.decode()}"
                    )
                    return None

                if not stdout.strip():
                    logger.warning("Empty metadata response from yt-dlp")
                    return None

                # Parse metadata
                info = json.loads(stdout.decode())
                metadata = self._parse_youtube_metadata(info)
                if not metadata:
                    return None

                # Get stream URL
                stream_url = await self._get_stream_url(query)
                if not stream_url:
                    logger.error("Failed to get YouTube stream URL")
                    return None

                return (metadata, stream_url)

            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout attempt {attempt + 1}/{max_retries} for: {query}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)  # exponential backoff: 1s, 2s, 4s
                    continue
                logger.error("Final timeout extracting YouTube data")
                return None
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                return None

    async def _get_stream_url(self, query: str) -> Optional[str]:
        """Extract stream URL with better format selection and 403 handling"""
        try:
            # Enhanced format selection to avoid 403 errors
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
                "30",  # Increased timeout
                "--retries",
                "5",  # More retries
                "--fragment-retries",
                "5",
                # Anti-detection measures
                "--user-agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "--extractor-args",
                "youtube:skip=hls,dash;player_client=android,web",
                query,
            ]

            # Try with retries for 403 errors
            for attempt in range(3):
                try:
                    process = await asyncio.create_subprocess_exec(
                        *stream_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )

                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), timeout=45
                    )

                    if process.returncode == 0 and stdout.strip():
                        url = stdout.decode().strip()
                        logger.info(
                            f"Successfully extracted stream URL (attempt {attempt + 1})"
                        )
                        return url

                    # Check for 403 error
                    error_msg = stderr.decode()
                    if youtube_error_handler.is_403_error(error_msg):
                        logger.warning(
                            f"403 error on attempt {attempt + 1}: {error_msg}"
                        )

                        # Try auto-recovery on first 403 error
                        if attempt == 0:
                            logger.info("🚨 Attempting auto-recovery for 403 error...")
                            recovery_success = (
                                await auto_recovery_service.check_and_recover_if_needed(
                                    error_msg
                                )
                            )

                            if recovery_success:
                                logger.info("✅ Auto-recovery completed, retrying...")
                                await asyncio.sleep(5)  # Wait a bit after recovery
                                continue

                        if attempt < 2 and youtube_error_handler.should_retry_403(
                            query, attempt
                        ):
                            # Wait before retry
                            delay = await youtube_error_handler.get_retry_delay(attempt)
                            logger.info(
                                f"Retrying in {delay} seconds with different format..."
                            )
                            await asyncio.sleep(delay)

                            # Update command with alternative format
                            alt_format = youtube_error_handler.get_alternative_format(
                                attempt + 1
                            )
                            stream_cmd[
                                stream_cmd.index(
                                    "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best"
                                )
                                - 1
                            ] = alt_format
                            continue

                    logger.error(
                        f"Failed to get stream URL (attempt {attempt + 1}): {error_msg}"
                    )

                    # Try auto-recovery on last attempt if not tried yet
                    if attempt == 2 and not youtube_error_handler.is_403_error(
                        error_msg
                    ):
                        recovery_success = (
                            await auto_recovery_service.check_and_recover_if_needed(
                                error_msg
                            )
                        )
                        if recovery_success:
                            logger.info("✅ Auto-recovery completed on final attempt")

                    if attempt == 2:  # Last attempt
                        return None

                except asyncio.TimeoutError:
                    logger.warning(
                        f"Timeout on stream URL extraction attempt {attempt + 1}"
                    )
                    if attempt == 2:
                        return None
                    await asyncio.sleep(2)

            return None

        except Exception as e:
            logger.error(f"Error extracting stream URL: {e}")
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

            return SongMetadata(
                title=title, artist=artist, duration=duration, thumbnail_url=thumbnail
            )

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
                "15",
                query,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=20)

            if process.returncode == 0 and stdout.strip():
                info = json.loads(stdout.decode())
                return self._parse_youtube_metadata(info)

            # Ultimate fallback: create basic metadata from URL
            logger.warning("Creating basic metadata from URL")
            return SongMetadata(
                title=f"YouTube Video ({query[-11:]})",  # Use video ID as title
                artist="Unknown Artist",
                duration=0,
                thumbnail_url="",
                source_url=query,
            )

        except Exception as e:
            logger.error(f"Basic info extraction failed: {e}")
            # Last resort: minimal metadata
            return SongMetadata(
                title="YouTube Video",
                artist="Unknown",
                duration=0,
                thumbnail_url="",
                source_url=query,
            )


class SongProcessingService:
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
        logger.info(f"Starting song processing: {song.original_input}")

        try:
            # Find appropriate processor
            processor = None
            for p in self._processors:
                if await p.can_process(song):
                    processor = p
                    break

            if not processor:
                logger.error(f"No processor found for song: {song.original_input}")
                song.mark_failed("Unsupported song source")
                return False

            # Process the song
            success = await processor.process(song)

            # Special handling for Spotify: need to find YouTube stream
            if (
                success
                and song.source_type == SourceType.SPOTIFY
                and not song.stream_url
            ):
                logger.info("Spotify song processed, searching for YouTube stream...")
                youtube_success = await self.youtube_service.search_for_spotify_song(
                    song
                )
                if not youtube_success:
                    logger.warning("Failed to find YouTube stream for Spotify song")
                    return False

            return success

        except Exception as e:
            logger.error(f"Unexpected error processing song {song.original_input}: {e}")
            song.mark_failed(f"Processing error: {str(e)}")
            return False
