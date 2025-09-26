"""Clean SpotDL integration"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from .config import config
from .logger import logger


class SpotDLClient:
    """Simplified SpotDL operations"""

    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize Spotify URL"""
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    async def sync_playlist(self, playlist_name: str) -> bool:
        """Sync playlist with format protection"""
        file_path = config.playlist_path / f"{playlist_name}.spotdl"
        output_dir = config.music_path / playlist_name

        if not file_path.exists():
            logger.error(f"Playlist file not found: {file_path}")
            return False

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
    
        # Backup original format
        backup_data = None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                backup_data = json.load(f)
        except Exception as e:
            logger.warning(f"Could not backup {file_path}: {e}")

        try:
            # Run spotdl sync
            process = await asyncio.create_subprocess_exec(
                "spotdl",
                "sync",
                "--save-file",
                str(file_path),
                "--output",
                str(output_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"SpotDL sync failed: {stderr.decode()}")
                return False
            
            # Restore sync format if needed
            await self._restore_format(file_path, backup_data)

            logger.info(f"Synced playlist: {playlist_name}")
            return True

        except Exception as e:
            logger.error(f"Sync failed for {playlist_name}: {e}")
            return False

    async def download_song(self, url: str, output_dir: Path) -> bool:
        """Download single song"""
        try:
            normalized_url = self.normalize_url(url)
            
            # Count files before download
            files_before = list(output_dir.glob("*.mp3")) if output_dir.exists() else []

            process = await asyncio.create_subprocess_exec(
                "spotdl",
                "download",
                normalized_url,
                "--output",
                str(output_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()
            
            # Count files after download
            files_after = list(output_dir.glob("*.mp3")) if output_dir.exists() else []
            new_files = len(files_after) - len(files_before)

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                logger.error(f"SpotDL download failed for {url}: {error_msg}")
                return False

            if new_files > 0:
                logger.info(f"Successfully downloaded {new_files} file(s) for: {url}")
                return True
            else:
                logger.warning(f"No new files downloaded for: {url}")
                return False

        except Exception as e:
            logger.error(f"Download failed for {url}: {e}")
            return False

    def add_to_playlist(self, playlist_name: str, url: str) -> bool:
        """Add URL to playlist file"""
        file_path = config.playlist_path / f"{playlist_name}.spotdl"
        normalized_url = self.normalize_url(url)

        # Load or create playlist data
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {"type": "sync", "query": [], "songs": []}
        else:
            data = {"type": "sync", "query": [], "songs": []}

        # Ensure sync format
        if isinstance(data, list):
            data = {"type": "sync", "query": [], "songs": data}
        elif "type" not in data:
            data = {"type": "sync", "query": [], "songs": []}

        # Add URL if not exists
        if normalized_url not in data["query"]:
            data["query"].append(normalized_url)

            # Save updated file
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Added {url} to {playlist_name}")
            return True

        logger.info(f"Song already exists in {playlist_name}: {url}")
        return False

    async def _restore_format(self, file_path: Path, backup_data: Optional[dict]):
        """Restore sync format if spotdl converted it"""
        if not backup_data or not file_path.exists():
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                current_data = json.load(f)

            # If converted to array, restore sync format
            if (
                isinstance(current_data, list)
                and isinstance(backup_data, dict)
                and backup_data.get("type") == "sync"
            ):

                restored_data = {
                    "type": "sync",
                    "query": backup_data.get("query", []),
                    "songs": (
                        current_data if current_data else backup_data.get("songs", [])
                    ),
                }

                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(restored_data, f, indent=2, ensure_ascii=False)

                logger.info(f"Restored sync format for {file_path}")

        except Exception as e:
            logger.warning(f"Failed to restore format for {file_path}: {e}")


# Global instance
spotdl = SpotDLClient()
