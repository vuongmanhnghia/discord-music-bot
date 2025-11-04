"""YouTube utilities - Playlist handling and error management"""

import re
import logging
import asyncio
import yt_dlp
from typing import List, Optional, Tuple, Dict, Any
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


class YouTubeHandler:
    """YouTube playlist URL processing and extraction"""

    @staticmethod
    def _extract_info_sync(url: str) -> Optional[Dict[str, Any]]:
        """
        Synchronous version of extract_info - to be run in executor
        Input: YouTube playlist URL
        Extract playlist information and video URLs
        Output: (id, title, entries,...)
        """
        try:
            ydl_opts = {
                "format": "bestaudio/best",
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "default_search": "auto",
                "socket_timeout": 30,  # Add timeout to prevent hanging
                "nocheckcertificate": True,  # Skip SSL certificate verification
                "ignoreerrors": False,  # Don't ignore errors
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                # Verify we got valid info
                if not info:
                    logger.error(f"yt-dlp returned None for {url}")
                    return None

                # Check if we have a valid stream URL
                if "url" not in info and "formats" not in info:
                    logger.error(f"No stream URL or formats in extracted info for {url}")
                    return None

                return info
        except ImportError:
            logger.error("yt-dlp not available for YouTube extraction")
            return None
        except yt_dlp.DownloadError as e:
            # Bắt lỗi cụ thể từ yt-dlp
            error_msg = str(e).lower()
            if "video unavailable" in error_msg or "private video" in error_msg:
                logger.error(f"Video unavailable or private: {url}")
            elif "429" in error_msg or "too many requests" in error_msg:
                logger.error(f"Rate limited by YouTube for {url}")
            else:
                logger.error(f"yt-dlp DownloadError for {url}: {e}")
            return None
        except Exception as e:
            # Bắt các lỗi không mong muốn khác
            logger.error(f"Unexpected error extracting info from {url}: {type(e).__name__}: {e}")
            return None

    @staticmethod
    def strip_playlist_params(url: str) -> str:
        """
        Strip playlist/radio parameters from YouTube URL to get clean video URL
        Converts: https://www.youtube.com/watch?v=VIDEO_ID&list=RD...
        To: https://www.youtube.com/watch?v=VIDEO_ID
        """
        try:
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

            parsed = urlparse(url)
            if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
                query_params = parse_qs(parsed.query)

                # Keep only video ID parameter
                if 'v' in query_params:
                    clean_query = urlencode({'v': query_params['v'][0]}, doseq=True)
                    clean_url = urlunparse((
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path,
                        parsed.params,
                        clean_query,
                        parsed.fragment
                    ))
                    if clean_url != url:
                        logger.info(f"Stripped playlist params from URL: {url} -> {clean_url}")
                    return clean_url

            return url
        except Exception as e:
            logger.warning(f"Failed to strip playlist params from {url}: {e}")
            return url

    @staticmethod
    async def extract_info(url: str, timeout: float = 60.0, strip_playlist: bool = False, retries: int = 2) -> Optional[Dict[str, Any]]:
        """
        Async version - runs blocking yt-dlp in executor to prevent blocking event loop
        Input: YouTube playlist URL
        Extract playlist information and video URLs
        Output: (id, title, entries,...)

        Args:
            url: YouTube URL
            timeout: Timeout in seconds
            strip_playlist: If True, strip playlist/radio params before extraction (useful for refresh)
            retries: Number of retries on failure (default: 2)
        """
        # Strip playlist params if requested (for refresh operations)
        if strip_playlist:
            url = YouTubeHandler.strip_playlist_params(url)

        last_error = None
        for attempt in range(retries + 1):
            try:
                if attempt > 0:
                    # Wait before retry with exponential backoff
                    wait_time = min(2 ** attempt, 10)  # Max 10 seconds
                    logger.info(f"⏳ Retry attempt {attempt}/{retries} after {wait_time}s for {url}")
                    await asyncio.sleep(wait_time)

                loop = asyncio.get_running_loop()
                # Run blocking call in executor with timeout
                info = await asyncio.wait_for(
                    loop.run_in_executor(None, YouTubeHandler._extract_info_sync, url),
                    timeout=timeout
                )

                if info:  # Success
                    if attempt > 0:
                        logger.info(f"✅ Retry successful on attempt {attempt}")
                    return info

            except asyncio.TimeoutError:
                last_error = f"Timeout (exceeded {timeout}s)"
                logger.warning(f"⏱️ Attempt {attempt + 1}/{retries + 1} timed out for {url}")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"⚠️ Attempt {attempt + 1}/{retries + 1} failed for {url}: {type(e).__name__}")

        # All retries failed
        logger.error(f"❌ All {retries + 1} attempts failed for {url}. Last error: {last_error}")
        return None

    @staticmethod
    def is_playlist_url(url: str) -> bool:
        if not url or not isinstance(url, str):
            return False
        playlist_patterns = [
            r"youtube\.com/playlist\?list=",
            r"music\.youtube\.com/playlist\?list=",
        ]
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in playlist_patterns)

    # @staticmethod
    # def is_single_video_with_playlist(url: str) -> bool:
    #     if not url or not isinstance(url, str):
    #         return False
    #     single_video_patterns = [
    #         r"youtube\.com/watch\?.*v=.*&.*list=",
    #         r"youtube\.com/watch\?.*list=.*&.*v=",
    #         r"youtu\.be/.*\?.*list=",
    #     ]
    #     return any(
    #         re.search(pattern, url, re.IGNORECASE) for pattern in single_video_patterns
    #     )

    @staticmethod
    def extract_playlist_id(url: str) -> Optional[str]:
        try:
            parsed_url = urlparse(url)
            if parsed_url.netloc in [
                "www.youtube.com",
                "youtube.com",
                "music.youtube.com",
                "youtu.be",
            ]:
                if "list=" in parsed_url.query:
                    query_params = parse_qs(parsed_url.query)
                    return query_params.get("list", [None])[0]
            return None
        except Exception as e:
            logger.error(f"Error extracting playlist ID from {url}: {e}")
            return None

    @staticmethod
    def _extract_playlist_sync(url: str) -> Tuple[bool, List[str], str]:
        """Synchronous playlist extraction - to be run in executor"""
        try:
            playlist_id = YouTubeHandler.extract_playlist_id(url)
            if not playlist_id:
                return False, [], "Invalid playlist URL"

            ydl_opts = {
                "format": "bestaudio/best",
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": True,
                "playlist_items": "1-100",
                "socket_timeout": 30,
            }
            video_urls = []

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    """
                    Input: YouTube playlist URL
                    Extract playlist information and video URLs
                    Output: (id, title, entries,...)
                    """
                    playlist_info = ydl.extract_info(url, download=False)
                    if not playlist_info:
                        return False, [], "Could not extract playlist information"

                    playlist_title = playlist_info.get("title", "Unknown Playlist")
                    entries = playlist_info.get("entries", [])

                    if not entries:
                        return (
                            False,
                            [],
                            f"Playlist '{playlist_title}' is empty",
                        )

                    for entry in entries[:]:
                        if entry and entry.get("id"):
                            video_urls.append(f"https://www.youtube.com/watch?v={entry['id']}")

                    if not video_urls:
                        return (
                            False,
                            [],
                            f"No accessible videos found in playlist '{playlist_title}'",
                        )

                    logger.info(f"Extracted {len(video_urls)} videos from playlist: {playlist_title}")
                    return (True, video_urls, f"Found {len(video_urls)} videos in '{playlist_title}'")

                except yt_dlp.DownloadError as e:
                    error_msg = str(e)
                    if "Private video" in error_msg:
                        return False, [], "Playlist is private or unavailable"
                    elif "Video unavailable" in error_msg:
                        return False, [], "Playlist contains unavailable videos"
                    else:
                        return False, [], f"Error accessing playlist: {error_msg}"
                except Exception as e:
                    logger.error(f"yt-dlp error processing playlist {url}: {e}")
                    return False, [], f"Error processing playlist: {str(e)}"

        except ImportError:
            logger.error("yt-dlp not available for playlist processing")
            return (False, [], "YouTube playlist processing not available (yt-dlp required)")
        except Exception as e:
            logger.error(f"Unexpected error processing playlist {url}: {e}")
            return False, [], f"Unexpected error: {str(e)}"

    @staticmethod
    async def extract_playlist(url: str, timeout: float = 90.0) -> Tuple[bool, List[str], str]:
        """
        Async playlist extraction - runs blocking yt-dlp in executor
        Input: YouTube playlist URL
        Output: (success, video_urls, message)
        """
        try:
            loop = asyncio.get_running_loop()
            # Run blocking call in executor with timeout
            result = await asyncio.wait_for(
                loop.run_in_executor(None, YouTubeHandler._extract_playlist_sync, url),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Timeout extracting playlist from {url} (exceeded {timeout}s)")
            return False, [], f"Timeout extracting playlist (exceeded {timeout}s)"
        except Exception as e:
            logger.error(f"Error in async extract_playlist for {url}: {e}")
            return False, [], f"Error extracting playlist: {str(e)}"

    # @staticmethod
    # def format_playlist_message(
    #     video_count: int, playlist_title: str, processing_type: str = "added"
    # ) -> str:
    #     if video_count == 0:
    #         return f"❌ No videos found in playlist '{playlist_title}'"
    #     elif video_count == 1:
    #         return (
    #             f"✅ {processing_type.title()} 1 video from playlist '{playlist_title}'"
    #         )
    #     else:
    #         return f"✅ {processing_type.title()} {video_count} videos from playlist '{playlist_title}'"


class YouTubeErrorHandler:
    """YouTube error handling and retry strategies"""

    def __init__(self):
        self._last_403_time: Dict[str, float] = {}
        self._retry_delays = [1, 2, 5, 10, 30]

    def is_403_error(self, error_msg: str) -> bool:
        error_indicators = [
            "403 Forbidden",
            "Server returned 403",
            "HTTP error 403",
            "access denied",
            "Access denied",
        ]
        return any(indicator in error_msg for indicator in error_indicators)

    # def should_retry_403(self, url: str, attempt: int) -> bool:
    #     current_time = time.time()
    #     last_403 = self._last_403_time.get(url, 0)

    #     if current_time - last_403 < 300:
    #         return False

    #     self._last_403_time[url] = current_time
    #     return attempt < 3

    # async def get_retry_delay(self, attempt: int) -> int:
    #     return (
    #         self._retry_delays[attempt]
    #         if attempt < len(self._retry_delays)
    #         else self._retry_delays[-1]
    #     )

    # def get_alternative_format(self, attempt: int) -> str:
    #     formats = [
    #         "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
    #         "worst[ext=webm]/worst[ext=m4a]/worst/best",
    #         "bestaudio[protocol^=http]/best[protocol^=http]",
    #         "worst",
    #     ]
    #     return formats[attempt] if attempt < len(formats) else formats[-1]

    # def get_alternative_extractor_args(self, attempt: int) -> Dict[str, Any]:
    #     configs = [
    #         {"youtube": {"skip": ["hls", "dash"], "player_client": ["android", "web"]}},
    #         {"youtube": {"skip": ["hls"], "player_client": ["web"]}},
    #         {"youtube": {"skip": ["dash"], "player_client": ["android"]}},
    #         {"youtube": {"player_client": ["web"]}},
    #     ]
    #     return configs[attempt] if attempt < len(configs) else configs[-1]

    # def clean_old_403_records(self, max_age_hours: int = 24):
    #     current_time = time.time()
    #     cutoff_time = current_time - (max_age_hours * 3600)
    #     urls_to_remove = [
    #         url
    #         for url, timestamp in self._last_403_time.items()
    #         if timestamp < cutoff_time
    #     ]

    #     for url in urls_to_remove:
    #         del self._last_403_time[url]

    #     if urls_to_remove:
    #         logger.debug(f"Cleaned up {len(urls_to_remove)} old 403 records")
