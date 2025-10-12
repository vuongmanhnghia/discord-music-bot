"""Helper utilities for bot operations"""

from typing import Optional
import discord
from ..pkg.logger import logger


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
    async def handle_auto_disconnect(
        voice_client: discord.VoiceClient,
        guild_id: int,
        delay: int = 60
    ) -> bool:
        """Handle auto-disconnect after delay if still alone"""
        import asyncio
        from ..services.audio_service import audio_service
        
        logger.info(f"Bot alone in channel, waiting {delay}s before disconnect")
        await asyncio.sleep(delay)
        
        # Double-check still alone
        if VoiceStateHelper.is_alone_in_channel(voice_client):
            logger.info(f"Still alone after {delay}s, disconnecting")
            await audio_service.disconnect_from_guild(guild_id)
            return True
        
        return False


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
