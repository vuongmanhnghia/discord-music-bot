"""
Core domain models for the music bot
Clean architecture with rich domain objects
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from ..logger import logger


class SourceType(Enum):
    """Music source types"""

    SPOTIFY = "spotify"
    YOUTUBE = "youtube"
    SOUNDCLOUD = "soundcloud"
    SEARCH_QUERY = "search"


class SongStatus(Enum):
    """Song processing status"""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True)
class SongMetadata:
    """Immutable song metadata"""

    title: str
    artist: str
    duration: int  # seconds
    album: Optional[str] = None
    thumbnail_url: Optional[str] = None
    release_date: Optional[str] = None
    genres: List[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        """Human-readable song name"""
        if self.artist and self.title:
            return f"{self.artist} - {self.title}"
        return self.title

    @property
    def duration_formatted(self) -> str:
        """Duration in MM:SS format"""
        if self.duration <= 0:
            return "00:00"
        minutes, seconds = divmod(self.duration, 60)
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def search_query(self) -> str:
        """Generate search query for finding this song"""
        parts = []
        if self.artist:
            parts.append(self.artist)
        if self.title:
            parts.append(self.title)
        return " ".join(parts)


@dataclass
class Song:
    """Core Song entity - rich domain object"""

    # Identity
    original_input: str  # What user originally entered
    source_type: SourceType

    # State
    status: SongStatus = SongStatus.PENDING
    metadata: Optional[SongMetadata] = None
    stream_url: Optional[str] = None
    error_message: Optional[str] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None

    # Requester info
    requested_by: Optional[str] = None
    guild_id: Optional[int] = None

    @property
    def is_ready(self) -> bool:
        """Check if song is ready to play"""
        return (
            self.status == SongStatus.READY
            and self.metadata is not None
            and self.stream_url is not None
        )

    @property
    def display_name(self) -> str:
        """Get display name for the song"""
        if self.metadata:
            return self.metadata.display_name
        return self.original_input

    @property
    def duration_formatted(self) -> str:
        """Get formatted duration"""
        if self.metadata:
            return self.metadata.duration_formatted
        return "00:00"

    def mark_processing(self):
        """Mark song as being processed"""
        self.status = SongStatus.PROCESSING
        self.processed_at = datetime.now()

    def mark_ready(self, metadata: SongMetadata, stream_url: str):
        """Mark song as ready with metadata and stream URL"""
        self.status = SongStatus.READY
        self.metadata = metadata
        self.stream_url = stream_url
        self.error_message = None

    def mark_failed(self, error: str):
        """Mark song as failed with error message"""
        self.status = SongStatus.FAILED
        self.error_message = error
        self.processed_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "original_input": self.original_input,
            "source_type": self.source_type.value,
            "status": self.status.value,
            "metadata": (
                {
                    "title": self.metadata.title,
                    "artist": self.metadata.artist,
                    "duration": self.metadata.duration,
                    "album": self.metadata.album,
                    "thumbnail_url": self.metadata.thumbnail_url,
                }
                if self.metadata
                else None
            ),
            "stream_url": self.stream_url,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "processed_at": (
                self.processed_at.isoformat() if self.processed_at else None
            ),
            "requested_by": self.requested_by,
            "guild_id": self.guild_id,
        }


class InputAnalyzer:
    """Analyzes user input to determine source type"""

    SPOTIFY_PATTERNS = ["open.spotify.com", "spotify.com", "spotify:"]

    YOUTUBE_PATTERNS = ["youtube.com", "youtu.be", "m.youtube.com"]

    SOUNDCLOUD_PATTERNS = ["soundcloud.com"]

    @classmethod
    def analyze(cls, user_input: str) -> SourceType:
        """Analyze user input and determine source type"""
        user_input_lower = user_input.lower().strip()

        # Check if it's a URL
        if user_input_lower.startswith(("http://", "https://")):
            # Spotify URL
            if any(pattern in user_input_lower for pattern in cls.SPOTIFY_PATTERNS):
                return SourceType.SPOTIFY

            # YouTube URL
            if any(pattern in user_input_lower for pattern in cls.YOUTUBE_PATTERNS):
                return SourceType.YOUTUBE

            # SoundCloud URL
            if any(pattern in user_input_lower for pattern in cls.SOUNDCLOUD_PATTERNS):
                return SourceType.SOUNDCLOUD

        # If not a recognized URL, treat as search query
        return SourceType.SEARCH_QUERY

    @classmethod
    def create_song(
        cls, user_input: str, requested_by: str = None, guild_id: int = None
    ) -> Song:
        """Create a Song object from user input"""
        source_type = cls.analyze(user_input)

        return Song(
            original_input=user_input.strip(),
            source_type=source_type,
            requested_by=requested_by,
            guild_id=guild_id,
        )


# Abstract interfaces for processors
class SongProcessor(ABC):
    """Abstract base for song processors"""

    @abstractmethod
    async def can_process(self, song: Song) -> bool:
        """Check if this processor can handle the song"""
        pass

    @abstractmethod
    async def process(self, song: Song) -> bool:
        """Process the song and update its state"""
        pass


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
