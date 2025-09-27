from __future__ import annotations
from typing import List, Optional

from .playlist import Playlist, PlaylistEntry
from ..repositories.playlist_repository import PlaylistRepository
from ..valueobjects.source_type import SourceType


class LibraryManager:
    """Manages the music library with persistent storage"""

    def __init__(self, base_path: str = "playlist"):
        self._repository = PlaylistRepository(base_path)
        self._cache: dict[str, Playlist] = {}

    def create_playlist(self, name: str) -> bool:
        """Create a new empty playlist"""
        if self._repository.exists(name):
            return False

        playlist = Playlist(name)
        success = self._repository.save(playlist)
        if success:
            self._cache[name] = playlist
        return success

    def get_playlist(self, name: str) -> Optional[Playlist]:
        """Retrieve a playlist by name (with caching)"""
        if name in self._cache:
            return self._cache[name]

        playlist = self._repository.load(name)
        if playlist:
            self._cache[name] = playlist
        return playlist

    def save_playlist(self, playlist: Playlist) -> bool:
        """Save playlist to storage"""
        success = self._repository.save(playlist)
        if success:
            self._cache[playlist.name] = playlist
        return success

    def delete_playlist(self, name: str) -> bool:
        """Delete a playlist"""
        success = self._repository.delete(name)
        if success and name in self._cache:
            del self._cache[name]
        return success

    def list_playlists(self) -> List[str]:
        """List all playlist names"""
        return self._repository.list_all()

    def add_to_playlist(
        self,
        playlist_name: str,
        original_input: str,
        source_type: SourceType,
        title: Optional[str] = None,
    ) -> bool:
        """Add song to playlist"""
        playlist = self.get_playlist(playlist_name)
        if not playlist:
            return False

        playlist.add_entry(original_input, source_type, title)
        return self.save_playlist(playlist)

    def remove_from_playlist(self, playlist_name: str, index: int) -> bool:
        """Remove song from playlist by index"""
        playlist = self.get_playlist(playlist_name)
        if not playlist:
            return False

        if playlist.remove_entry(index):
            return self.save_playlist(playlist)
        return False

    def clear_playlist(self, playlist_name: str) -> bool:
        """Clear all songs from playlist"""
        playlist = self.get_playlist(playlist_name)
        if not playlist:
            return False

        playlist.clear()
        return self.save_playlist(playlist)
