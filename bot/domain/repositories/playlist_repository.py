from __future__ import annotations
import json
import os
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..entities.playlist import Playlist
from ...pkg.logger import logger


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
        """Save playlist to file with atomic write"""
        try:
            file_path = self._get_file_path(playlist.name)
            
            # Create backup if file exists
            if file_path.exists():
                backup_path = file_path.with_suffix('.json.backup')
                try:
                    shutil.copy2(file_path, backup_path)
                except Exception as backup_error:
                    logger.warning(f"Could not create backup: {backup_error}")
            
            # Atomic write using temp file
            temp_path = file_path.with_suffix('.json.tmp')
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(playlist.to_dict(), f, indent=2, ensure_ascii=False)
            
            # Rename for atomicity
            temp_path.replace(file_path)
            
            logger.info(f"✅ Saved playlist: {playlist.name}")
            return True
        except PermissionError as e:
            logger.error(f"❌ Permission denied saving playlist {playlist.name}: {e}")
            return False
        except OSError as e:
            logger.error(f"❌ Disk error saving playlist {playlist.name}: {e}")
            return False
        except Exception as e:
            logger.exception(f"❌ Unexpected error saving playlist {playlist.name}")
            return False

    def load(self, playlist_name: str) -> Optional[Playlist]:
        """Load playlist from file"""
        try:
            file_path = self._get_file_path(playlist_name)
            if not file_path.exists():
                logger.debug(f"Playlist file not found: {playlist_name}")
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            logger.info(f"✅ Loaded playlist: {playlist_name}")
            return Playlist.from_dict(data)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in playlist {playlist_name}: {e}")
            return None
        except OSError as e:
            logger.error(f"❌ Error reading playlist {playlist_name}: {e}")
            return None
        except Exception as e:
            logger.exception(f"❌ Unexpected error loading playlist {playlist_name}")
            return None

    def delete(self, playlist_name: str) -> bool:
        """Delete playlist file"""
        try:
            file_path = self._get_file_path(playlist_name)
            if not file_path.exists():
                logger.warning(f"Playlist file not found: {playlist_name}")
                return False
            
            # Move to trash instead of permanent delete
            trash_path = file_path.with_suffix('.json.deleted')
            file_path.rename(trash_path)
            
            logger.info(f"🗑️ Deleted playlist: {playlist_name}")
            return True
        except OSError as e:
            logger.error(f"❌ Error deleting playlist {playlist_name}: {e}")
            return False
        except Exception as e:
            logger.exception(f"❌ Unexpected error deleting playlist {playlist_name}")
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
                except Exception as e:
                    logger.warning(f"Could not read playlist {file_path}: {e}")
                    continue
            return sorted(playlist_names)
        except Exception as e:
            logger.error(f"❌ Error listing playlists: {e}")
            return []

    def exists(self, playlist_name: str) -> bool:
        """Check if playlist exists"""
        return self._get_file_path(playlist_name).exists()
