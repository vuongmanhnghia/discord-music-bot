"""
Base command handler for the music bot
Provides common utilities and patterns for all command handlers
"""

from typing import Optional, TYPE_CHECKING
import discord
from discord.ext import commands

from ..pkg.logger import logger
from ..config.constants import ERROR_MESSAGES, COLORS

from ..utils.discord_ui import EmbedFactory

if TYPE_CHECKING:
    from ..music_bot import MusicBot


class BaseCommandHandler:
    """Base class for all command handlers with common utilities"""

    def __init__(self, bot: "MusicBot"):
        self.bot = bot
        # Store commonly used services for convenience
        self.audio_service = bot.audio_service

    async def ensure_user_in_voice(self, interaction: discord.Interaction) -> bool:
        """Ensure user is in a voice channel"""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(ERROR_MESSAGES["voice_required"], ephemeral=True)
            return False
        return True

    async def ensure_same_voice_channel(self, interaction: discord.Interaction) -> bool:
        """Ensure user and bot are in the same voice channel"""
        if not interaction.guild:
            return False

        voice_client = interaction.guild.voice_client
        user_voice = interaction.user.voice

        if not voice_client or not user_voice:
            return False

        if voice_client.channel != user_voice.channel:
            await interaction.response.send_message(ERROR_MESSAGES["same_channel_required"], ephemeral=True)
            return False

        return True

    def get_tracklist(self, guild_id: int):
        """Get tracklist manager for guild"""
        return self.audio_service.get_tracklist(guild_id)

    def create_error_embed(self, title: str, description: str) -> discord.Embed:
        """Create standardized error embed"""
        return EmbedFactory.error(title=title, description=description, color=COLORS["error"])

    def create_success_embed(self, title: str, description: str) -> discord.Embed:
        """Create standardized success embed"""
        return EmbedFactory.success(title=title, description=description, color=COLORS["success"])

    def create_info_embed(self, title: str, description: str) -> discord.Embed:
        """Create standardized info embed"""
        return EmbedFactory.info(title=title, description=description, color=COLORS["info"])

    def create_warning_embed(self, title: str, description: str) -> discord.Embed:
        """Create standardized warning embed"""
        return EmbedFactory.warning(title=title, description=description, color=COLORS["warning"])

    async def handle_command_error(self, interaction: discord.Interaction, error: Exception, command_name: str):
        """Standardized error handling for commands"""
        logger.error(f"Error in /{command_name}: {error}")

        error_embed = self.create_error_embed(
            f"{ERROR_MESSAGES['command_error']} /{command_name}",
            f"Đã xảy ra lỗi: {str(error)}",
        )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")


class CommandRegistry:
    """Registry to manage and organize command handlers"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.handlers = []

    def register_handler(self, handler_class):
        """Register a command handler"""
        handler = handler_class(self.bot)
        self.handlers.append(handler)
        return handler

    def setup_all_commands(self):
        """Setup all registered command handlers"""
        for handler in self.handlers:
            if hasattr(handler, "setup_commands"):
                handler.setup_commands()
