from enum import Enum


class SourceType(Enum):
    """Music source types"""

    SPOTIFY = "spotify"
    YOUTUBE = "youtube"
    SOUNDCLOUD = "soundcloud"
    SEARCH_QUERY = "search"
