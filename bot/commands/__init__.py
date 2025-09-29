"""
Base command handler for the music bot
Provides common utilities and patterns for all command handlers
"""

from typing import Optional
import discord
from discord.ext import commands
from discord import app_commands

from ..pkg.logger import logger
from ..services.audio_service import audio_service
from ..services.playback import playback_service
from ..utils.embed_factory import EmbedFactory
from ..config.constants import ERROR_MESSAGES


class BaseCommandHandler:
    """Base class for all command handlers with common utilities"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def ensure_voice_connection(
        self, interaction: discord.Interaction
    ) -> Optional[discord.VoiceClient]:
        """Ensure bot is connected to voice channel, return VoiceClient if connected"""
        if not interaction.guild:
            await interaction.response.send_message(
                ERROR_MESSAGES["guild_only"], ephemeral=True
            )
            return None

        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            await interaction.response.send_message(
                ERROR_MESSAGES["not_connected"], ephemeral=True
            )
            return None

        return voice_client

    async def ensure_user_in_voice(self, interaction: discord.Interaction) -> bool:
        """Ensure user is in a voice channel"""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                ERROR_MESSAGES["voice_required"], ephemeral=True
            )
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
            await interaction.response.send_message(
                ERROR_MESSAGES["same_channel_required"], ephemeral=True
            )
            return False

        return True

    def get_queue_manager(self, guild_id: int):
        """Get queue manager for guild"""
        return audio_service.get_queue_manager(guild_id)

    def create_error_embed(self, title: str, description: str) -> discord.Embed:
        """Create standardized error embed"""
        return EmbedFactory.create_error_embed(title, description)

    def create_success_embed(self, title: str, description: str) -> discord.Embed:
        """Create standardized success embed"""
        return EmbedFactory.create_success_embed(title, description)

    def create_info_embed(self, title: str, description: str) -> discord.Embed:
        """Create standardized info embed"""
        return EmbedFactory.create_info_embed(title, description)

    async def handle_command_error(
        self, interaction: discord.Interaction, error: Exception, command_name: str
    ):
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
                await interaction.response.send_message(
                    embed=error_embed, ephemeral=True
                )
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
