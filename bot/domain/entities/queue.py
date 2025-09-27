from __future__ import annotations
from typing import Optional, List

from .song import Song

class QueueManager:
    """Manages song queue with rich functionality"""

    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self._songs: List[Song] = []
        self._current_index: int = 0
        self._history: List[Song] = []
        self._shuffle_enabled: bool = False
        self._repeat_mode: str = "queue"  # Tự động lặp lại queue

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

    def add_song(self, song: Song) -> int:
        """Add song to queue, return position"""
        self._songs.append(song)
        return len(self._songs)

    def get_upcoming(self, limit: int = 5) -> List[Song]:
        """Get upcoming songs"""
        start = self._current_index + 1
        end = min(start + limit, len(self._songs))
        return self._songs[start:end]

    def next_song(self) -> Optional[Song]:
        """Move to next song"""
        if self._repeat_mode == "song":
            return self.current_song

        # Add current to history
        if self.current_song:
            self._history.append(self.current_song)
            # Limit history size
            if len(self._history) > 50:
                self._history = self._history[-50:]

        self._current_index += 1

        if self._current_index >= len(self._songs):
            if self._repeat_mode == "queue":
                self._current_index = 0
                return self.current_song
            else:
                return None

        return self.current_song

    def previous_song(self) -> Optional[Song]:
        """Move to previous song"""
        if self._history:
            # Get from history
            prev_song = self._history.pop()
            # Find it in current queue
            try:
                self._current_index = self._songs.index(prev_song)
                return prev_song
            except ValueError:
                # Not in queue anymore, add it back
                self._songs.insert(self._current_index, prev_song)
                return prev_song

        # No history, go to previous in queue
        if self._current_index > 0:
            self._current_index -= 1
            return self.current_song

        return None

    def clear(self):
        """Clear the entire queue"""
        self._songs.clear()
        self._current_index = 0
        self._history.clear()

    def remove_at(self, index: int) -> bool:
        """Remove song at index"""
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
