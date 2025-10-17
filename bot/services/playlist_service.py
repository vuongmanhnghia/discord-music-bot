from __future__ import annotations
from typing import List, Optional

from ..domain.entities.library import LibraryManager
from ..domain.valueobjects.source_type import SourceType
from ..pkg.logger import logger
from ..config.service_constants import ErrorMessages


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
            return (True, ErrorMessages.playlist_created(name))
        return False, f"Playlist '{name}' already exists or failed to create"

    def add_to_playlist(
        self,
        playlist_name: str,
        original_input: str,
        source_type: SourceType,
        title: Optional[str] = None,
    ) -> tuple[bool, str]:
        """Add song to playlist with input validation"""
        # Validate input is not empty
        if not original_input or not original_input.strip():
            logger.error(
                f"Validation failed: Empty input for playlist '{playlist_name}'"
            )
            return False, "Input cannot be empty"

        # Validate source type
        if not isinstance(source_type, SourceType):
            logger.error(
                f"Validation failed: Invalid source type '{source_type}' for playlist '{playlist_name}'"
            )
            return False, "Invalid source type"

        # Validate playlist exists
        playlist = self.library.get_playlist(playlist_name)
        if not playlist:
            logger.error(
                f"Validation failed: Playlist '{playlist_name}' not found when adding '{original_input}'"
            )
            return False, f"Playlist '{playlist_name}' not found"

        # Sanitize and validate input based on source type
        original_input = original_input.strip()

        # URL validation for URL-based sources
        if source_type in [
            SourceType.YOUTUBE,
            SourceType.SPOTIFY,
            SourceType.SOUNDCLOUD,
        ]:
            if not (
                original_input.startswith("http://")
                or original_input.startswith("https://")
            ):
                logger.error(
                    f"Validation failed: Invalid URL '{original_input}' for {source_type.value} in playlist '{playlist_name}'"
                )
                return False, f"Invalid URL for {source_type.value}"

        # Try to add to playlist
        try:
            success, is_duplicate = self.library.add_to_playlist(
                playlist_name, original_input, source_type, title
            )

            if success and is_duplicate:
                logger.info(
                    f"Duplicate '{title or original_input}' skipped for playlist '{playlist_name}'"
                )
                return (
                    True,
                    ErrorMessages.song_exists_in_playlist(
                        title or original_input, playlist_name
                    ),
                )
            elif success:
                logger.info(
                    f"Successfully added '{title or original_input}' to playlist '{playlist_name}'"
                )
                return (
                    True,
                    ErrorMessages.song_added_to_playlist(
                        title or original_input, playlist_name
                    ),
                )
            else:
                logger.error(
                    f"Failed to add '{original_input}' to playlist '{playlist_name}' (library rejected)"
                )
                return (
                    False,
                    f"Failed to add to playlist '{playlist_name}' (internal error)",
                )
        except Exception as e:
            logger.error(
                f"Exception adding '{original_input}' to playlist '{playlist_name}': {e}"
            )
            return False, f"Error adding to playlist: {str(e)}"

    def remove_from_playlist(self, playlist_name: str, index: int) -> tuple[bool, dict]:
        """Remove song from playlist by index (1-based for user)

        Returns:
            tuple[bool, dict]: (success, data)
            - If success: data contains removed_index, removed_title, remaining, message
            - If failed: data contains error message
        """
        playlist = self.library.get_playlist(playlist_name)
        if not playlist:
            return False, {
                "error": f"Playlist '{playlist_name}' not found",
                "message": ErrorMessages.playlist_not_found(playlist_name),
            }

        # Convert to 0-based index
        zero_index = index - 1
        if zero_index < 0 or zero_index >= playlist.total_songs:
            return False, {
                "error": f"Invalid index {index}. Playlist has {playlist.total_songs} songs",
                "message": ErrorMessages.invalid_position(playlist.total_songs),
            }

        # Get song title before removing
        removed_song_title = (
            playlist.entries[zero_index].title if playlist.entries else "Unknown"
        )

        # Remove from playlist
        if self.library.remove_from_playlist(playlist_name, zero_index):
            # Get updated playlist to get remaining count
            updated_playlist = self.library.get_playlist(playlist_name)
            remaining = updated_playlist.total_songs if updated_playlist else 0

            return True, {
                "removed_index": index,
                "removed_title": removed_song_title,
                "remaining": remaining,
                "message": ErrorMessages.song_removed(index, remaining),
            }

        return False, {
            "error": f"Failed to remove song from playlist '{playlist_name}'",
            "message": ErrorMessages.cannot_remove_song(playlist_name),
        }

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
