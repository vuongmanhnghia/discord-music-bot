from __future__ import annotations
from typing import List, Optional

from ..domain.entities.library import LibraryManager
from ..domain.entities.queue import QueueManager
from ..domain.entities.song import Song
from ..domain.valueobjects.source_type import SourceType
from ..domain.valueobjects.song_status import SongStatus
from ..pkg.logger import logger
from ..utils.lazy_playlist_loader import (
    get_lazy_playlist_loader,
    PlaylistLoadingStrategy,
)


class PlaylistService:
    """Service for managing playlists and queue integration"""

    def __init__(self, library_manager: LibraryManager):
        self.library = library_manager
        # Track loaded playlists per guild to prevent duplicate processing
        self._loaded_playlists: dict[int, dict[str, int]] = (
            {}
        )  # guild_id -> {playlist_name: load_count}

    async def load_playlist_to_queue(
        self,
        playlist_name: str,
        queue_manager: QueueManager,
        requested_by: str,
        guild_id: int,
        force_reload: bool = False,
    ) -> tuple[bool, str]:
        """Load playlist entries into queue as songs"""
        playlist = self.library.get_playlist(playlist_name)
        if not playlist:
            return False, f"Playlist '{playlist_name}' not found"

        if playlist.total_songs == 0:
            logger.info(
                f"Activated empty playlist '{playlist_name}' in guild {guild_id}"
            )
            return (
                True,
                f"Đã kích hoạt playlist **{playlist_name}** (empty). Sử dụng `/add <song>` để thêm bài hát.",
            )

        # Check if playlist already loaded
        if not force_reload:
            if guild_id in self._loaded_playlists:
                if playlist_name in self._loaded_playlists[guild_id]:
                    load_count = self._loaded_playlists[guild_id][playlist_name]
                    logger.info(
                        f"Playlist '{playlist_name}' already loaded {load_count} times in guild {guild_id}, skipping duplicate processing"
                    )

                    # Check if songs from this playlist are still in queue
                    queue_songs = queue_manager.get_all_songs()
                    playlist_songs_in_queue = [
                        song
                        for song in queue_songs
                        if any(
                            entry.original_input == song.original_input
                            for entry in playlist.entries
                        )
                    ]

                    if playlist_songs_in_queue:
                        return (
                            True,
                            f"Playlist '{playlist_name}' already loaded ({len(playlist_songs_in_queue)} songs still in queue)",
                        )
                    else:
                        logger.info(
                            f"Playlist songs no longer in queue, will reload playlist '{playlist_name}'"
                        )
                        # Reset the load tracking for this playlist
                        del self._loaded_playlists[guild_id][playlist_name]

        # Convert playlist entries to Song objects and process them
        added_count = 0
        processing_service = None

        # Import processing service (lazy import to avoid circular dependency)
        try:
            from .processing import SongProcessingService

            processing_service = SongProcessingService()
        except ImportError:
            logger.error("Failed to import SongProcessingService")

        for entry in playlist.entries:
            song = Song(
                original_input=entry.original_input,
                source_type=entry.source_type,
                status=SongStatus.PENDING,
                requested_by=requested_by,
                guild_id=guild_id,
            )

            # Process song to get metadata and stream_url (like in play_request)
            if processing_service:
                try:
                    success = await processing_service.process_song(song)
                    if not success:
                        logger.warning(
                            f"Failed to process playlist song: {song.original_input}"
                        )
                        # Still add to queue even if processing failed
                except Exception as e:
                    logger.error(
                        f"Error processing playlist song {song.original_input}: {e}"
                    )

            queue_manager.add_song(song)
            added_count += 1

        # Track this playlist as loaded for deduplication
        if guild_id not in self._loaded_playlists:
            self._loaded_playlists[guild_id] = {}

        if playlist_name not in self._loaded_playlists[guild_id]:
            self._loaded_playlists[guild_id][playlist_name] = 0

        self._loaded_playlists[guild_id][playlist_name] += 1
        logger.info(
            f"Marked playlist '{playlist_name}' as loaded (count: {self._loaded_playlists[guild_id][playlist_name]}) for guild {guild_id}"
        )

        return (
            True,
            f"Added {added_count} songs from playlist '{playlist_name}' to queue",
        )

    async def load_playlist_to_queue_lazy(
        self,
        playlist_name: str,
        queue_manager: QueueManager,
        requested_by: str,
        guild_id: int,
        strategy: PlaylistLoadingStrategy = PlaylistLoadingStrategy.IMMEDIATE,
        progress_callback: Optional[callable] = None,
    ) -> tuple[bool, str, Optional[str]]:
        """
        Load playlist with lazy loading strategy

        Returns:
            (success, message, job_id)
        """
        playlist = self.library.get_playlist(playlist_name)
        if not playlist:
            return False, f"Playlist '{playlist_name}' not found", None

        if playlist.total_songs == 0:
            logger.info(
                f"Activated empty playlist '{playlist_name}' with lazy loading in guild {guild_id}"
            )
            return (
                True,
                f"Đã kích hoạt playlist **{playlist_name}** (empty). Sử dụng `/add <song>` để thêm bài hát.",
                None,
            )

        # Check if playlist already being loaded
        lazy_loader = await get_lazy_playlist_loader()
        current_job = await lazy_loader.get_guild_job_status(guild_id)

        if current_job and not current_job["is_complete"]:
            return (
                False,
                f"Already loading playlist '{current_job['playlist_name']}'. Please wait...",
                current_job["job_id"],
            )

        # Start lazy loading
        try:
            success, message, job_id = await lazy_loader.load_playlist_lazy(
                playlist=playlist,
                queue_manager=queue_manager,
                requested_by=requested_by,
                guild_id=guild_id,
                strategy=strategy,
                progress_callback=progress_callback,
            )

            if success:
                # Track playlist as loaded
                if guild_id not in self._loaded_playlists:
                    self._loaded_playlists[guild_id] = {}

                if playlist_name not in self._loaded_playlists[guild_id]:
                    self._loaded_playlists[guild_id][playlist_name] = 0

                self._loaded_playlists[guild_id][playlist_name] += 1
                logger.info(
                    f"Started lazy loading for playlist '{playlist_name}' in guild {guild_id}"
                )

            return success, message, job_id

        except Exception as e:
            logger.error(f"Error in lazy playlist loading: {e}")
            return False, f"Error loading playlist: {str(e)}", None

    async def get_playlist_loading_status(self, guild_id: int) -> Optional[dict]:
        """Get current playlist loading status for guild"""
        try:
            lazy_loader = await get_lazy_playlist_loader()
            return await lazy_loader.get_guild_job_status(guild_id)
        except Exception as e:
            logger.error(f"Error getting playlist loading status: {e}")
            return None

    async def cancel_playlist_loading(self, guild_id: int) -> bool:
        """Cancel current playlist loading for guild"""
        try:
            lazy_loader = await get_lazy_playlist_loader()
            return await lazy_loader.cancel_guild_job(guild_id)
        except Exception as e:
            logger.error(f"Error cancelling playlist loading: {e}")
            return False

    def clear_loaded_playlist_tracking(
        self, guild_id: int, playlist_name: str = None
    ) -> None:
        """Clear loaded playlist tracking for deduplication"""
        if guild_id not in self._loaded_playlists:
            return

        if playlist_name:
            # Clear tracking for specific playlist
            if playlist_name in self._loaded_playlists[guild_id]:
                del self._loaded_playlists[guild_id][playlist_name]
                logger.info(
                    f"Cleared loaded tracking for playlist '{playlist_name}' in guild {guild_id}"
                )
        else:
            # Clear all playlist tracking for guild
            self._loaded_playlists[guild_id].clear()
            logger.info(f"Cleared all loaded playlist tracking for guild {guild_id}")

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
