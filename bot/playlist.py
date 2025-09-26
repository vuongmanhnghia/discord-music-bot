"""Playlist management with clean interface"""

import json
import random
from typing import List, Optional

from .config import config
from .logger import logger
from .models import PlaylistInfo


class PlaylistManager:
    AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}

    def get_playlists(self) -> List[PlaylistInfo]:
        """Get all available playlists"""
        playlists = []
        for file_path in config.playlist_path.glob("*.spotdl"):
            name = file_path.stem
            music_dir = config.music_path / name

            # Count songs
            song_count = 0
            if music_dir.exists():
                song_count = len([f for f in music_dir.iterdir() if f.suffix.lower() in self.AUDIO_EXTENSIONS])

            playlists.append(
                PlaylistInfo(
                    name=name,
                    file_path=file_path,
                    music_dir=music_dir,
                    song_count=song_count,
                )
            )

        return sorted(playlists, key=lambda p: p.name)

    def get_playlist(self, name: str) -> Optional[PlaylistInfo]:
        """Get specific playlist info"""
        file_path = config.playlist_path / f"{name}.spotdl"
        if not file_path.exists():
            return None

        music_dir = config.music_path / name
        song_count = 0
        if music_dir.exists():
            song_count = len([f for f in music_dir.iterdir() if f.suffix.lower() in self.AUDIO_EXTENSIONS])

        return PlaylistInfo(
            name=name,
            file_path=file_path,
            music_dir=music_dir,
            song_count=song_count
        )

    def get_songs(self, playlist_name: Optional[str] = None) -> List[str]:
        """Get all songs from playlist or root folder"""
        if playlist_name:
            music_dir = config.music_path / playlist_name
        else:
            music_dir = config.music_path

        if not music_dir.exists():
            return []

        songs = []
        for file_path in music_dir.iterdir():
            if file_path.suffix.lower() in self.AUDIO_EXTENSIONS:
                songs.append(str(file_path))

        random.shuffle(songs)
        return songs

    def find_song(
        self, song_name: str, playlist_name: Optional[str] = None
    ) -> Optional[str]:
        """Find specific song by name"""
        if playlist_name:
            music_dir = config.music_path / playlist_name
        else:
            music_dir = config.music_path

        if not music_dir.exists():
            return None

        # Try exact match first
        for ext in self.AUDIO_EXTENSIONS:
            song_path = music_dir / f"{song_name}{ext}"
            if song_path.exists():
                return str(song_path)

        # Try partial match
        for file_path in music_dir.iterdir():
            if (
                file_path.suffix.lower() in self.AUDIO_EXTENSIONS
                and song_name.lower() in file_path.stem.lower()
            ):
                return str(file_path)

        return None

    def create_playlist(self, name: str) -> bool:
        """Create new empty playlist"""
        # Validate name
        if not name or not name.strip():
            return False

        # Clean name (remove invalid characters)
        clean_name = "".join(c for c in name if c.isalnum() or c in "._- ").strip()
        if not clean_name:
            return False
        
        file_path = config.playlist_path / f"{clean_name}.spotdl"
        
        # Check if already exists
        if file_path.exists():
            return False

        # Create directory structure
        music_dir = config.music_path / clean_name
        music_dir.mkdir(parents=True, exist_ok=True)
        
        # Create empty playlist file in sync format
        playlist_data = {
            "type": "sync",
            "query": [],
            "songs": []
        }
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(playlist_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Created new playlist: {clean_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create playlist {clean_name}: {e}")
            return False

    def ensure_sync_format(self, playlist_name: str) -> bool:
        """Ensure playlist file is in sync format"""
        file_path = config.playlist_path / f"{playlist_name}.spotdl"
        if not file_path.exists():
            return False

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Already sync format
            if isinstance(data, dict) and data.get("type") == "sync":
                return True

            # Convert array to sync format
            if isinstance(data, list):
                sync_data = {"type": "sync", "query": [], "songs": data}

                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(sync_data, f, indent=2, ensure_ascii=False)

                logger.info(f"Converted {playlist_name} to sync format")
                return True

        except Exception as e:
            logger.error(f"Failed to fix format for {playlist_name}: {e}")
            return False, "Đã xảy ra lỗi khi sửa định dạng."

        return False


# Global instance
playlist_manager = PlaylistManager()
