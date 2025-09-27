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
            # Handle different Spotify URL formats
            patterns = [
                r"spotify\.com/track/([a-zA-Z0-9]+)",
                r"open\.spotify\.com/track/([a-zA-Z0-9]+)",
                r"spotify:track:([a-zA-Z0-9]+)",
            ]

            for pattern in patterns:
                match = re.search(pattern, spotify_url)
                if match:
                    return match.group(1)

            logger.warning(f"Could not extract Spotify track ID from: {spotify_url}")
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
            if not result:
                song.mark_failed("Failed to extract YouTube data")
                return False

            metadata, stream_url = result

            # Cache the result
            self._cache[cache_key] = result

            # Mark as ready
            song.mark_ready(metadata, stream_url)

            logger.info(f"Successfully processed YouTube: {metadata.display_name}")
            return True

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
        self, query: str
    ) -> Optional[tuple[SongMetadata, str]]:
        """Extract both metadata and stream URL from YouTube"""
        try:
            # First get metadata
            metadata_cmd = [
                "yt-dlp",
                "--dump-json",
                "--no-playlist",
                "--quiet",
                "--no-warnings",
                "--ignore-errors",
                "--skip-download",
                query,
            ]

            metadata_process = await asyncio.create_subprocess_exec(
                *metadata_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                metadata_process.communicate(), timeout=30
            )

            if metadata_process.returncode != 0:
                logger.warning(f"yt-dlp metadata extraction failed: {stderr.decode()}")
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
            logger.error("Timeout extracting YouTube data")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse YouTube metadata JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error extracting YouTube data: {e}")
            return None

    async def _get_stream_url(self, query: str) -> Optional[str]:
        """Get direct stream URL from YouTube optimized for Discord"""
        try:
            # Try with specific format for better compatibility
            cmd = [
                "yt-dlp",
                "--get-url",
                "--format",
                "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
                "--no-playlist",
                "--no-check-certificate",
                "--quiet",
                "--no-warnings",
                "--user-agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                query,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

            if process.returncode != 0:
                logger.error(f"Failed to get stream URL: {stderr.decode()}")
                return None

            stream_url = stdout.decode().strip()
            if stream_url:
                logger.debug("Successfully obtained YouTube stream URL")
                return stream_url

            return None

        except asyncio.TimeoutError:
            logger.error("Timeout getting YouTube stream URL")
            return None
        except Exception as e:
            logger.error(f"Error getting YouTube stream URL: {e}")
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
