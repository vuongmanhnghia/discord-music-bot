from __future__ import annotations
from typing import List, Optional

from ..domain.entities.library import LibraryManager
from ..domain.valueobjects.source_type import SourceType
from ..pkg.logger import logger


class PlaylistService:
    """Service for managing playlists and queue integration"""

    def __init__(self, library_manager: LibraryManager):
        self.library = library_manager

    def load_playlist(self, playlist_name: str) -> tuple[bool, str]:
        """Simple playlist loading for activation (non-queue loading)"""
        playlist = self.library.get_playlist(playlist_name)
        if not playlist:
            return False, f"Playlist '{playlist_name}' not found"

        if playlist.total_songs == 0:
            return (
                True,
                f"Playlist **{playlist_name}** is empty. Use `/add <song>` to add songs.",
            )

        return (
            True,
            f"Playlist **{playlist_name}** loaded with {playlist.total_songs} songs.",
        )

    def get_playlist_content(self, playlist_name: str) -> tuple[bool, List[dict]]:
        """Get playlist content for display"""
        playlist = self.library.get_playlist(playlist_name)
        if not playlist:
            return False, []

        songs = []
        for entry in playlist.entries:
            songs.append(
                {
                    "title": entry.title or entry.original_input,
                    "original_input": entry.original_input,
                    "source_type": entry.source_type.value,
                    "added_at": entry.added_at,
                }
            )

        return True, songs

    def create_playlist(self, name: str) -> tuple[bool, str]:
        """Create a new playlist"""
        if self.library.create_playlist(name):
            return (
                True,
                f"Đã tạo playlist **{name}** thành công, hãy sử dụng `/use {name}` để kich hoạt.",
            )
        return False, f"Playlist '{name}' already exists or failed to create"

    def add_to_playlist(
        self,
        playlist_name: str,
        original_input: str,
        source_type: SourceType,
        title: Optional[str] = None,
    ) -> tuple[bool, str]:
        """Add song to playlist"""
        if self.library.add_to_playlist(
            playlist_name, original_input, source_type, title
        ):
            return (
                True,
                f"Added '{title or original_input}' to playlist '{playlist_name}'",
            )
        return (
            False,
            f"Failed to add to playlist '{playlist_name}' (playlist may not exist)",
        )

    def remove_from_playlist(self, playlist_name: str, index: int) -> tuple[bool, str]:
        """Remove song from playlist by index (1-based for user)"""
        playlist = self.library.get_playlist(playlist_name)
        if not playlist:
            return False, f"Playlist '{playlist_name}' not found"

        # Convert to 0-based index
        zero_index = index - 1
        if zero_index < 0 or zero_index >= playlist.total_songs:
            return (
                False,
                f"Invalid index {index}. Playlist has {playlist.total_songs} songs",
            )

        if self.library.remove_from_playlist(playlist_name, zero_index):
            return True, f"Removed song #{index} from playlist '{playlist_name}'"
        return False, f"Failed to remove song from playlist '{playlist_name}'"

    def list_playlists(self) -> List[str]:
        """List all available playlists"""
        return self.library.list_playlists()

    def get_playlist_info(self, playlist_name: str) -> Optional[dict]:
        """Get playlist information"""
        playlist = self.library.get_playlist(playlist_name)
        if not playlist:
            return None

        return {
            "name": playlist.name,
            "total_songs": playlist.total_songs,
            "created_at": playlist.created_at,
            "updated_at": playlist.updated_at,
            "entries": [
                {
                    "title": entry.title,
                    "original_input": entry.original_input,
                    "source_type": entry.source_type.value,
                    "added_at": entry.added_at,
                }
                for entry in playlist.entries
            ],
        }

    def delete_playlist(self, playlist_name: str) -> tuple[bool, str]:
        """Delete a playlist"""
        if self.library.delete_playlist(playlist_name):
            return True, f"Deleted playlist '{playlist_name}'"
        return False, f"Failed to delete playlist '{playlist_name}' (may not exist)"
