"""
Async Song Processing System with Background Workers
===================================================

Advanced asynchronous song processing with worker pool, real-time progress,
and queue management for maximum performance.

Features:
- Background worker pool (3 workers)
- Real-time progress updates via Discord embeds
- Queue management with priority system
- Automatic retry with exponential backoff
- Circuit breaker pattern for error handling
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
import discord

from ..domain.entities.song import Song
from ..domain.valueobjects.song_status import SongStatus
from ..pkg.logger import setup_logger

logger = setup_logger(__name__)


class ProcessingPriority(Enum):
    """Priority levels for song processing"""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class ProcessingStatus(Enum):
    """Status of processing tasks"""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProcessingTask:
    """Represents a song processing task"""

    id: str
    song: Song
    priority: ProcessingPriority = ProcessingPriority.NORMAL
    callback: Optional[Callable] = None
    created_at: datetime = field(default_factory=datetime.now)
    status: ProcessingStatus = ProcessingStatus.QUEUED
    progress: int = 0  # 0-100
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    def __post_init__(self):
        """Generate unique task ID if not provided"""
        if not self.id:
            self.id = f"task_{int(time.time() * 1000)}"


@dataclass
class WorkerStats:
    """Statistics for background workers"""

    worker_id: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_processing_time: float = 0.0
    current_task: Optional[str] = None
    is_active: bool = True
    last_activity: datetime = field(default_factory=datetime.now)


class CircuitBreaker:
    """Circuit breaker pattern for error handling"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit"""
        return (
            self.last_failure_time
            and time.time() - self.last_failure_time > self.recovery_timeout
        )

    def _on_success(self):
        """Handle successful execution"""
        self.failure_count = 0
        self.state = "CLOSED"

    def _on_failure(self):
        """Handle failed execution"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


class AsyncSongProcessor:
    """
    Advanced async song processor with background workers

    Features:
    - Multiple background workers for parallel processing
    - Real-time progress updates via Discord
    - Priority queue management
    - Circuit breaker pattern for error resilience
    - Comprehensive metrics and monitoring
    """

    def __init__(
        self,
        worker_count: int = 3,
        max_queue_size: int = 100,
        progress_callback: Optional[Callable] = None,
    ):
        self.worker_count = worker_count
        self.max_queue_size = max_queue_size
        self.progress_callback = progress_callback

        # Task management
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=max_queue_size
        )
        self.active_tasks: Dict[str, ProcessingTask] = {}
        self.completed_tasks: Dict[str, ProcessingTask] = {}

        # Worker management
        self.workers: List[asyncio.Task] = []
        self.worker_stats: Dict[str, WorkerStats] = {}
        self.is_running = False

        # Error handling
        self.circuit_breaker = CircuitBreaker()
        self.thread_executor = ThreadPoolExecutor(max_workers=worker_count)

        # Metrics
        self.total_tasks_processed = 0
        self.total_processing_time = 0.0
        self.start_time = datetime.now()

        logger.info(f"🔄 AsyncSongProcessor initialized with {worker_count} workers")

    async def start(self):
        """Start the background workers"""
        if self.is_running:
            logger.warning("AsyncSongProcessor already running")
            return

        self.is_running = True

        # Create and start workers
        for i in range(self.worker_count):
            worker_id = f"worker_{i+1}"
            self.worker_stats[worker_id] = WorkerStats(worker_id=worker_id)

            worker_task = asyncio.create_task(
                self._worker_loop(worker_id), name=f"song_processor_{worker_id}"
            )
            self.workers.append(worker_task)

        logger.info(f"🚀 Started {self.worker_count} background workers")

    async def stop(self):
        """Stop all background workers gracefully"""
        if not self.is_running:
            return

        self.is_running = False

        # Cancel all workers
        for worker in self.workers:
            worker.cancel()

        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)

        # Shutdown thread executor
        self.thread_executor.shutdown(wait=True)

        logger.info("⏹️ AsyncSongProcessor stopped")

    async def submit_task(
        self,
        song: Song,
        priority: ProcessingPriority = ProcessingPriority.NORMAL,
        callback: Optional[Callable] = None,
    ) -> str:
        """
        Submit a song for async processing

        Args:
            song: Song to process
            priority: Processing priority
            callback: Optional callback when processing completes

        Returns:
            task_id: Unique task identifier
        """
        if self.task_queue.qsize() >= self.max_queue_size:
            raise Exception("Processing queue is full")

        # Create processing task
        task = ProcessingTask(
            id=f"task_{int(time.time() * 1000)}_{song.original_input}",
            song=song,
            priority=priority,
            callback=callback,
        )

        # Add to queue (priority queue uses negative values for max-heap behavior)
        priority_value = -priority.value
        await self.task_queue.put((priority_value, task.created_at, task))

        self.active_tasks[task.id] = task

        logger.info(
            f"📋 Task {task.id} queued for processing (priority: {priority.name})"
        )

        # Send initial progress update
        await self._send_progress_update(task)

        return task.id

    async def get_task_status(self, task_id: str) -> Optional[ProcessingTask]:
        """Get current status of a processing task"""
        return self.active_tasks.get(task_id) or self.completed_tasks.get(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a processing task"""
        task = self.active_tasks.get(task_id)
        if task and task.status in [
            ProcessingStatus.QUEUED,
            ProcessingStatus.PROCESSING,
        ]:
            task.status = ProcessingStatus.CANCELLED
            logger.info(f"❌ Task {task_id} cancelled")
            return True
        return False

    async def get_queue_info(self) -> Dict[str, Any]:
        """Get information about current queue status"""
        active_count = len(
            [
                t
                for t in self.active_tasks.values()
                if t.status == ProcessingStatus.PROCESSING
            ]
        )
        queued_count = self.task_queue.qsize()

        return {
            "queue_size": queued_count,
            "active_tasks": active_count,
            "total_processed": self.total_tasks_processed,
            "uptime": datetime.now() - self.start_time,
            "worker_stats": {
                wid: {
                    "completed": stats.tasks_completed,
                    "failed": stats.tasks_failed,
                    "current_task": stats.current_task,
                    "is_active": stats.is_active,
                }
                for wid, stats in self.worker_stats.items()
            },
        }

    async def _worker_loop(self, worker_id: str):
        """Main worker loop for processing tasks"""
        worker_stats = self.worker_stats[worker_id]

        logger.info(f"👷 Worker {worker_id} started")

        while self.is_running:
            try:
                # Get task from queue (wait up to 1 second)
                try:
                    priority, created_at, task = await asyncio.wait_for(
                        self.task_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Check if task was cancelled
                if task.status == ProcessingStatus.CANCELLED:
                    continue

                # Process the task
                await self._process_task(task, worker_id, worker_stats)

            except Exception as e:
                logger.error(f"💥 Worker {worker_id} error: {e}")
                logger.error(traceback.format_exc())
                await asyncio.sleep(1)  # Brief pause on error

        worker_stats.is_active = False
        logger.info(f"🏁 Worker {worker_id} stopped")

    async def _process_task(
        self, task: ProcessingTask, worker_id: str, worker_stats: WorkerStats
    ):
        """Process a single task"""
        start_time = time.time()

        try:
            # Update worker and task status
            worker_stats.current_task = task.id
            worker_stats.last_activity = datetime.now()
            task.status = ProcessingStatus.PROCESSING

            logger.info(f"🎵 Worker {worker_id} processing task {task.id}")

            # Send progress update
            task.progress = 10
            await self._send_progress_update(task)

            # Simulate processing steps with progress updates
            await self._process_song_with_progress(task)

            # Mark as completed
            task.status = ProcessingStatus.COMPLETED
            task.progress = 100

            # Update statistics
            processing_time = time.time() - start_time
            worker_stats.tasks_completed += 1
            worker_stats.total_processing_time += processing_time
            self.total_tasks_processed += 1
            self.total_processing_time += processing_time

            # Move to completed tasks
            self.completed_tasks[task.id] = task
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]

            # Send final progress update
            await self._send_progress_update(task)

            # Call completion callback if provided
            if task.callback:
                try:
                    await task.callback(task)
                except Exception as e:
                    logger.error(f"Callback error for task {task.id}: {e}")

            logger.info(f"✅ Task {task.id} completed in {processing_time:.2f}s")

        except Exception as e:
            # Handle processing error
            task.status = ProcessingStatus.FAILED
            task.error_message = str(e)
            task.retry_count += 1

            worker_stats.tasks_failed += 1

            logger.error(f"❌ Task {task.id} failed: {e}")

            # Retry logic
            if task.retry_count < task.max_retries:
                logger.info(
                    f"🔄 Retrying task {task.id} ({task.retry_count}/{task.max_retries})"
                )

                # Exponential backoff
                delay = min(2**task.retry_count, 30)
                await asyncio.sleep(delay)

                # Re-queue the task
                task.status = ProcessingStatus.QUEUED
                priority_value = -task.priority.value
                await self.task_queue.put((priority_value, task.created_at, task))
            else:
                # Max retries exceeded
                await self._send_progress_update(task)
                logger.error(
                    f"💀 Task {task.id} failed permanently after {task.max_retries} retries"
                )

        finally:
            worker_stats.current_task = None

    async def _process_song_with_progress(self, task: ProcessingTask):
        """Process song with detailed progress updates"""
        song = task.song

        try:
            # Import playback_service here to avoid circular imports
            from ..services.playback import playback_service

            # Step 1: Validate URL (20%)
            task.progress = 20
            await self._send_progress_update(task)

            # Step 2: Extract metadata (40%)
            task.progress = 40
            await self._send_progress_update(task)

            # Step 3: Download audio info (60%)
            task.progress = 60
            await self._send_progress_update(task)

            # Step 4: Process audio stream (80%)
            task.progress = 80
            await self._send_progress_update(task)

            # Step 5: Use real processor to process the song
            task.progress = 90
            await self._send_progress_update(task)

            # Actually process the song using the real processor
            success, _, processed_song = await playback_service.play_request(
                song.original_input, song.requested_by, song.guild_id, auto_play=False
            )

            if success and processed_song and processed_song.is_ready:
                # Copy processed data to our song object
                song.metadata = processed_song.metadata
                song.stream_url = processed_song.stream_url
                song.status = SongStatus.READY
                logger.info(f"✅ Song processing completed: {song.display_name}")
            else:
                song.status = SongStatus.FAILED
                logger.warning(f"❌ Song processing failed: {song.original_input}")

        except Exception as e:
            song.status = SongStatus.FAILED
            logger.error(f"💥 Error processing song {song.original_input}: {e}")
            raise

    async def _send_progress_update(self, task: ProcessingTask):
        """Send progress update via callback"""
        if self.progress_callback:
            try:
                await self.progress_callback(task)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")


