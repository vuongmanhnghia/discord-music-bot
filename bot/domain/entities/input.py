from ..valueobjects.source_type import SourceType
from .song import Song


class Input:
    """Analyzes user input to determine source type"""

    SPOTIFY_PATTERNS = ["open.spotify.com", "spotify.com", "spotify:"]

    YOUTUBE_PATTERNS = ["youtube.com", "youtu.be", "m.youtube.com"]

    SOUNDCLOUD_PATTERNS = ["soundcloud.com"]

    @classmethod
    def analyze(cls, input: str) -> SourceType:
        """Analyze user input and determine source type"""
        input = input.lower().strip()

        # Check if it's a URL
        if input.startswith(("http://", "https://")):
            # Spotify URL
            if any(pattern in input for pattern in cls.SPOTIFY_PATTERNS):
                return SourceType.SPOTIFY

            # YouTube URL
            if any(pattern in input for pattern in cls.YOUTUBE_PATTERNS):
                return SourceType.YOUTUBE

            # SoundCloud URL
            if any(pattern in input for pattern in cls.SOUNDCLOUD_PATTERNS):
                return SourceType.SOUNDCLOUD

        # If not a recognized URL, treat as search query
        return SourceType.SEARCH_QUERY

    @classmethod
    def create_song(
        cls,
        user_input: str,
        requested_by: str,
        guild_id: int,
    ) -> Song:
        """Create a Song object from user input"""
        source_type = cls.analyze(user_input)

        return Song(
            original_input=user_input.strip(),
            source_type=source_type,
            requested_by=requested_by,
            guild_id=guild_id,
        )
