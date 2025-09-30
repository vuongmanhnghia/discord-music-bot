from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

from ..valueobjects.source_type import SourceType
from ..valueobjects.song_status import SongStatus
from ..valueobjects.song_metadata import SongMetadata


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
    stream_url_timestamp: Optional[float] = (
        None  # When stream URL was obtained (for refresh)
    )

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
        
        # Publish song update event for real-time title updates
        self._publish_update_event()

    def _publish_update_event(self):
        """Publish song metadata update event"""
        try:
            from ..utils.song_events import song_event_bus, SongUpdateEvent
            import asyncio
            
            event = SongUpdateEvent(song_id=self.id, guild_id=self.guild_id)
            
            # Try to publish in event loop if available
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(song_event_bus.publish("song_metadata_updated", event))
            except RuntimeError:
                # No event loop running, skip event
                pass
        except Exception as e:
            # Don't fail if event system has issues
            from ...pkg.logger import logger
            logger.debug(f"Could not publish song update event: {e}")

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
