from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..valueobjects.source_type import SourceType
from ...pkg.logger import logger


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

    def has_entry(self, original_input: str) -> bool:
        """Check if an entry with the same original_input already exists"""
        return any(entry.original_input == original_input for entry in self._entries)

    def add_entry(
        self, original_input: str, source_type: SourceType, title: Optional[str] = None
    ) -> bool:
        """Add a new entry to playlist

        Returns:
            bool: True if added successfully, False if duplicate found
        """
        # Check for duplicates
        if self.has_entry(original_input):
            logger.warning(
                f"Duplicate entry '{original_input}' not added to playlist '{self.name}'"
            )
            return False

        entry = PlaylistEntry(original_input, source_type, title)
        self._entries.append(entry)
        self.updated_at = datetime.now()
        logger.info(
            f"Added entry '{title or original_input}' to playlist '{self.name}'"
        )
        return True

    def remove_entry(self, index: int) -> bool:
        """Remove entry by index"""
        if 0 <= index < len(self._entries):
            self._entries.pop(index)
            self.updated_at = datetime.now()
            logger.info(f"Removed entry at index {index} from playlist '{self.name}'")
            return True
        logger.error(
            f"Invalid index {index} for removing entry from playlist '{self.name}'"
        )
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
