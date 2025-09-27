from __future__ import annotations
from typing import List

from .song import Song
from .playlist import Playlist


class LibraryManager:
    """Manages the music library"""

    def __init__(self):
        self._playlists: dict[str, Playlist] = {}

    def add_playlist(self, name: str, songs: List[Song]) -> None:
        """Add a new playlist"""
        self._playlists[name] = Playlist(name, songs)

    def get_playlist(self, name: str) -> Playlist | None:
        """Retrieve a playlist by name"""
        return self._playlists.get(name)

    def list_playlists(self) -> List[str]:
        """List all playlist names"""
        return list(self._playlists.keys())
