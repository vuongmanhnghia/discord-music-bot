from __future__ import annotations
from typing import List, Optional

from .playlist import Playlist
from ..repositories.playlist_repository import PlaylistRepository
from ..valueobjects.source_type import SourceType
from ...pkg.logger import logger


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
    ) -> tuple[bool, bool]:
        """Add song to playlist

        Returns:
            tuple[bool, bool]: (success, is_duplicate)
            - (True, False): Added successfully
            - (True, True): Duplicate found, not added
            - (False, False): Playlist not found or save failed
        """
        playlist = self.get_playlist(playlist_name)
        if not playlist:
            return False, False

        # Check for duplicate before adding
        if playlist.has_entry(original_input):
            logger.info(
                f"Duplicate '{original_input}' skipped in playlist '{playlist_name}'"
            )
            return True, True  # Success = True (no error), Duplicate = True

        # Add entry (returns True if successful)
        if playlist.add_entry(original_input, source_type, title):
            if self.save_playlist(playlist):
                return True, False  # Added successfully
            else:
                # Revert the add if save failed
                playlist._entries.pop()
                return False, False

        return False, False

    def remove_from_playlist(self, playlist_name: str, index: int) -> bool:
        """Remove song from playlist by index"""
        playlist = self.get_playlist(playlist_name)
        if not playlist:
            logger.error(f"Playlist '{playlist_name}' not found")
            return False

        if playlist.remove_entry(index):
            return self.save_playlist(playlist)
        logger.error(f"Failed to remove entry at index {index} from '{playlist_name}'")
        return False

    def clear_playlist(self, playlist_name: str) -> bool:
        """Clear all songs from playlist"""
        playlist = self.get_playlist(playlist_name)
        if not playlist:
            return False

        playlist.clear()
        return self.save_playlist(playlist)

    def exists(self, playlist_name: str) -> bool:
        """Check if a playlist exists"""
        return self._repository.exists(playlist_name)
