"""
YouTube Playlist Handler
Utilities for extracting and processing YouTube playlist URLs
"""

import re
import logging
from typing import List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


class YouTubePlaylistHandler:
    """Handle YouTube playlist URL processing"""

    @staticmethod
    def is_playlist_url(url: str) -> bool:
        """Check if URL is a YouTube playlist"""
        if not url or not isinstance(url, str):
            return False

        # Clean URL patterns for playlists
        playlist_patterns = [
            r"youtube\.com/playlist\?list=",
            r"youtube\.com/watch\?.*list=",
            r"youtu\.be/.*\?.*list=",
            r"music\.youtube\.com/playlist\?list=",
        ]

        return any(
            re.search(pattern, url, re.IGNORECASE) for pattern in playlist_patterns
        )

    @staticmethod
    def extract_playlist_id(url: str) -> Optional[str]:
        """Extract playlist ID from YouTube URL"""
        try:
            parsed_url = urlparse(url)

            # Handle different YouTube domains
            if parsed_url.netloc in [
                "www.youtube.com",
                "youtube.com",
                "music.youtube.com",
            ]:
                if "list=" in parsed_url.query:
                    query_params = parse_qs(parsed_url.query)
                    playlist_id = query_params.get("list", [None])[0]
                    if playlist_id:
                        return playlist_id

            elif parsed_url.netloc in ["youtu.be"]:
                if "list=" in parsed_url.query:
                    query_params = parse_qs(parsed_url.query)
                    playlist_id = query_params.get("list", [None])[0]
                    if playlist_id:
                        return playlist_id

            return None

        except Exception as e:
            logger.error(f"Error extracting playlist ID from {url}: {e}")
            return None

    @staticmethod
    async def extract_playlist_videos(url: str) -> Tuple[bool, List[str], str]:
        """
        Extract video URLs from YouTube playlist
        Returns: (success, video_urls, error_message)
        """
        try:
            import yt_dlp

            playlist_id = YouTubePlaylistHandler.extract_playlist_id(url)
            if not playlist_id:
                return False, [], "Invalid playlist URL"

            # yt-dlp options for playlist extraction
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,  # Only extract URLs, don't download
                "playlist_items": "1-100",  # Limit to first 100 videos to prevent abuse
            }

            video_urls = []

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    # Extract playlist info
                    playlist_info = ydl.extract_info(url, download=False)

                    if not playlist_info:
                        return False, [], "Could not extract playlist information"

                    # Get playlist title
                    playlist_title = playlist_info.get("title", "Unknown Playlist")

                    # Extract video entries
                    entries = playlist_info.get("entries", [])
                    if not entries:
                        return (
                            False,
                            [],
                            f"Playlist '{playlist_title}' is empty or private",
                        )

                    # Convert entries to video URLs
                    for entry in entries[:100]:  # Limit to 100 videos
                        if entry and entry.get("id"):
                            video_id = entry["id"]
                            video_url = f"https://www.youtube.com/watch?v={video_id}"
                            video_urls.append(video_url)

                    if not video_urls:
                        return (
                            False,
                            [],
                            f"No accessible videos found in playlist '{playlist_title}'",
                        )

                    logger.info(
                        f"Extracted {len(video_urls)} videos from playlist: {playlist_title}"
                    )
                    return (
                        True,
                        video_urls,
                        f"Found {len(video_urls)} videos in '{playlist_title}'",
                    )

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
            return (
                False,
                [],
                "YouTube playlist processing not available (yt-dlp required)",
            )

        except Exception as e:
            logger.error(f"Unexpected error processing playlist {url}: {e}")
            return False, [], f"Unexpected error: {str(e)}"

    @staticmethod
    def format_playlist_message(
        video_count: int, playlist_title: str, processing_type: str = "added"
    ) -> str:
        """Format user-friendly message for playlist operations"""
        if video_count == 0:
            return f"❌ No videos found in playlist '{playlist_title}'"
        elif video_count == 1:
            return (
                f"✅ {processing_type.title()} 1 video from playlist '{playlist_title}'"
            )
        else:
            return f"✅ {processing_type.title()} {video_count} videos from playlist '{playlist_title}'"
