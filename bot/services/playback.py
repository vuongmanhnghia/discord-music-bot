import asyncio
from typing import Optional

from ..domain.entities.song import Song
from ..domain.entities.input import InputAnalyzer
from ..config.performance import performance_config
from ..config.service_constants import ErrorMessages, ServiceConstants

from ..pkg.logger import logger
from .processing import SongProcessingService
from .cached_processing import CachedSongProcessor
from .audio_service import audio_service
from ..utils.async_processor import (
    AsyncSongProcessor,
    ProcessingPriority,
    initialize_async_processor,
    get_async_processor,
)


class PlaybackService:
    """
    Main playback service implementing the complete flow:

    1. Analyze user input (URL or search query)
    2. Create Song object
    3. Process song (extract metadata + stream URL)
    4. Add to queue
    5. Start playback loop if not already playing
    """

    def __init__(self):
        # Load performance configuration
        self.config = performance_config
        self.config.log_config()  # Log current configuration

        self.processing_service = SongProcessingService()
        self.cached_processor = CachedSongProcessor()  # Smart caching processor
        self.async_processor: Optional[AsyncSongProcessor] = (
            None  # Will be initialized later
        )
        self._processing_tasks: dict[int, set[asyncio.Task]] = {}

    # ===============================
    # Common Helper Methods
    # ===============================

    async def _add_song_to_queue(self, song: Song, guild_id: int) -> Optional[int]:
        """
        Add a song to the queue

        Returns:
            Position in queue if successful, None otherwise
        """
        queue_manager = audio_service.get_queue_manager(guild_id)
        if not queue_manager:
            logger.error(f"No queue manager found for guild {guild_id}")
            return None

        position = await queue_manager.add_song(song)
        logger.info(f"Added song to queue at position {position}: {song.display_name}")
        return position

    async def _handle_auto_play(self, guild_id: int, auto_play: bool) -> None:
        """Start playback if auto_play is enabled and not already playing"""
        if auto_play and not audio_service.is_playing(guild_id):
            await self._try_start_playback(guild_id)

    # ===============================
    # Public Play Request Methods
    # ===============================

    async def play_request(
        self, user_input: str, guild_id: int, requested_by: str, auto_play: bool = True
    ) -> tuple[bool, str, Optional[Song]]:
        """
        Handle a play request from user

        Returns:
            (success, message, song) tuple
        """
        try:
            # Analyze user input and create song
            song = InputAnalyzer.create_song(
                user_input=user_input, requested_by=requested_by, guild_id=guild_id
            )

            # Process song (wait for completion)
            success = await self.processing_service.process_song(song)

            if not success:
                return (
                    False,
                    ErrorMessages.failed_to_process_song(song.error_message),
                    None,
                )

            # Add to queue after processing is complete
            position = await self._add_song_to_queue(song, guild_id)
            if position is None:
                return (False, ErrorMessages.no_queue_manager(), None)

            # Start playback if auto_play is enabled
            await self._handle_auto_play(guild_id, auto_play)

            return (
                True,
                ErrorMessages.song_added(song.display_name, position, cached=False),
                song,
            )

        except Exception as e:
            logger.error(f"play_request failed for '{user_input}': {e}")
            return (False, f"Failed to process request: {str(e)}", None)

    async def play_request_cached(
        self, user_input: str, guild_id: int, requested_by: str, auto_play: bool = True
    ) -> tuple[bool, str, Optional[Song]]:
        """
        Handle a play request using smart caching for faster responses

        Returns:
            (success, message, song) tuple
        """
        try:
            # Process with smart caching (much faster for cached content)
            song_data, was_cached = await self.cached_processor.process_song(user_input)

            if not song_data:
                return (False, ErrorMessages.failed_to_process_song(), None)

            # Create Song object from cached/processed data
            song = await self.cached_processor.create_song_from_data(
                song_data, requested_by, guild_id
            )

            # Add to queue
            position = await self._add_song_to_queue(song, guild_id)
            if position is None:
                return (False, ErrorMessages.no_queue_manager(), None)

            # Start playback if auto_play is enabled
            await self._handle_auto_play(guild_id, auto_play)

            return (
                True,
                ErrorMessages.song_added(
                    song.display_name, position, cached=was_cached
                ),
                song,
            )

        except Exception as e:
            logger.error(f"play_request_cached failed for '{user_input}': {e}")
            # Fallback to original processing method
            return await self.play_request(
                user_input, guild_id, requested_by, auto_play
            )

    async def _try_start_playback(self, guild_id: int):
        """Try to start playback if conditions are met"""
        try:
            # Quick checks
            if audio_service.is_playing(guild_id):
                return

            if not audio_service.is_connected(guild_id):
                return

            queue_manager = audio_service.get_queue_manager(guild_id)
            if not queue_manager:
                return

            current_song = queue_manager.current_song
            if not current_song or not current_song.is_ready:
                return

            # Start playback
            success = await audio_service.play_next_song(guild_id)

            if not success:
                logger.error(f"Failed to start playback in guild {guild_id}")

        except Exception as e:
            logger.error(f"Error starting playback in guild {guild_id}: {e}")

    async def play_request_async(
        self,
        user_input: str,
        guild_id: int,
        requested_by: str,
        priority: ProcessingPriority = ProcessingPriority.NORMAL,
        interaction: Optional[object] = None,
        auto_play: bool = True,
    ) -> tuple[bool, str, Optional[Song], Optional[str]]:
        """
        Play request with async background processing

        Returns:
            (success, message, song, task_id)
        """
        try:
            # Initialize async processor if needed
            if self.async_processor is None:
                self.async_processor = await get_async_processor()

            # Analyze input and create song
            song = InputAnalyzer.create_song(user_input, requested_by, guild_id)

            if not song:
                return (False, "Invalid input", None, None)

            # Verify queue manager exists
            if not audio_service.get_queue_manager(guild_id):
                return (False, ErrorMessages.no_queue_manager(), None, None)

            # Submit for async processing with callback
            callback = None
            if interaction:
                from ..utils.discord_ui import EnhancedProgressCallback

                callback = EnhancedProgressCallback(interaction)
            else:
                callback = self._create_async_callback_with_queue(guild_id, auto_play)

            task_id = await self.async_processor.submit_task(
                song=song, priority=priority, callback=callback
            )

            return (
                True,
                ErrorMessages.processing_song(),
                song,
                task_id,
            )

        except Exception as e:
            logger.error(f"play_request_async failed for '{user_input}': {e}")
            return (False, f"Lỗi: {str(e)}", None, None)

    def _create_async_callback_with_queue(self, guild_id: int, auto_play: bool = True):
        """Create callback that adds song to queue AFTER processing completes"""

        async def callback(task):
            try:
                if task.status.value == "completed":
                    # Add to queue ONLY after successful processing
                    position = await self._add_song_to_queue(task.song, guild_id)
                    if position is not None:
                        # Try to start playback if auto_play is enabled
                        await self._handle_auto_play(guild_id, auto_play)

                elif task.status.value == "failed":
                    logger.error(
                        f"Async processing failed for task {task.id}: {task.error_message}"
                    )

            except Exception as e:
                logger.error(f"Error in async callback: {e}")

        return callback

    async def get_processing_queue_info(self, guild_id: Optional[int] = None) -> dict:
        """Get information about processing queue"""
        try:
            if self.async_processor is None:
                return {"error": "Async processor not initialized"}

            queue_info = await self.async_processor.get_queue_info()

            # Add guild-specific information if requested
            if guild_id:
                guild_tasks = []
                for task in self.async_processor.active_tasks.values():
                    if task.song.guild_id == guild_id:
                        guild_tasks.append(
                            {
                                "id": task.id,
                                "song": task.song.title,
                                "status": task.status.value,
                                "progress": task.progress,
                                "priority": task.priority.name,
                            }
                        )

                queue_info["guild_tasks"] = guild_tasks

            return queue_info

        except Exception as e:
            logger.error(f"Error getting processing queue info: {e}")
            return {"error": str(e)}

    async def cancel_processing_task(self, task_id: str) -> tuple[bool, str]:
        """Cancel a processing task"""
        try:
            if self.async_processor is None:
                return (False, "Async processor not initialized")

            success = await self.async_processor.cancel_task(task_id)

            if success:
                return (True, f"Task {task_id} cancelled successfully")
            else:
                return (False, f"Could not cancel task {task_id}")

        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {e}")
            return (False, f"Error: {str(e)}")

    async def initialize_async_processing(self, bot_instance=None):
        """Initialize async processing system with dynamic config"""
        try:
            if not self.config.enable_background_processing:
                logger.info("🚫 Background processing disabled by config")
                return True

            self.async_processor = await initialize_async_processor(
                bot_instance,
                worker_count=self.config.async_workers,
                max_queue_size=self.config.processing_queue_size,
            )
            logger.info(
                f"🚀 Async processing system initialized with {self.config.async_workers} workers"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to initialize async processing: {e}")
            return False

    async def skip_current_song(self, guild_id: int) -> tuple[bool, str]:
        """Skip current song"""
        try:
            queue_manager = audio_service.get_queue_manager(guild_id)
            if not queue_manager:
                return (False, ErrorMessages.no_queue_manager())

            current_song = queue_manager.current_song
            if not current_song:
                return (False, ErrorMessages.no_current_song())

            # Skip to next
            success = await audio_service.skip_to_next(guild_id)

            if success:
                next_song = queue_manager.current_song
                if next_song:
                    return (True, ErrorMessages.skipped_to_song(next_song.display_name))
                else:
                    return (True, ErrorMessages.skipped_no_more_songs())
            else:
                return (False, ErrorMessages.cannot_skip())

        except Exception as e:
            logger.error(f"Error skipping song in guild {guild_id}: {e}")
            return (False, f"Lỗi khi bỏ qua: {str(e)}")

    async def pause_playback(self, guild_id: int) -> tuple[bool, str]:
        """Pause current playback"""
        try:
            audio_player = audio_service.get_audio_player(guild_id)
            if not audio_player:
                return (False, ErrorMessages.no_audio_player())

            if audio_player.is_paused:
                return (False, ErrorMessages.already_paused())

            success = audio_player.pause()
            if success:
                song_name = (
                    audio_player.current_song.display_name
                    if audio_player.current_song
                    else "Unknown"
                )
                return (True, ErrorMessages.paused_song(song_name))
            else:
                return (False, ErrorMessages.cannot_pause())

        except Exception as e:
            logger.error(f"Error pausing playback in guild {guild_id}: {e}")
            return (False, f"Lỗi tạm dừng: {str(e)}")

    async def resume_playback(self, guild_id: int) -> tuple[bool, str]:
        """Resume paused playback"""
        try:
            audio_player = audio_service.get_audio_player(guild_id)
            if not audio_player:
                return (False, ErrorMessages.no_audio_player())

            if not audio_player.is_paused:
                return (False, ErrorMessages.nothing_to_resume())

            success = audio_player.resume()
            if success:
                song_name = (
                    audio_player.current_song.display_name
                    if audio_player.current_song
                    else "Unknown"
                )
                return (True, ErrorMessages.resumed_song(song_name))
            else:
                return (False, ErrorMessages.cannot_resume())

        except Exception as e:
            logger.error(f"Error resuming playback in guild {guild_id}: {e}")
            return (False, f"Lỗi tiếp tục: {str(e)}")

    async def stop_playback(self, guild_id: int) -> tuple[bool, str]:
        """Stop playback and clear queue"""
        try:
            # Stop audio
            audio_player = audio_service.get_audio_player(guild_id)
            if audio_player:
                audio_player.stop()

            # Clear queue
            queue_manager = audio_service.get_queue_manager(guild_id)
            if queue_manager:
                await queue_manager.clear()

            # Cancel processing tasks
            if guild_id in self._processing_tasks:
                for task in self._processing_tasks[guild_id]:
                    task.cancel()
                self._processing_tasks[guild_id].clear()

            logger.info(f"Stopped playback and cleared queue in guild {guild_id}")
            return (True, ErrorMessages.stopped_and_cleared())

        except Exception as e:
            logger.error(f"Error stopping playback in guild {guild_id}: {e}")
            return (False, f"Lỗi dừng phát: {str(e)}")

    async def get_queue_status(self, guild_id: int) -> Optional[dict]:
        """Get current queue status"""
        try:
            queue_manager = audio_service.get_queue_manager(guild_id)
            audio_player = audio_service.get_audio_player(guild_id)

            if not queue_manager:
                return None

            current_song = queue_manager.current_song
            upcoming_songs = queue_manager.get_upcoming(5)
            position = queue_manager.position

            return {
                "current_song": current_song,
                "upcoming_songs": upcoming_songs,
                "position": position,
                "is_playing": audio_player.is_playing if audio_player else False,
                "is_paused": audio_player.is_paused if audio_player else False,
                "volume": audio_player.volume if audio_player else 0.5,
            }

        except Exception as e:
            logger.error(f"Error getting queue status for guild {guild_id}: {e}")
            return None

    async def set_volume(self, guild_id: int, volume: float) -> tuple[bool, str]:
        """
        Set playback volume

        Args:
            guild_id: Guild ID
            volume: Volume level as float (0.0 to 1.0)

        Returns:
            (success, message) tuple
        """
        try:
            audio_player = audio_service.get_audio_player(guild_id)
            if not audio_player:
                return (False, ErrorMessages.no_audio_player())

            # Ensure volume is within valid range
            volume = max(0.0, min(1.0, volume))
            success = audio_player.set_volume(volume)

            if success:
                volume_percent = int(volume * 100)
                return (True, ErrorMessages.volume_set(volume_percent))
            else:
                return (False, ErrorMessages.cannot_set_volume())

        except Exception as e:
            logger.error(f"Error setting volume in guild {guild_id}: {e}")
            return (False, f"Lỗi âm lượng: {str(e)}")

    async def set_repeat_mode(self, guild_id: int, mode: str) -> bool:
        """Set repeat mode for queue"""
        try:
            queue_manager = audio_service.get_queue_manager(guild_id)
            if not queue_manager:
                return False

            return queue_manager.set_repeat_mode(mode)

        except Exception as e:
            logger.error(f"Error setting repeat mode in guild {guild_id}: {e}")
            return False

    # ===============================
    # Smart Caching Methods
    # ===============================

    async def get_cache_performance(self) -> dict:
        """Get cache performance statistics"""
        return await self.cached_processor.get_cache_stats()

    async def warm_cache_with_popular(self) -> int:
        """Warm cache with popular songs"""
        return await self.cached_processor.warm_popular_cache()

    async def cleanup_cache(self) -> dict:
        """Clean up expired cache entries"""
        return await self.cached_processor.cleanup_cache()

    async def clear_all_cache(self) -> int:
        """Clear all cached songs"""
        return await self.cached_processor.clear_all_cache()

    async def batch_process_songs(self, urls: list, max_concurrent: int = 3) -> list:
        """Process multiple songs with caching"""
        return await self.cached_processor.batch_process(urls, max_concurrent)

    async def shutdown_cache_system(self):
        """Clean shutdown of caching system"""
        await self.cached_processor.shutdown()

    async def start_playlist_playback(self, guild_id: int, playlist_name: str) -> bool:
        """
        Start playback from a playlist

        Args:
            guild_id: Guild ID where to start playback
            playlist_name: Name of the playlist to play from

        Returns:
            bool: Success status
        """
        try:
            # Import playlist service (lazy import to avoid circular dependency)
            from .playlist_service import PlaylistService
            from ..domain.entities.library import LibraryManager

            # Create library manager instance for reading playlists
            library_manager = LibraryManager()
            playlist_service = PlaylistService(library_manager)

            # Get playlist content
            success, playlist_songs = playlist_service.get_playlist_content(
                playlist_name
            )
            if not success:
                logger.error(f"Failed to load playlist '{playlist_name}'")
                return False

            # Empty playlist is OK - just set as active without loading songs
            if not playlist_songs:
                logger.info(
                    f"Playlist '{playlist_name}' is empty - will be populated with /add commands"
                )
                return True  # Success even if empty

            # Get queue manager
            queue_manager = audio_service.get_queue_manager(guild_id)
            if not queue_manager:
                logger.error(f"No queue manager found for guild {guild_id}")
                return False

            # Clear existing queue only if not empty (safe approach)
            existing_songs = queue_manager.get_all_songs()
            if existing_songs:
                logger.info(f"Clearing {len(existing_songs)} existing songs from queue")
                await queue_manager.clear()

            # Check async processor capacity
            async_songs_count = len(playlist_songs) - ServiceConstants.IMMEDIATE_PROCESS_COUNT
            if async_songs_count > 0 and self.async_processor:
                available_capacity = self.async_processor.get_available_capacity()
                if available_capacity < async_songs_count:
                    logger.warning(
                        f"⚠️ Processing queue has limited capacity: {available_capacity}/{async_songs_count} slots available"
                    )
                    logger.info("Songs will be queued with retry logic as queue space becomes available")

            # Add songs from playlist to queue with smart processing
            processed_count = 0  # Songs processed immediately (in queue)
            queued_for_processing = (
                0  # Songs queued for async processing (not in queue yet)
            )
            immediate_process_count = min(
                ServiceConstants.IMMEDIATE_PROCESS_COUNT, len(playlist_songs)
            )

            logger.info(
                f"Processing {immediate_process_count} songs immediately, {len(playlist_songs) - immediate_process_count} async"
            )

            for idx, song_info in enumerate(playlist_songs):
                try:
                    if idx < immediate_process_count:
                        # Process first few songs immediately for instant playback
                        logger.info(
                            f"🔄 Processing song {idx+1}/{len(playlist_songs)} immediately: {song_info['original_input'][:50]}..."
                        )
                        
                        # Add delay between immediate processing to avoid rate limits (except first song)
                        if idx > 0:
                            await asyncio.sleep(3)  # 3 second delay between songs
                        
                        success, _, song = await self.play_request(
                            song_info["original_input"],
                            guild_id,
                            "Playlist",
                            auto_play=(idx == 0),  # Only auto-play the first song
                        )
                        if success:
                            processed_count += 1
                            logger.info(
                                f"✅ Song {idx+1} ready for playback: {song.display_name if song else 'Unknown'}"
                            )
                        else:
                            logger.warning(
                                f"⚠️ Failed to process song {idx+1} immediately"
                            )
                    else:
                        # Process remaining songs asynchronously in background
                        logger.info(
                            f"📋 Queuing song {idx+1}/{len(playlist_songs)} for async processing: {song_info['original_input'][:50]}..."
                        )
                        
                        # Retry logic for queue full scenarios with exponential backoff
                        max_queue_retries = 5  # Increased from 3
                        base_retry_delay = 2  # seconds
                        
                        for retry in range(max_queue_retries):
                            success_async, _, song_async, task_id = (
                                await self.play_request_async(
                                    song_info["original_input"],
                                    guild_id,
                                    "Playlist",
                                    auto_play=False,  # Don't auto-play async songs
                                )
                            )
                            
                            if success_async:
                                queued_for_processing += 1
                                logger.info(
                                    f"📝 Song {idx+1} submitted for processing with task ID: {task_id}"
                                )
                                break  # Success, exit retry loop
                            else:
                                if retry < max_queue_retries - 1:
                                    # Exponential backoff: 2s, 4s, 8s, 16s
                                    retry_delay = base_retry_delay * (2 ** retry)
                                    logger.warning(
                                        f"⚠️ Queue full, retrying song {idx+1} in {retry_delay}s (attempt {retry+1}/{max_queue_retries})"
                                    )
                                    await asyncio.sleep(retry_delay)
                                else:
                                    logger.error(
                                        f"❌ Failed to submit song {idx+1} after {max_queue_retries} attempts - queue persistently full"
                                    )

                except Exception as e:
                    logger.error(f"Error adding song {idx+1} to playlist playback: {e}")
                    continue

            # Summary logging
            total_handled = processed_count + queued_for_processing
            if total_handled > 0:
                logger.info(
                    f"✅ Started playlist playback: {processed_count} songs ready, "
                    f"{queued_for_processing} processing in background from '{playlist_name}'"
                )
                return True
            else:
                logger.error(
                    f"❌ Failed to start any songs from playlist '{playlist_name}'"
                )
                return False

        except Exception as e:
            logger.error(f"Error in start_playlist_playback: {e}")
            return False


# Global playback service instance
playback_service = PlaybackService()
