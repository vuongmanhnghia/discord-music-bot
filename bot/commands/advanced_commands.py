"""
Advanced commands for the music bot
Handles help, aplay and other advanced features
"""

import discord
from discord import app_commands

from . import BaseCommandHandler
from ..config.config import config

from ..config.constants import ERROR_MESSAGES
from ..utils.discord_ui import (
    create_help_embed,
    EmbedFactory,
)

from ..services.playlist_switch import playlist_switch_manager
from ..utils.discord_ui import create_switch_status_embed


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

                from ..utils.youtube import YouTubePlaylistHandler

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

                    return await self.bot._process_playlist_videos(
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

        @self.bot.tree.command(
            name="recovery", description="Kiểm tra trạng thái auto-recovery system"
        )
        async def recovery_status(interaction: discord.Interaction):
            """🛠️ Check auto-recovery status"""
            try:
                from ..services.auto_recovery import auto_recovery_service

                stats = auto_recovery_service.get_recovery_stats()
                embed = EmbedFactory.info(stats)
                await interaction.response.send_message(embed=embed)

            except Exception as e:
                await self.handle_command_error(interaction, e, "recovery")

        @self.bot.tree.command(
            name="stream", description="Kiểm tra trạng thái stream URL refresh system"
        )
        async def stream_status(interaction: discord.Interaction):
            """🔄 Check stream refresh status"""
            try:
                from ..services.stream_refresh import stream_refresh_service

                stats = stream_refresh_service.get_refresh_stats()
                embed = EmbedFactory.info(stats)
                await interaction.response.send_message(embed=embed)

            except Exception as e:
                await self.handle_command_error(interaction, e, "stream")

        @self.bot.tree.command(
            name="switch", description="Kiểm tra trạng thái playlist switch system"
        )
        @app_commands.describe(action="Action: status, clear, settings")
        async def switch_status(
            interaction: discord.Interaction, action: str = "status"
        ):
            """🔄 Kiểm tra trạng thái playlist switch system"""
            try:
                if not interaction.guild:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["guild_only"], ephemeral=True
                    )
                    return

                await interaction.response.defer()

                if action == "status":
                    # Show current switch status

                    guild_id = interaction.guild.id
                    is_switching = playlist_switch_manager.is_switching(guild_id)
                    switching_to = playlist_switch_manager.get_switching_playlist(
                        guild_id
                    )

                    # Get current active playlist
                    active_playlist = getattr(self.bot, "active_playlists", {}).get(
                        guild_id
                    )

                    # Use standardized embed function
                    embed = create_switch_status_embed(
                        is_switching=is_switching,
                        switching_to=switching_to,
                        active_playlist=active_playlist,
                    )

                    await interaction.followup.send(embed=embed)

                elif action == "clear":
                    # Note: Switch locks auto-clear after switch completes
                    # This action is kept for compatibility but does nothing
                    await interaction.followup.send(
                        "ℹ️ Switch locks auto-clear automatically. No manual action needed."
                    )

                else:
                    await interaction.followup.send(
                        "❌ Invalid action. Use: status, clear"
                    )

            except Exception as e:
                await self.handle_command_error(interaction, e, "switch")
