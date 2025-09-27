"""
Playback orchestration service
Implements the complete playback flow as specified
"""

import asyncio
from typing import Optional

from ..domain.models import Song, InputAnalyzer, QueueManager
from ..logger import logger
from .processing import SongProcessingService
from .audio import audio_service


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
        self.processing_service = SongProcessingService()
        self._processing_tasks: dict[int, set[asyncio.Task]] = {}

    async def play_request(
        self, user_input: str, guild_id: int, requested_by: str, auto_play: bool = True
    ) -> tuple[bool, str, Optional[Song]]:
        """
        Handle a play request from user

        Returns:
            (success, message, song) tuple
        """
        logger.info(
            f"Processing play request: '{user_input}' from {requested_by} in guild {guild_id}"
        )

        try:
            # Step 1: Analyze user input
            song = InputAnalyzer.create_song(
                user_input=user_input, requested_by=requested_by, guild_id=guild_id
            )

            logger.info(
                f"Analyzed input: {song.source_type.value} - {song.original_input}"
            )

            # Step 2: Process song first (wait for completion)
            logger.info(f"Processing song: {song.original_input}")
            success = await self.processing_service.process_song(song)

            if not success:
                logger.warning(
                    f"Failed to process song: {song.original_input} - {song.error_message}"
                )
                return (False, f"Không thể xử lý bài hát: {song.error_message}", None)

            # Step 3: Add to queue after processing is complete
            queue_manager = audio_service.get_queue_manager(guild_id)
            position = queue_manager.add_song(song)

            logger.info(
                f"Added processed song to queue at position {position}: {song.display_name}"
            )

            # Step 4: Start playback if not already playing and auto_play is True
            if auto_play and not audio_service.is_playing(guild_id):
                await self._try_start_playback(guild_id)

            return (
                True,
                f"**{song.display_name}** ・ *(Vị trí: {position})*",
                song,
            )

        except Exception as e:
            logger.error(f"Error processing play request '{user_input}': {e}")
            return (False, f"Failed to process request: {str(e)}", None)

    async def _start_song_processing(self, song: Song):
        """Start asynchronous song processing"""
        guild_id = song.guild_id
        if not guild_id:
            return

        # Create task for processing
        task = asyncio.create_task(self._process_song_with_callbacks(song))

        # Track the task
        if guild_id not in self._processing_tasks:
            self._processing_tasks[guild_id] = set()
        self._processing_tasks[guild_id].add(task)

        # Remove task when done
        task.add_done_callback(lambda t: self._processing_tasks[guild_id].discard(t))

    async def _process_song_with_callbacks(self, song: Song):
        """Process song and handle the result"""
        try:
            logger.info(f"Starting processing for: {song.display_name}")

            # Process the song
            success = await self.processing_service.process_song(song)

            if success:
                logger.info(f"Successfully processed: {song.display_name}")

                # If this was the current song and nothing is playing, start playback
                if song.guild_id:
                    await self._try_start_playback(song.guild_id)
            else:
                logger.warning(
                    f"Failed to process: {song.display_name} - {song.error_message}"
                )

        except Exception as e:
            logger.error(f"Error in song processing callback: {e}")
            song.mark_failed(f"Processing callback error: {str(e)}")

    async def _try_start_playback(self, guild_id: int):
        """Try to start playback if conditions are met"""
        try:
            # Check if already playing
            if audio_service.is_playing(guild_id):
                return

            # Check if connected to voice
            if not audio_service.is_connected(guild_id):
                logger.debug(
                    f"Not connected to voice in guild {guild_id}, cannot start playback"
                )
                return

            # Get queue manager
            queue_manager = audio_service.get_queue_manager(guild_id)
            if not queue_manager:
                return

            # Get current song
            current_song = queue_manager.current_song
            if not current_song:
                logger.debug(f"No current song in queue for guild {guild_id}")
                return

            # Check if song is ready
            if not current_song.is_ready:
                logger.debug(f"Current song not ready yet: {current_song.display_name}")
                return

            # Start playback
            logger.info(
                f"Starting playback for guild {guild_id}: {current_song.display_name}"
            )
            success = await audio_service.play_next_song(guild_id)

            if success:
                logger.info(f"Playback started successfully in guild {guild_id}")
            else:
                logger.error(f"Failed to start playback in guild {guild_id}")

        except Exception as e:
            logger.error(f"Error trying to start playback in guild {guild_id}: {e}")

    async def skip_current_song(self, guild_id: int) -> tuple[bool, str]:
        """Skip current song"""
        try:
            queue_manager = audio_service.get_queue_manager(guild_id)
            if not queue_manager:
                return (False, "No queue manager found")

            current_song = queue_manager.current_song
            if not current_song:
                return (False, "No song currently playing")

            # Skip to next
            success = await audio_service.skip_to_next(guild_id)

            if success:
                next_song = queue_manager.current_song
                if next_song:
                    return (True, f"Skipped to: **{next_song.display_name}**")
                else:
                    return (True, "Skipped. No more songs in queue.")
            else:
                return (False, "Failed to skip song")

        except Exception as e:
            logger.error(f"Error skipping song in guild {guild_id}: {e}")
            return (False, f"Skip error: {str(e)}")

    async def pause_playback(self, guild_id: int) -> tuple[bool, str]:
        """Pause current playback"""
        try:
            audio_player = audio_service.get_audio_player(guild_id)
            if not audio_player:
                return (False, "No audio player found")

            if audio_player.is_paused:
                return (False, "Playback is already paused")

            success = audio_player.pause()
            if success:
                return (True, f"Paused: **{audio_player.current_song.display_name}**")
            else:
                return (False, "Failed to pause playback")

        except Exception as e:
            logger.error(f"Error pausing playback in guild {guild_id}: {e}")
            return (False, f"Pause error: {str(e)}")

    async def resume_playback(self, guild_id: int) -> tuple[bool, str]:
        """Resume paused playback"""
        try:
            audio_player = audio_service.get_audio_player(guild_id)
            if not audio_player:
                return (False, "No audio player found")

            if not audio_player.is_paused:
                return (False, "Playback is not paused")

            success = audio_player.resume()
            if success:
                return (True, f"Resumed: **{audio_player.current_song.display_name}**")
            else:
                return (False, "Failed to resume playback")

        except Exception as e:
            logger.error(f"Error resuming playback in guild {guild_id}: {e}")
            return (False, f"Resume error: {str(e)}")

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
                queue_manager.clear()

            # Cancel processing tasks
            if guild_id in self._processing_tasks:
                for task in self._processing_tasks[guild_id]:
                    task.cancel()
                self._processing_tasks[guild_id].clear()

            logger.info(f"Stopped playback and cleared queue in guild {guild_id}")
            return (True, "Stopped playback and cleared queue")

        except Exception as e:
            logger.error(f"Error stopping playback in guild {guild_id}: {e}")
            return (False, f"Stop error: {str(e)}")

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
        """Set playback volume"""
        try:
            audio_player = audio_service.get_audio_player(guild_id)
            if not audio_player:
                return (False, "No audio player found")

            volume = max(0.0, min(1.0, volume))
            success = audio_player.set_volume(volume)

            if success:
                return (True, f"Volume set to {volume:.0%}")
            else:
                return (False, "Failed to set volume")

        except Exception as e:
            logger.error(f"Error setting volume in guild {guild_id}: {e}")
            return (False, f"Volume error: {str(e)}")


# Global playback service instance
playback_service = PlaybackService()

playback_service = PlaybackService()
