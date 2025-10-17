"""
Auto Recovery Service
Automatically handles YouTube 403 errors and cache management
"""

import asyncio
import os
import shutil
import tempfile
import sys
import time
from pathlib import Path
from typing import Dict, Optional

from ..config.service_constants import ServiceConstants
from ..pkg.logger import logger


class AutoRecoveryService:
    """Automatically handle YouTube errors and cache management"""

    def __init__(self):
        self._last_recovery_time = 0
        self._recovery_count = 0
        self._error_patterns = {
            "403_forbidden": [
                "403 Forbidden",
                "Server returned 403",
                "HTTP error 403",
                "access denied",
            ],
            "rate_limit": ["rate limit", "too many requests", "429"],
            "unavailable": ["Video unavailable", "not available", "private video"],
            "extraction_error": [
                "unable to extract",
                "extraction failed",
                "no formats found",
            ],
        }
        self._auto_recovery_enabled = True
        self._recovery_cooldown = ServiceConstants.RECOVERY_COOLDOWN_SECONDS

    async def check_and_recover_if_needed(self, error_msg: str) -> bool:
        """Check if recovery is needed and perform it automatically"""
        if not self._auto_recovery_enabled:
            return False

        current_time = time.time()

        # Check cooldown
        if current_time - self._last_recovery_time < self._recovery_cooldown:
            return False

        # Check if error matches patterns requiring recovery
        error_type = self._classify_error(error_msg)

        if error_type in ["403_forbidden", "rate_limit"]:
            logger.info(f"Auto-recovery initiated for {error_type}")
            success = await self._perform_auto_recovery(error_type)

            if success:
                self._last_recovery_time = current_time
                self._recovery_count += 1
                return True
            else:
                logger.error("Auto-recovery failed")
                return False

        return False

    def _classify_error(self, error_msg: str) -> Optional[str]:
        """Classify the error type based on error message"""
        error_lower = error_msg.lower()

        for error_type, patterns in self._error_patterns.items():
            if any(pattern.lower() in error_lower for pattern in patterns):
                return error_type

        return None

    async def _perform_auto_recovery(self, error_type: str) -> bool:
        """Perform automatic recovery based on error type"""
        try:
            await self._clear_ytdlp_cache()
            await self._clear_bot_cache()

            if error_type == "403_forbidden":
                await self._update_ytdlp()

            await asyncio.sleep(ServiceConstants.RECOVERY_POST_WAIT)
            return True

        except Exception as e:
            logger.error(f"Auto-recovery error: {e}")
            return False

    async def _clear_ytdlp_cache(self):
        """Clear yt-dlp cache directories"""

        def clear_cache():
            cache_dirs = []
            home = Path.home()

            cache_dirs.extend(
                [
                    home / ".cache" / "yt-dlp",
                    home / ".cache" / "youtube-dl",
                    Path(tempfile.gettempdir()) / "yt-dlp",
                ]
            )

            # Windows cache locations
            if os.name == "nt":
                appdata = os.environ.get("APPDATA", "")
                if appdata:
                    cache_dirs.extend(
                        [
                            Path(appdata) / "yt-dlp",
                            Path(appdata) / "youtube-dl",
                        ]
                    )

            cleared_count = 0
            for cache_dir in cache_dirs:
                if cache_dir.exists():
                    try:
                        shutil.rmtree(cache_dir)
                        cleared_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to clear cache {cache_dir}: {e}")

            return cleared_count

        loop = asyncio.get_event_loop()
        cleared_count = await loop.run_in_executor(None, clear_cache)

        if cleared_count > 0:
            logger.info(f"Cleared {cleared_count} yt-dlp cache directories")

    async def _clear_bot_cache(self):
        """Clear bot-specific cache"""

        def clear_cache():
            bot_root = Path(__file__).parent.parent.parent
            cache_dirs = [bot_root / "cache"]

            cleared_count = 0
            for cache_dir in cache_dirs:
                if cache_dir.exists():
                    try:
                        for item in cache_dir.rglob("*"):
                            if item.is_file() and item.name != "cache_index.json":
                                item.unlink()
                                cleared_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to clear bot cache {cache_dir}: {e}")

            # Reset cache index
            try:
                cache_index_file = bot_root / "cache" / "songs" / "cache_index.json"
                if cache_index_file.exists():
                    cache_index_file.write_text("{}")
            except Exception as e:
                logger.warning(f"Failed to reset cache index: {e}")

            return cleared_count

        loop = asyncio.get_event_loop()
        cleared_count = await loop.run_in_executor(None, clear_cache)

        if cleared_count > 0:
            logger.info(f"Cleared {cleared_count} bot cache files")

    async def _update_ytdlp(self):
        """Update yt-dlp to latest version"""
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "yt-dlp",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)

            if process.returncode != 0:
                logger.warning(f"yt-dlp update warning: {stderr.decode()}")

        except asyncio.TimeoutError:
            logger.warning("yt-dlp update timed out")
        except Exception as e:
            logger.error(f"Error updating yt-dlp: {e}")

    async def scheduled_maintenance(self):
        """Perform scheduled maintenance tasks"""
        try:
            await self._cleanup_old_cache()

            if self._should_update_ytdlp():
                await self._update_ytdlp()

        except Exception as e:
            logger.error(f"Scheduled maintenance failed: {e}")

    async def _cleanup_old_cache(self):
        """Clean up cache files older than 24 hours"""

        def cleanup():
            bot_root = Path(__file__).parent.parent.parent
            cache_dir = bot_root / "cache" / "songs"

            if not cache_dir.exists():
                return 0

            current_time = time.time()
            cleaned_count = 0

            for cache_file in cache_dir.glob("*.json"):
                if cache_file.name == "cache_index.json":
                    continue

                try:
                    file_age = current_time - cache_file.stat().st_mtime
                    if file_age > 86400:  # 24 hours
                        cache_file.unlink()
                        cleaned_count += 1
                except Exception:
                    pass

            return cleaned_count

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, cleanup)

    def _should_update_ytdlp(self) -> bool:
        """Check if yt-dlp should be updated (weekly)"""
        # Store last update time in a simple file
        update_file = Path.home() / ".ytdlp_last_update"

        try:
            if update_file.exists():
                last_update = float(update_file.read_text().strip())
                current_time = time.time()

                # Update weekly (7 days)
                return (current_time - last_update) > (7 * 24 * 3600)
            else:
                # First time, update now
                update_file.write_text(str(time.time()))
                return True

        except Exception:
            return False

    def disable_auto_recovery(self):
        """Disable automatic recovery"""
        self._auto_recovery_enabled = False

    def enable_auto_recovery(self):
        """Enable automatic recovery"""
        self._auto_recovery_enabled = True


# Global auto recovery service instance
auto_recovery_service = AutoRecoveryService()
