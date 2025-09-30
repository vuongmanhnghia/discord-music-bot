"""
Auto Recovery Service
Automatically handles YouTube 403 errors and cache management
"""

import asyncio
import os
import shutil
import tempfile
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional
import json

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
        self._recovery_cooldown = 300  # 5 minutes between recoveries

    async def check_and_recover_if_needed(self, error_msg: str) -> bool:
        """Check if recovery is needed and perform it automatically"""
        if not self._auto_recovery_enabled:
            return False

        current_time = time.time()

        # Check cooldown
        if current_time - self._last_recovery_time < self._recovery_cooldown:
            logger.debug(
                f"Recovery cooldown active. Next recovery available in {self._recovery_cooldown - (current_time - self._last_recovery_time):.0f}s"
            )
            return False

        # Check if error matches patterns requiring recovery
        error_type = self._classify_error(error_msg)

        if error_type in ["403_forbidden", "rate_limit"]:
            logger.info(f"🚨 Detected {error_type} error, initiating auto-recovery...")
            success = await self._perform_auto_recovery(error_type)

            if success:
                self._last_recovery_time = current_time
                self._recovery_count += 1
                logger.info(f"✅ Auto-recovery completed (#{self._recovery_count})")
                return True
            else:
                logger.error("❌ Auto-recovery failed")
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
            logger.info(f"🔄 Starting auto-recovery for {error_type}...")

            # Step 1: Clear yt-dlp cache
            await self._clear_ytdlp_cache()

            # Step 2: Clear bot cache
            await self._clear_bot_cache()

            # Step 3: Update yt-dlp if it's a 403 error
            if error_type == "403_forbidden":
                await self._update_ytdlp()

            # Step 4: Wait a bit for changes to take effect
            await asyncio.sleep(2)

            logger.info("✅ Auto-recovery completed successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Auto-recovery failed: {e}")
            return False

    async def _clear_ytdlp_cache(self):
        """Clear yt-dlp cache directories"""
        logger.info("🧹 Clearing yt-dlp cache...")

        def clear_cache():
            cache_dirs = []

            # Common yt-dlp cache locations
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

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        cleared_count = await loop.run_in_executor(None, clear_cache)

        if cleared_count > 0:
            logger.info(f"   ✅ Cleared {cleared_count} yt-dlp cache directories")
        else:
            logger.debug("   ℹ️ No yt-dlp cache directories found")

    async def _clear_bot_cache(self):
        """Clear bot-specific cache"""
        logger.info("🤖 Clearing bot cache...")

        def clear_cache():
            bot_root = Path(__file__).parent.parent.parent  # Navigate to bot root
            cache_dirs = [
                bot_root / "cache",
            ]

            cleared_count = 0
            for cache_dir in cache_dirs:
                if cache_dir.exists():
                    try:
                        # Clear contents but keep structure
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
            logger.info(f"   ✅ Cleared {cleared_count} bot cache files")
        else:
            logger.debug("   ℹ️ No bot cache files found")

    async def _update_ytdlp(self):
        """Update yt-dlp to latest version"""
        logger.info("🔄 Updating yt-dlp...")

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

            if process.returncode == 0:
                logger.info("   ✅ yt-dlp updated successfully")
            else:
                logger.warning(f"   ⚠️ yt-dlp update warning: {stderr.decode()}")

        except asyncio.TimeoutError:
            logger.warning("   ⏱️ yt-dlp update timed out")
        except Exception as e:
            logger.error(f"   ❌ Error updating yt-dlp: {e}")

    async def scheduled_maintenance(self):
        """Perform scheduled maintenance tasks"""
        logger.info("🔧 Running scheduled maintenance...")

        try:
            # Clear old cache files (older than 24 hours)
            await self._cleanup_old_cache()

            # Update yt-dlp weekly
            if self._should_update_ytdlp():
                await self._update_ytdlp()

            logger.info("✅ Scheduled maintenance completed")

        except Exception as e:
            logger.error(f"❌ Scheduled maintenance failed: {e}")

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
        cleaned_count = await loop.run_in_executor(None, cleanup)

        if cleaned_count > 0:
            logger.info(f"   🧹 Cleaned {cleaned_count} old cache files")

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
        logger.info("🔒 Auto-recovery disabled")

    def enable_auto_recovery(self):
        """Enable automatic recovery"""
        self._auto_recovery_enabled = True
        logger.info("🔓 Auto-recovery enabled")

    def get_recovery_stats(self) -> Dict:
        """Get recovery statistics"""
        return {
            "recovery_count": self._recovery_count,
            "last_recovery_time": self._last_recovery_time,
            "auto_recovery_enabled": self._auto_recovery_enabled,
            "cooldown_remaining": max(
                0, self._recovery_cooldown - (time.time() - self._last_recovery_time)
            ),
        }


# Global auto recovery service instance
auto_recovery_service = AutoRecoveryService()
