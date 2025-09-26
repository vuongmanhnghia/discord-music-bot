"""Data models and types"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PlaylistInfo:
    """Playlist information"""

    name: str
    file_path: Path
    music_dir: Path
    song_count: int = 0

    @property
    def exists(self) -> bool:
        return self.file_path.exists()

    @property
    def music_exists(self) -> bool:
        return self.music_dir.exists() and any(self.music_dir.iterdir())


@dataclass
class GuildState:
    """Per-guild bot state"""

    guild_id: int
    active_playlist: Optional[str] = None
    queue: List[str] = None

    def __post_init__(self):
        if self.queue is None:
            self.queue = []
