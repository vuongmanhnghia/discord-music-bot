"""File system watcher for music folders"""

import asyncio
from pathlib import Path
from typing import Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .config import config
from .logger import logger


class MusicWatcher(FileSystemEventHandler):
    """Optimized file watcher for audio files"""

    AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}

    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self.callback = callback

    def _is_audio_file(self, path: str) -> bool:
        return Path(path).suffix.lower() in self.AUDIO_EXTENSIONS

    def _should_process(self, event) -> bool:
        return (
            not event.is_directory
            and hasattr(event, "src_path")
            and self._is_audio_file(event.src_path)
        )

    def on_created(self, event):
        if self._should_process(event):
            self.callback(event.src_path)

    def on_deleted(self, event):
        if self._should_process(event):
            self.callback(event.src_path)

    def on_moved(self, event):
        if self._should_process(event):
            self.callback(getattr(event, "dest_path", event.src_path))


class FileWatcherManager:
    """Manages file system watching"""

    def __init__(self):
        self.observer: Optional[Observer] = None
        self.callback: Optional[Callable] = None
        self._debounce_task: Optional[asyncio.Task] = None
        self._debounce_scheduled = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, callback: Callable[[str], None]):
        """Start watching music folder"""
        if not config.music_path.exists():
            logger.warning(f"Music folder not found: {config.music_path}")
            return

        self.callback = callback
        # Store the current event loop
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.error("No running event loop found. File watcher cannot start.")
            return

        self.observer = Observer()
        handler = MusicWatcher(self._on_change)

        self.observer.schedule(handler, str(config.music_path), recursive=True)
        self.observer.start()

        logger.info(f"Started watching: {config.music_path}")

    def _on_change(self, changed_path: str):
        """Handle file changes with debouncing"""
        if self._debounce_scheduled or not self._loop:
            return

        self._debounce_scheduled = True

        # Cancel existing task
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

        # Schedule debounced callback in the main event loop
        try:
            self._loop.call_soon_threadsafe(
                self._schedule_debounced_callback, changed_path
            )
        except Exception as e:
            logger.error(f"Failed to schedule callback: {e}")
            self._debounce_scheduled = False

    def _schedule_debounced_callback(self, changed_path: str):
        """Schedule the debounced callback in the main event loop"""
        if self._loop and not self._loop.is_closed():
            self._debounce_task = self._loop.create_task(
                self._debounced_callback(changed_path)
            )

    async def _debounced_callback(self, changed_path: str):
        """Debounced callback execution"""
        try:
            await asyncio.sleep(1.0)  # Debounce delay
            if self.callback:
                self.callback(changed_path)
        except asyncio.CancelledError:
            pass
        finally:
            self._debounce_scheduled = False

    async def stop(self):
        """Stop watching"""
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
            try:
                await self._debounce_task
            except asyncio.CancelledError:
                pass

        if self.observer:
            self.observer.stop()
            # Run in executor to avoid blocking
            if self._loop and not self._loop.is_closed():
                await self._loop.run_in_executor(None, lambda: self.observer.join(timeout=3.0))
            self.observer = None

        self._loop = None
        logger.info("File watcher stopped")


# Global instance
watcher = FileWatcherManager()
