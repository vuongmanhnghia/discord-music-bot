"""
Advanced commands for the music bot
Handles help, aplay and other advanced features
"""

from typing import TYPE_CHECKING
import discord
from discord import app_commands

from . import BaseCommandHandler
from ..config.config import config
from ..pkg.logger import logger

from ..config.constants import ERROR_MESSAGES
from ..utils.discord_ui import (
    create_help_embed,
)

if TYPE_CHECKING:
    from ..music_bot import MusicBot


class AdvancedCommandHandler(BaseCommandHandler):
    """Handler for advanced commands"""

    def __init__(self, bot: "MusicBot"):
        super().__init__(bot)
        # Utils
        self.playlist_processor = bot.playlist_processor
        self.youtube_handler = bot.youtube_handler

    def setup_commands(self):
        """Setup advanced commands"""

        @self.bot.tree.command(
            name="help",
            description=f"Hiển thị thông tin về {config.BOT_NAME} và các tính năng",
        )
        async def show_help(interaction: discord.Interaction):
            """❓ Show help information"""
            try:
                embed = create_help_embed(bot_name=config.BOT_NAME, version=config.VERSION)
                await interaction.response.send_message(embed=embed)

            except Exception as e:
                await self.handle_command_error(interaction, e, "help")

        @self.bot.tree.command(name="sync", description="[Admin] Đồng bộ slash commands với Discord")
        async def sync_commands(interaction: discord.Interaction):
            """🔄 Sync slash commands (Owner only)"""
            try:
                # Check if user is bot owner
                if interaction.user.id != self.bot.application.owner.id:
                    embed = self.create_error_embed("Permission Denied", "Only the bot owner can use this command.")
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                await interaction.response.defer(ephemeral=True)

                synced = await self.bot.tree.sync()

                embed = self.create_success_embed(
                    "✅ Commands Synced",
                    f"Successfully synced **{len(synced)}** slash commands with Discord.",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.info(f"Commands manually synced by {interaction.user}")

            except Exception as e:
                await self.handle_command_error(interaction, e, "sync")

        @self.bot.tree.command(name="aplay", description="Phát toàn bộ playlist YouTube (Async Processing)")
        @app_commands.describe(url="URL playlist YouTube")
        async def async_play_playlist(interaction: discord.Interaction, url: str):
            """🚀 Async play entire YouTube playlist"""
            try:
                if not interaction.guild:
                    await interaction.response.send_message(ERROR_MESSAGES["guild_only"], ephemeral=True)
                    return

                if not await self.ensure_user_in_voice(interaction):
                    return

                # Check if it's a valid playlist URL
                if not self.youtube_handler.is_playlist_url(url):
                    await interaction.response.send_message(ERROR_MESSAGES["invalid_playlist_url"], ephemeral=True)
                    return

                # Handle async playlist processing
                async def process_async_playlist():
                    # Extract playlist videos
                    success, video_urls, message = await self.youtube_handler.extract_playlist(url)

                    if not success or not video_urls:
                        return self.create_error_embed(ERROR_MESSAGES["playlist_extraction_error"], message)

                    return await self.playlist_processor.process_playlist_videos(
                        video_urls,
                        message,
                        interaction.guild.id,
                        str(interaction.user),
                    )

                result = await self.bot.interaction_manager.handle_long_operation(
                    interaction,
                    process_async_playlist,
                    "🚀 Processing YouTube Playlist Asynchronously...",
                )

            except Exception as e:
                await self.handle_command_error(interaction, e, "aplay")
