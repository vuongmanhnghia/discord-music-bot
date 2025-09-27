from __future__ import annotations
import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..entities.playlist import Playlist


class PlaylistRepository:
    """Repository for persisting playlists to JSON files"""

    def __init__(self, base_path: str = "playlist"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)

    def _get_file_path(self, playlist_name: str) -> Path:
        """Get file path for playlist"""
        safe_name = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in playlist_name
        )
        return self.base_path / f"{safe_name}.json"

    def save(self, playlist: Playlist) -> bool:
        """Save playlist to file"""
        try:
            file_path = self._get_file_path(playlist.name)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(playlist.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving playlist {playlist.name}: {e}")
            return False

    def load(self, playlist_name: str) -> Optional[Playlist]:
        """Load playlist from file"""
        try:
            file_path = self._get_file_path(playlist_name)
            if not file_path.exists():
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Playlist.from_dict(data)
        except Exception as e:
            print(f"Error loading playlist {playlist_name}: {e}")
            return None

    def delete(self, playlist_name: str) -> bool:
        """Delete playlist file"""
        try:
            file_path = self._get_file_path(playlist_name)
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception as e:
            print(f"Error deleting playlist {playlist_name}: {e}")
            return False

    def list_all(self) -> List[str]:
        """List all available playlists"""
        try:
            playlist_names = []
            for file_path in self.base_path.glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    playlist_names.append(data["name"])
                except Exception:
                    continue
            return sorted(playlist_names)
        except Exception as e:
            print(f"Error listing playlists: {e}")
            return []

    def exists(self, playlist_name: str) -> bool:
        """Check if playlist exists"""
        return self._get_file_path(playlist_name).exists()
