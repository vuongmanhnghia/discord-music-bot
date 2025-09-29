"""
Lazy Loading Playlist System
===========================

Advanced playlist loading with lazy evaluation and background processing.
Only loads first few songs immediately, then processes others in background.

Features:
- Instant playlist activation (load only 2-3 songs initially)
- Background async processing for remaining songs
- Just-in-time loading when approaching end of loaded songs
- Smart priority system for next songs to load
- Progress tracking and user feedback
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..domain.entities.song import Song
from ..domain.entities.playlist import Playlist
from ..domain.valueobjects.song_status import SongStatus
from ..pkg.logger import setup_logger
from ..utils.async_processor import (
    AsyncSongProcessor,
    ProcessingPriority,
    get_async_processor,
)

logger = setup_logger(__name__)


class PlaylistLoadingStrategy(Enum):
    """Different strategies for playlist loading"""

    IMMEDIATE = "immediate"  # Load first 3 songs immediately
    PROGRESSIVE = "progressive"  # Load songs progressively as needed
    BACKGROUND = "background"  # Load all in background, no waiting


@dataclass
class PlaylistLoadingJob:
    """Represents a playlist loading job"""

    playlist_name: str
    guild_id: int
    requested_by: str
    queue_manager: object
    strategy: PlaylistLoadingStrategy = PlaylistLoadingStrategy.IMMEDIATE

    # State tracking
    total_songs: int = 0
    loaded_songs: int = 0
    failed_songs: int = 0
    loading_tasks: Set[str] = field(default_factory=set)
    added_songs: Set[str] = field(
        default_factory=set
    )  # Track songs already added to queue

    # Configuration
    immediate_load_count: int = 3  # Load first 3 songs immediately
    buffer_size: int = 2  # Keep 2 songs ahead loaded

    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class LazyPlaylistLoader:
    """
    Advanced playlist loader with lazy loading and background processing

    Features:
    - Load only first few songs immediately for instant playback
    - Process remaining songs in background
    - Smart buffering to always have next songs ready
    - Progress tracking and user notifications
    """

    def __init__(self):
        self.active_jobs: Dict[str, PlaylistLoadingJob] = {}  # job_id -> job
        self.guild_jobs: Dict[int, str] = {}  # guild_id -> current_job_id
        self.async_processor: Optional[AsyncSongProcessor] = None

    async def initialize(self):
        """Initialize the lazy loader with async processor"""
        try:
            self.async_processor = await get_async_processor()
            logger.info("🚄 LazyPlaylistLoader initialized with async processor")
        except Exception as e:
            logger.warning(f"Failed to initialize async processor: {e}")

    async def load_playlist_lazy(
        self,
        playlist: Playlist,
        queue_manager: object,
        requested_by: str,
        guild_id: int,
        strategy: PlaylistLoadingStrategy = PlaylistLoadingStrategy.IMMEDIATE,
        progress_callback: Optional[callable] = None,
    ) -> Tuple[bool, str, str]:
        """
        Load playlist with lazy loading strategy

        Returns:
            (success, message, job_id)
        """

        if playlist.total_songs == 0:
            return False, f"Playlist '{playlist.name}' is empty", ""

        # Create loading job
        job_id = f"playlist_load_{guild_id}_{int(datetime.now().timestamp())}"
        job = PlaylistLoadingJob(
            playlist_name=playlist.name,
            guild_id=guild_id,
            requested_by=requested_by,
            queue_manager=queue_manager,
            strategy=strategy,
            total_songs=playlist.total_songs,
        )

        self.active_jobs[job_id] = job
        self.guild_jobs[guild_id] = job_id

        logger.info(
            f"🚄 Starting lazy loading for playlist '{playlist.name}' ({playlist.total_songs} songs)"
        )

        try:
            if strategy == PlaylistLoadingStrategy.IMMEDIATE:
                return await self._load_immediate_strategy(
                    playlist, job, job_id, progress_callback
                )
            elif strategy == PlaylistLoadingStrategy.PROGRESSIVE:
                return await self._load_progressive_strategy(
                    playlist, job, job_id, progress_callback
                )
            else:  # BACKGROUND
                return await self._load_background_strategy(
                    playlist, job, job_id, progress_callback
                )

        except Exception as e:
            logger.error(f"Error in lazy playlist loading: {e}")
            self._cleanup_job(job_id)
            return False, f"Error loading playlist: {str(e)}", job_id

    async def _load_immediate_strategy(
        self,
        playlist: Playlist,
        job: PlaylistLoadingJob,
        job_id: str,
        progress_callback: Optional[callable] = None,
    ) -> Tuple[bool, str, str]:
        """Load first few songs immediately, rest in background"""

        # Step 1: Load first few songs immediately for instant playback
        immediate_songs = playlist.entries[: job.immediate_load_count]
        background_songs = playlist.entries[job.immediate_load_count :]

        logger.info(
            f"📦 Loading {len(immediate_songs)} songs immediately, {len(background_songs)} in background"
        )

        # Load immediate songs synchronously
        immediate_success_count = 0
        for i, entry in enumerate(immediate_songs):
            try:
                song = self._create_song_from_entry(
                    entry, job.requested_by, job.guild_id
                )

                # Process song immediately (blocking)
                if self.async_processor:
                    # Submit with high priority and wait for completion
                    task_id = await self.async_processor.submit_task(
                        song=song, priority=ProcessingPriority.HIGH, callback=None
                    )

                    # Wait for completion (with timeout)
                    timeout_count = 0
                    while (
                        timeout_count < 60
                    ):  # 60 second timeout per song (increased from 30s)
                        task_status = await self.async_processor.get_task_status(
                            task_id
                        )
                        if task_status and task_status.status.value == "completed":
                            break
                        elif task_status and task_status.status.value == "failed":
                            logger.warning(
                                f"Failed to process immediate song: {entry.original_input}"
                            )
                            break

                        await asyncio.sleep(1)
                        timeout_count += 1

                    if timeout_count >= 60:
                        logger.warning(
                            f"Timeout processing immediate song: {entry.original_input}"
                        )
                        continue

                # Only add to queue if song is actually ready and not already added
                if song.is_ready and entry.original_input not in job.added_songs:
                    position = job.queue_manager.add_song(song)
                    job.added_songs.add(entry.original_input)  # Track as added
                    immediate_success_count += 1
                    job.loaded_songs += 1
                    logger.info(
                        f"✅ Added immediate song to queue: {entry.original_input}"
                    )
                elif not song.is_ready:
                    logger.error(
                        f"❌ Song not ready after processing: {entry.original_input}, "
                        f"Status: {song.status}, Has metadata: {bool(song.metadata)}, "
                        f"Has stream_url: {bool(song.stream_url)}"
                    )
                    job.failed_songs += 1
                elif entry.original_input in job.added_songs:
                    logger.warning(
                        f"Song already added, skipping: {entry.original_input}"
                    )
                    continue
                else:
                    logger.warning(
                        f"Song not ready after processing: {entry.original_input}"
                    )
                    continue

                logger.info(
                    f"✅ Loaded immediate song {i+1}/{len(immediate_songs)}: {entry.title or entry.original_input}"
                )

                # Progress callback
                if progress_callback:
                    await progress_callback(
                        f"Loaded {i+1}/{len(immediate_songs)} immediate songs..."
                    )

            except Exception as e:
                logger.error(
                    f"Error loading immediate song {entry.original_input}: {e}"
                )
                job.failed_songs += 1

        # Step 2: Start background processing for remaining songs
        if background_songs and self.async_processor:
            logger.info(
                f"🔄 Starting background processing for {len(background_songs)} songs"
            )

            for entry in background_songs:
                try:
                    song = self._create_song_from_entry(
                        entry, job.requested_by, job.guild_id
                    )

                    # Submit with normal priority for background processing
                    task_id = await self.async_processor.submit_task(
                        song=song,
                        priority=ProcessingPriority.NORMAL,
                        callback=self._create_background_completion_callback(
                            job_id, job.queue_manager
                        ),
                    )

                    job.loading_tasks.add(task_id)

                except Exception as e:
                    logger.error(
                        f"Error submitting background song {entry.original_input}: {e}"
                    )
                    job.failed_songs += 1

        # Return success if we loaded at least some immediate songs
        if immediate_success_count > 0:
            remaining_count = len(background_songs)
            message = (
                f"✅ Loaded **{immediate_success_count}** songs immediately. "
                f"**{remaining_count}** songs processing in background..."
            )

            if progress_callback:
                await progress_callback(message)

            return True, message, job_id
        else:
            return False, "Failed to load any songs from playlist", job_id

    async def _load_progressive_strategy(
        self,
        playlist: Playlist,
        job: PlaylistLoadingJob,
        job_id: str,
        progress_callback: Optional[callable] = None,
    ) -> Tuple[bool, str, str]:
        """Load songs progressively as queue gets consumed"""
        # Implementation for progressive loading
        # This would monitor queue status and load next batch when needed
        return await self._load_immediate_strategy(
            playlist, job, job_id, progress_callback
        )

    async def _load_background_strategy(
        self,
        playlist: Playlist,
        job: PlaylistLoadingJob,
        job_id: str,
        progress_callback: Optional[callable] = None,
    ) -> Tuple[bool, str, str]:
        """Load all songs in background, no immediate loading"""

        logger.info(
            f"🔄 Starting full background loading for {len(playlist.entries)} songs"
        )

        if not self.async_processor:
            return False, "Async processor not available", job_id

        # Submit all songs for background processing
        for entry in playlist.entries:
            try:
                song = self._create_song_from_entry(
                    entry, job.requested_by, job.guild_id
                )

                task_id = await self.async_processor.submit_task(
                    song=song,
                    priority=ProcessingPriority.NORMAL,
                    callback=self._create_background_completion_callback(
                        job_id, job.queue_manager
                    ),
                )

                job.loading_tasks.add(task_id)

            except Exception as e:
                logger.error(
                    f"Error submitting background song {entry.original_input}: {e}"
                )
                job.failed_songs += 1

        message = f"🔄 Processing **{len(playlist.entries)}** songs in background..."

        if progress_callback:
            await progress_callback(message)

        return True, message, job_id

    def _create_song_from_entry(self, entry, requested_by: str, guild_id: int) -> Song:
        """Create Song object from playlist entry"""
        return Song(
            original_input=entry.original_input,
            source_type=entry.source_type,
            status=SongStatus.PENDING,
            requested_by=requested_by,
            guild_id=guild_id,
        )

    def _create_background_completion_callback(
        self, job_id: str, queue_manager: object
    ):
        """Create callback for background song completion"""

        async def callback(task):
            try:
                job = self.active_jobs.get(job_id)
                if not job:
                    return

                if task.status.value == "completed":
                    # Only add if not already added and song is ready
                    if (
                        task.song.original_input not in job.added_songs
                        and task.song.is_ready
                    ):
                        position = queue_manager.add_song(task.song)
                        job.added_songs.add(task.song.original_input)  # Track as added
                        job.loaded_songs += 1

                        logger.info(
                            f"✅ Background song loaded: {task.song.original_input} (position: {position})"
                        )
                    elif task.song.original_input in job.added_songs:
                        logger.info(
                            f"Song already in queue, skipping: {task.song.original_input}"
                        )
                    else:
                        logger.warning(
                            f"Song not ready for queue: {task.song.original_input}"
                        )

                elif task.status.value == "failed":
                    job.failed_songs += 1
                    logger.warning(
                        f"❌ Background song failed: {task.song.original_input}"
                    )

                # Remove from loading tasks
                if task.id in job.loading_tasks:
                    job.loading_tasks.remove(task.id)

                # Check if all background tasks completed
                if len(job.loading_tasks) == 0:
                    job.completed_at = datetime.now()
                    total_time = (job.completed_at - job.created_at).total_seconds()

                    logger.info(
                        f"🎉 Playlist '{job.playlist_name}' fully loaded: "
                        f"{job.loaded_songs} loaded, {job.failed_songs} failed "
                        f"({total_time:.1f}s)"
                    )

                    # Clean up job after delay
                    await asyncio.sleep(60)  # Keep for 1 minute then cleanup
                    self._cleanup_job(job_id)

            except Exception as e:
                logger.error(f"Error in background completion callback: {e}")

        return callback

    def _cleanup_job(self, job_id: str):
        """Clean up completed job"""
        try:
            if job_id in self.active_jobs:
                job = self.active_jobs[job_id]

                # Remove from guild jobs
                if (
                    job.guild_id in self.guild_jobs
                    and self.guild_jobs[job.guild_id] == job_id
                ):
                    del self.guild_jobs[job.guild_id]

                # Remove job
                del self.active_jobs[job_id]

                logger.info(f"🧹 Cleaned up playlist loading job: {job_id}")

        except Exception as e:
            logger.error(f"Error cleaning up job {job_id}: {e}")

    async def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get status of a playlist loading job"""
        job = self.active_jobs.get(job_id)
        if not job:
            return None

        return {
            "job_id": job_id,
            "playlist_name": job.playlist_name,
            "guild_id": job.guild_id,
            "total_songs": job.total_songs,
            "loaded_songs": job.loaded_songs,
            "failed_songs": job.failed_songs,
            "remaining_tasks": len(job.loading_tasks),
            "strategy": job.strategy.value,
            "created_at": job.created_at,
            "completed_at": job.completed_at,
            "is_complete": len(job.loading_tasks) == 0,
        }

    async def get_guild_job_status(self, guild_id: int) -> Optional[Dict]:
        """Get status of current playlist loading job for guild"""
        job_id = self.guild_jobs.get(guild_id)
        if not job_id:
            return None

        return await self.get_job_status(job_id)

    async def cancel_guild_job(self, guild_id: int) -> bool:
        """Cancel current playlist loading job for guild"""
        job_id = self.guild_jobs.get(guild_id)
        if not job_id:
            return False

        job = self.active_jobs.get(job_id)
        if not job:
            return False

        # Cancel all pending tasks
        if self.async_processor:
            for task_id in job.loading_tasks.copy():
                await self.async_processor.cancel_task(task_id)

        # Clean up job
        self._cleanup_job(job_id)

        logger.info(f"❌ Cancelled playlist loading job for guild {guild_id}")
        return True


# Global lazy loader instance
lazy_playlist_loader: Optional[LazyPlaylistLoader] = None


async def get_lazy_playlist_loader() -> LazyPlaylistLoader:
    """Get or create the global lazy playlist loader"""
    global lazy_playlist_loader

    if lazy_playlist_loader is None:
        lazy_playlist_loader = LazyPlaylistLoader()
        await lazy_playlist_loader.initialize()
        logger.info("🚄 Global LazyPlaylistLoader initialized")

    return lazy_playlist_loader
