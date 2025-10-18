"""
Advanced commands for the music bot
Handles help, aplay and other advanced features
"""

import discord
from discord import app_commands

from . import BaseCommandHandler
from ..config.config import config
from ..utils.youtube import YouTubePlaylistHandler
from ..utils.playlist_processors import PlaylistProcessor

from ..config.constants import ERROR_MESSAGES
from ..utils.discord_ui import (
    create_help_embed,
)


class AdvancedCommandHandler(BaseCommandHandler):
    """Handler for advanced commands"""

    def setup_commands(self):
        """Setup advanced commands"""

        @self.bot.tree.command(
            name="help",
            description=f"Hiển thị thông tin về {config.BOT_NAME} và các tính năng",
        )
        async def show_help(interaction: discord.Interaction):
            """❓ Show help information"""
            try:
                embed = create_help_embed(
                    bot_name=config.BOT_NAME, version=config.VERSION
                )
                await interaction.response.send_message(embed=embed)

            except Exception as e:
                await self.handle_command_error(interaction, e, "help")

        @self.bot.tree.command(
            name="aplay", description="Phát toàn bộ playlist YouTube (Async Processing)"
        )
        @app_commands.describe(url="URL playlist YouTube")
        async def async_play_playlist(interaction: discord.Interaction, url: str):
            """🚀 Async play entire YouTube playlist"""
            try:
                if not interaction.guild:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["guild_only"], ephemeral=True
                    )
                    return

                if not await self.ensure_user_in_voice(interaction):
                    return

                # Check if it's a valid playlist URL
                if not YouTubePlaylistHandler.is_playlist_url(url):
                    await interaction.response.send_message(
                        ERROR_MESSAGES["invalid_playlist_url"], ephemeral=True
                    )
                    return

                # Handle async playlist processing
                async def process_async_playlist():
                    # Extract playlist videos
                    success, video_urls, message = (
                        await YouTubePlaylistHandler.extract_playlist_videos(url)
                    )

                    if not success or not video_urls:
                        return self.create_error_embed(
                            ERROR_MESSAGES["playlist_extraction_error"], message
                        )

                    return await PlaylistProcessor.process_playlist_videos(
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
