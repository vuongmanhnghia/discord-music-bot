from __future__ import annotations
import asyncio
from typing import Optional, List
from collections import deque

from .song import Song


class Queue:
    """
    Thread-safe queue manager with rich functionality
    Optimized with deque for O(1) operations
    """

    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self._songs: List[Song] = []
        self._current_index: int = 0
        self._history: deque[Song] = deque(maxlen=50)  # Auto-limit history
        self._shuffle_enabled: bool = False
        self._repeat_mode: str = "queue"  # Default: auto-repeat queue
        self._lock = asyncio.Lock()

    @property
    def current_song(self) -> Optional[Song]:
        """Get currently playing song"""
        if 0 <= self._current_index < len(self._songs):
            return self._songs[self._current_index]
        return None

    @property
    def queue_size(self) -> int:
        """Get total queue size"""
        return len(self._songs)

    @property
    def position(self) -> tuple[int, int]:
        """Get current position as (current, total)"""
        return (self._current_index + 1, len(self._songs))

    async def size(self) -> int:
        """Get queue size"""
        async with self._lock:
            return len(self._songs)

    async def add_song(self, song: Song) -> int:
        """Add song to queue, return position"""
        async with self._lock:
            self._songs.append(song)
            return len(self._songs)

    def get_upcoming(self, limit: int = 5) -> List[Song]:
        """Get upcoming songs"""
        start = self._current_index + 1
        end = min(start + limit, len(self._songs))
        return self._songs[start:end]

    async def next_song(self) -> Optional[Song]:
        """Move to next song"""
        async with self._lock:
            if self._repeat_mode == "track":
                return self.current_song

            # Add to history if valid
            if self.current_song and self._current_index < len(self._songs):
                self._history.append(self.current_song)

            self._current_index += 1

            # Handle queue end
            if self._current_index >= len(self._songs):
                if self._repeat_mode == "queue" and self._songs:
                    self._current_index = 0
                    return self.current_song
                # No more songs
                self._current_index = max(0, len(self._songs) - 1) if self._songs else 0
                return None

            return self.current_song

    async def previous_song(self) -> Optional[Song]:
        """Move to previous song"""
        async with self._lock:
            # Try history first
            if self._history:
                prev_song = self._history.pop()
                try:
                    self._current_index = self._songs.index(prev_song)
                    return prev_song
                except ValueError:
                    # Not in queue, add it back
                    self._songs.insert(self._current_index, prev_song)
                    return prev_song

            # No history, go to previous in queue
            if self._current_index > 0:
                self._current_index -= 1
                return self.current_song

            return None

    async def clear(self) -> None:
        """Clear the entire queue"""
        async with self._lock:
            self._songs.clear()
            self._current_index = 0
            self._history.clear()

    async def remove_at(self, index: int) -> bool:
        """Remove song at index"""
        async with self._lock:
            if 0 <= index < len(self._songs):
                self._songs.pop(index)
                if index < self._current_index:
                    self._current_index -= 1
                elif index == self._current_index and self._current_index >= len(
                    self._songs
                ):
                    self._current_index = 0
                return True
            return False

    def get_all_songs(self) -> List[Song]:
        """Get all songs in the queue"""
        return self._songs.copy()

    def find_song_by_input(self, original_input: str) -> Optional[Song]:
        """Find song in queue by original input"""
        return next(
            (song for song in self._songs if song.original_input == original_input),
            None,
        )

    def set_repeat_mode(self, mode: str) -> bool:
        """Set repeat mode (off, track, queue)"""
        mode_lower = mode.lower()
        if mode_lower in ("off", "track", "queue"):
            self._repeat_mode = mode_lower
            return True
        return False

    def get_repeat_mode(self) -> str:
        """Get current repeat mode"""
        return self._repeat_mode
