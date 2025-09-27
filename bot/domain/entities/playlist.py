from __future__ import annotations
from typing import Optional

from .song import Song


class Playlist:
    """Represents a playlist entity"""

    def __init__(self, name: str, songs: list):
        self.name = name
        self._songs = songs
        self._current_index = 0

    @property
    def current_song(self) -> Optional[Song]:
        """Get currently playing song"""
        if 0 <= self._current_index < len(self._songs):
            return self._songs[self._current_index]
        return None

    @property
    def total_songs(self) -> int:
        """Get total number of songs in the playlist"""
        return len(self._songs)
