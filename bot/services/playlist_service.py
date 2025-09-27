from __future__ import annotations
from typing import List, Optional

from ..domain.entities.library import LibraryManager
from ..domain.entities.queue import QueueManager
from ..domain.entities.song import Song
from ..domain.valueobjects.source_type import SourceType
from ..domain.valueobjects.song_status import SongStatus


class PlaylistService:
    """Service for managing playlists and queue integration"""

    def __init__(self, library_manager: LibraryManager):
        self.library = library_manager

    async def load_playlist_to_queue(
        self,
        playlist_name: str,
        queue_manager: QueueManager,
        requested_by: str,
        guild_id: int,
    ) -> tuple[bool, str]:
        """Load playlist entries into queue as songs"""
        playlist = self.library.get_playlist(playlist_name)
        if not playlist:
            return False, f"Playlist '{playlist_name}' not found"

        if playlist.total_songs == 0:
            return False, f"Playlist '{playlist_name}' is empty"

        # Convert playlist entries to Song objects
        added_count = 0
        for entry in playlist.entries:
            song = Song(
                original_input=entry.original_input,
                source_type=entry.source_type,
                status=SongStatus.PENDING,
                requested_by=requested_by,
                guild_id=guild_id,
            )
            queue_manager.add_song(song)
            added_count += 1

        return (
            True,
            f"Added {added_count} songs from playlist '{playlist_name}' to queue",
        )

    def create_playlist(self, name: str) -> tuple[bool, str]:
        """Create a new playlist"""
        if self.library.create_playlist(name):
            return True, f"Created playlist '{name}'"
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
