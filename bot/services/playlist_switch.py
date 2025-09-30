"""
Playlist Switch Manager - Handles safe playlist switching
Prevents bugs like mixed playlists, race conditions, and streaming conflicts
"""

import asyncio
from typing import Optional, Dict, Set
from ..pkg.logger import logger
from ..services.audio_service import audio_service


class PlaylistSwitchManager:
    """Manages safe playlist switching to prevent race conditions and mixed playlists"""

    def __init__(self):
        self._active_switches: Dict[int, str] = (
            {}
        )  # guild_id -> playlist_name being switched to
        self._processing_tasks: Dict[int, Set[asyncio.Task]] = (
            {}
        )  # guild_id -> set of tasks
        self._switch_locks: Dict[int, asyncio.Lock] = {}  # guild_id -> lock

    def _get_switch_lock(self, guild_id: int) -> asyncio.Lock:
        """Get or create switch lock for guild"""
        if guild_id not in self._switch_locks:
            self._switch_locks[guild_id] = asyncio.Lock()
        return self._switch_locks[guild_id]

    async def safe_playlist_switch(
        self, guild_id: int, new_playlist: str, requested_by: str = "User"
    ) -> tuple[bool, str]:
        """
        Safely switch to new playlist with proper cleanup

        Args:
            guild_id: Guild where to switch
            new_playlist: Name of new playlist to switch to
            requested_by: Who requested the switch

        Returns:
            (success, message) tuple
        """
        async with self._get_switch_lock(guild_id):
            try:
                logger.info(
                    f"🔄 Starting safe playlist switch to '{new_playlist}' in guild {guild_id}"
                )

                # Step 1: Cancel any ongoing processing for this guild
                await self._cancel_ongoing_processing(guild_id)

                # Step 2: Stop current playback gracefully
                await self._stop_current_playback(guild_id)

                # Step 3: Clear and reset queue
                await self._clear_queue_safely(guild_id)

                # Step 4: Mark switch as active
                self._active_switches[guild_id] = new_playlist

                # Step 5: Load new playlist
                success, message = await self._load_new_playlist(
                    guild_id, new_playlist, requested_by
                )

                if success:
                    logger.info(
                        f"✅ Successfully switched to playlist '{new_playlist}' in guild {guild_id}"
                    )
                    return (
                        True,
                        f"✅ Đã chuyển sang playlist **{new_playlist}**\n{message}",
                    )
                else:
                    logger.error(
                        f"❌ Failed to switch to playlist '{new_playlist}': {message}"
                    )
                    return (
                        False,
                        f"❌ Không thể chuyển sang playlist **{new_playlist}**\n{message}",
                    )

            except Exception as e:
                logger.error(f"❌ Error during playlist switch: {e}")
                return False, f"❌ Lỗi khi chuyển playlist: {str(e)}"
            finally:
                # Clean up switch state
                self._active_switches.pop(guild_id, None)

    async def _cancel_ongoing_processing(self, guild_id: int):
        """Cancel any ongoing song processing tasks for guild"""
        if guild_id in self._processing_tasks:
            tasks = self._processing_tasks[guild_id].copy()
            logger.info(
                f"🛑 Cancelling {len(tasks)} ongoing processing tasks for guild {guild_id}"
            )

            for task in tasks:
                if not task.done():
                    task.cancel()

            # Wait for cancellation (with timeout)
            if tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*tasks, return_exceptions=True), timeout=3.0
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        f"⏰ Timeout waiting for task cancellation in guild {guild_id}"
                    )

            self._processing_tasks[guild_id].clear()

    async def _stop_current_playback(self, guild_id: int):
        """Stop current playback gracefully"""
        try:
            audio_player = audio_service.get_audio_player(guild_id)
            if audio_player and audio_player.is_playing:
                logger.info(f"⏹️ Stopping current playback in guild {guild_id}")
                audio_player.stop()
                # Give a moment for cleanup
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.warning(f"Warning stopping playback in guild {guild_id}: {e}")

    async def _clear_queue_safely(self, guild_id: int):
        """Clear queue safely"""
        try:
            queue_manager = audio_service.get_queue_manager(guild_id)
            if queue_manager:
                old_count = len(queue_manager.get_all_songs())
                await queue_manager.clear()
                logger.info(
                    f"🧹 Cleared {old_count} songs from queue in guild {guild_id}"
                )
        except Exception as e:
            logger.warning(f"Warning clearing queue in guild {guild_id}: {e}")

    async def _load_new_playlist(
        self, guild_id: int, playlist_name: str, requested_by: str
    ) -> tuple[bool, str]:
        """Load new playlist into clean queue"""
        try:
            # Import here to avoid circular imports
            from ..services.playback import playback_service

            # Use the existing playlist loading logic but with clean state
            success = await playback_service.start_playlist_playback(
                guild_id, playlist_name
            )

            if success:
                queue_manager = audio_service.get_queue_manager(guild_id)
                if queue_manager:
                    song_count = len(queue_manager.get_all_songs())
                    if song_count > 0:
                        return True, f"Đã tải {song_count} bài hát từ playlist"
                    else:
                        # Empty playlist is fine - ready for /add commands
                        return True, f"Playlist '{playlist_name}' đã sẵn sàng (trống, sử dụng /add để thêm bài)"
                else:
                    return True, f"Playlist '{playlist_name}' đã được chọn"
            else:
                return False, "Không thể tải playlist"

        except Exception as e:
            logger.error(f"Error loading playlist '{playlist_name}': {e}")
            return False, f"Lỗi khi tải playlist: {str(e)}"

    def is_switching(self, guild_id: int) -> bool:
        """Check if guild is currently switching playlists"""
        return guild_id in self._active_switches

    def get_switching_playlist(self, guild_id: int) -> Optional[str]:
        """Get name of playlist being switched to (if any)"""
        return self._active_switches.get(guild_id)

    def track_processing_task(self, guild_id: int, task: asyncio.Task):
        """Track a processing task for potential cancellation"""
        if guild_id not in self._processing_tasks:
            self._processing_tasks[guild_id] = set()
        self._processing_tasks[guild_id].add(task)

        # Auto-cleanup when task completes
        def cleanup(t):
            if guild_id in self._processing_tasks:
                self._processing_tasks[guild_id].discard(task)

        task.add_done_callback(cleanup)

    async def safe_add_to_queue(
        self, guild_id: int, song_input: str, requested_by: str
    ) -> tuple[bool, str]:
        """Safely add song to queue, respecting ongoing switches"""
        if self.is_switching(guild_id):
            switching_to = self.get_switching_playlist(guild_id)
            logger.warning(
                f"⚠️ Blocking add to queue - guild {guild_id} switching to '{switching_to}'"
            )
            return (
                False,
                f"⚠️ Đang chuyển sang playlist **{switching_to}**, vui lòng chờ...",
            )

        # Proceed with normal add logic
        from ..services.playback import playback_service

        try:
            success, message, song = await playback_service.play_request(
                song_input, guild_id, requested_by, auto_play=True
            )
            return success, message
        except Exception as e:
            return False, f"Lỗi khi thêm bài hát: {str(e)}"


# Global instance
playlist_switch_manager = PlaylistSwitchManager()
