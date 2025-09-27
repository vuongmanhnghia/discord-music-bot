from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime

from .song import Song
from ..valueobjects.source_type import SourceType


class PlaylistEntry:
    """Simple playlist entry for serialization"""

    def __init__(
        self, original_input: str, source_type: SourceType, title: Optional[str] = None
    ):
        self.original_input = original_input
        self.source_type = source_type
        self.title = title or original_input
        self.added_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_input": self.original_input,
            "source_type": self.source_type.value,
            "title": self.title,
            "added_at": self.added_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlaylistEntry":
        entry = cls(
            original_input=data["original_input"],
            source_type=SourceType(data["source_type"]),
            title=data.get("title"),
        )
        if "added_at" in data:
            entry.added_at = datetime.fromisoformat(data["added_at"])
        return entry


class Playlist:
    """Represents a playlist entity"""

    def __init__(self, name: str, entries: Optional[List[PlaylistEntry]] = None):
        self.name = name
        self._entries = entries or []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    @property
    def total_songs(self) -> int:
        """Get total number of songs in the playlist"""
        return len(self._entries)

    @property
    def entries(self) -> List[PlaylistEntry]:
        """Get all playlist entries"""
        return self._entries.copy()

    def add_entry(
        self, original_input: str, source_type: SourceType, title: Optional[str] = None
    ) -> None:
        """Add a new entry to playlist"""
        entry = PlaylistEntry(original_input, source_type, title)
        self._entries.append(entry)
        self.updated_at = datetime.now()

    def remove_entry(self, index: int) -> bool:
        """Remove entry by index"""
        if 0 <= index < len(self._entries):
            self._entries.pop(index)
            self.updated_at = datetime.now()
            return True
        return False

    def clear(self) -> None:
        """Clear all entries"""
        self._entries.clear()
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "name": self.name,
            "entries": [entry.to_dict() for entry in self._entries],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Playlist":
        """Deserialize from dictionary"""
        entries = [
            PlaylistEntry.from_dict(entry_data)
            for entry_data in data.get("entries", [])
        ]
        playlist = cls(data["name"], entries)

        if "created_at" in data:
            playlist.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            playlist.updated_at = datetime.fromisoformat(data["updated_at"])

        return playlist
