"""
Core Utilities - Consolidated validation, helpers, and rate limiting
Merges: validation.py, bot_helpers.py, rate_limit_monitor.py
"""

import asyncio
from typing import Optional, Tuple
import discord
from datetime import datetime, timedelta
from collections import defaultdict

from ..pkg.logger import logger


# ============================================================================
# VALIDATION
# ============================================================================


class Validator:
    """Input validation utilities"""

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Check if string is a valid URL"""
        return url.startswith(("http://", "https://"))

    @staticmethod
    def is_youtube_url(url: str) -> bool:
        """Check if URL is YouTube"""
        return "youtube.com" in url or "youtu.be" in url

    @staticmethod
    def sanitize_query(query: str) -> str:
        if not query:
            return ""
        query = query.strip()
        dangerous_patterns = ["<script", "javascript:", "data:", "vbscript:"]
        query_lower = query.lower()
        for pattern in dangerous_patterns:
            if pattern in query_lower:
                query = query.replace(pattern, "")
        return query

    @staticmethod
    def validate_query_length(query: str, max_length: int = 200) -> Tuple[bool, Optional[str]]:
        if len(query) > max_length:
            return False, f"❌ Query quá dài! Giới hạn {max_length} ký tự."
        return True, None

    @staticmethod
    def validate_volume(volume: int) -> Tuple[bool, Optional[str]]:
        if not 0 <= volume <= 100:
            return False, "❌ Volume phải từ 0 đến 100!"
        return True, None

    @staticmethod
    def validate_playlist_name(name: str) -> Tuple[bool, Optional[str]]:
        if not name or not name.strip():
            return False, "❌ Tên playlist không được để trống!"
        name = name.strip()
        if len(name) > 50:
            return False, "❌ Tên playlist quá dài! Tối đa 50 ký tự."
        invalid_chars = ["/", ":", "*", "?", '"', "<", ">", "|"]
        for char in invalid_chars:
            if char in name:
                return False, f"❌ Tên playlist không được chứa ký tự '{char}'!"
        return True, None

    @staticmethod
    def validate_repeat_mode(mode: str) -> Tuple[bool, Optional[str]]:
        valid_modes = ["off", "track", "queue"]
        if mode.lower() not in valid_modes:
            return (
                False,
                f"❌ Chế độ lặp không hợp lệ! Sử dụng: {', '.join(valid_modes)}",
            )
        return True, None

    @staticmethod
    def is_spotify_url(url: str) -> bool:
        """Check if URL is Spotify"""
        return "spotify.com" in url

    @staticmethod
    def sanitize_query(query: str, max_length: int = 500) -> str:
        """Sanitize search query"""
        return query.strip()[:max_length]


# ============================================================================
# VOICE STATE HELPERS
# ============================================================================


class VoiceStateHelper:
    """Helper for voice state operations"""

    @staticmethod
    def is_alone_in_channel(voice_client: discord.VoiceClient) -> bool:
        """Check if bot is alone in voice channel"""
        if not voice_client or not voice_client.channel:
            return False

        channel = voice_client.channel
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            return False

        if not hasattr(channel, "members"):
            return False

        # Count non-bot members
        human_members = [m for m in channel.members if not m.bot]
        return len(human_members) == 0

    @staticmethod
    async def handle_auto_disconnect(voice_client: discord.VoiceClient, guild_id: int, delay: int = 60) -> bool:
        """Handle auto-disconnect after delay if still alone"""
        from ..services.audio.audio_service import audio_service

        logger.info(f"Bot alone in channel, waiting {delay}s before disconnect")
        await asyncio.sleep(delay)

        # Double-check still alone
        if VoiceStateHelper.is_alone_in_channel(voice_client):
            logger.info(f"Still alone after {delay}s, disconnecting")
            await audio_service.disconnect_from_guild(guild_id)
            return True

        return False


# ============================================================================
# ERROR EMBED FACTORY
# ============================================================================


class ErrorEmbedFactory:
    """Factory for creating error embeds"""

    @staticmethod
    def create_error_embed(title: str, description: str) -> discord.Embed:
        """Create error embed"""
        return discord.Embed(
            title=f"❌ {title}",
            description=description,
            color=discord.Color.red(),
        )

    @staticmethod
    def create_success_embed(title: str, description: str) -> discord.Embed:
        """Create success embed"""
        return discord.Embed(
            title=f"✅ {title}",
            description=description,
            color=discord.Color.green(),
        )

    @staticmethod
    def create_warning_embed(title: str, description: str) -> discord.Embed:
        """Create warning embed"""
        return discord.Embed(
            title=f"⚠️ {title}",
            description=description,
            color=discord.Color.orange(),
        )

    @staticmethod
    def create_info_embed(title: str, description: str) -> discord.Embed:
        """Create info embed"""
        return discord.Embed(
            title=f"ℹ️ {title}",
            description=description,
            color=discord.Color.blue(),
        )

    @staticmethod
    def create_rate_limit_embed(retry_after: float) -> discord.Embed:
        """Create rate limit embed"""
        return discord.Embed(
            title="⚠️ Rate Limited",
            description=f"Bot is being rate limited. Please wait {retry_after:.0f}s and try again.",
            color=discord.Color.orange(),
        )

    @staticmethod
    def create_cooldown_embed(retry_after: float) -> discord.Embed:
        """Create cooldown embed"""
        return discord.Embed(
            title="⏰ Command Cooldown",
            description=f"Command is on cooldown. Try again in {retry_after:.1f}s.",
            color=discord.Color.orange(),
        )


# ============================================================================
# RATE LIMIT MONITOR
# ============================================================================


class RateLimitMonitor:
    """Monitor and track rate limits"""

    def __init__(self):
        self._command_usage: dict[int, dict[str, list[datetime]]] = defaultdict(lambda: defaultdict(list))
        self._global_rate_limits: dict[str, datetime] = {}

    def check_rate_limit(
        self,
        guild_id: int,
        command_name: str,
        max_uses: int = 5,
        window_seconds: int = 60,
    ) -> tuple[bool, Optional[float]]:
        """
        Check if command is rate limited

        Returns:
            (is_allowed, retry_after_seconds)
        """
        now = datetime.now()
        cutoff = now - timedelta(seconds=window_seconds)

        # Clean old entries
        usage = self._command_usage[guild_id][command_name]
        self._command_usage[guild_id][command_name] = [t for t in usage if t > cutoff]

        # Check limit
        current_usage = len(self._command_usage[guild_id][command_name])
        if current_usage >= max_uses:
            oldest = min(self._command_usage[guild_id][command_name])
            retry_after = (oldest + timedelta(seconds=window_seconds) - now).total_seconds()
            return False, retry_after

        # Record usage
        self._command_usage[guild_id][command_name].append(now)
        return True, None

    def set_global_rate_limit(self, key: str, duration_seconds: float):
        """Set a global rate limit"""
        self._global_rate_limits[key] = datetime.now() + timedelta(seconds=duration_seconds)

    def check_global_rate_limit(self, key: str) -> tuple[bool, Optional[float]]:
        """Check if globally rate limited"""
        if key in self._global_rate_limits:
            now = datetime.now()
            if now < self._global_rate_limits[key]:
                retry_after = (self._global_rate_limits[key] - now).total_seconds()
                return False, retry_after
            else:
                del self._global_rate_limits[key]

        return True, None


# Global rate limit monitor instance
rate_limit_monitor = RateLimitMonitor()
