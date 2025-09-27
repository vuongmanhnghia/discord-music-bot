

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List

from ..valueobjects.source_type import SourceType
from ..valueobjects.song_status import SongStatus
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