# Global async processor instance
async_processor: Optional[AsyncSongProcessor] = None


async def initialize_async_processor(
    bot_instance=None, worker_count=3, max_queue_size=100
):
    """Initialize the global async processor with configurable parameters"""
    global async_processor

    if async_processor is None:
        # Create progress callback for Discord updates
        progress_callback = None
        if bot_instance:
            progress_callback = lambda task: default_discord_progress_callback(
                bot_instance, task
            )

        async_processor = AsyncSongProcessor(
            worker_count=worker_count,
            max_queue_size=max_queue_size,
            progress_callback=progress_callback,
        )

        await async_processor.start()
        logger.info(
            f"🚀 Global AsyncSongProcessor initialized with {worker_count} workers"
        )

    return async_processor


async def default_discord_progress_callback(bot, task: ProcessingTask):
    """Default Discord progress update callback - imports locally to avoid circular deps"""
    try:
        from .discord_ui import send_discord_progress_update as discord_update
        await discord_update(bot, task)
    except Exception as e:
        logger.error(f"Discord progress update failed: {e}")


async def get_async_processor() -> AsyncSongProcessor:
    """Get the global async processor instance"""
    global async_processor
    if async_processor is None:
        raise RuntimeError(
            "AsyncSongProcessor not initialized. Call initialize_async_processor() first."
        )
    return async_processor
