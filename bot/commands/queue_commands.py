"""
Queue commands for the music bot
Handles queue display and management
"""

import discord
from discord import app_commands

from . import BaseCommandHandler
from ..utils.embed_factory import EmbedFactory
from ..utils.validation import ValidationUtils

from ..config.constants import SUCCESS_MESSAGES, ERROR_MESSAGES


class QueueCommandHandler(BaseCommandHandler):
    """Handler for queue-related commands"""

    def setup_commands(self):
        """Setup queue commands"""

        @self.bot.tree.command(name="queue", description="Hiển thị hàng đợi hiện tại")
        @app_commands.describe(page="Trang hiển thị (mỗi trang 10 bài)")
        async def show_queue(interaction: discord.Interaction, page: int = 1):
            """📋 Display current queue"""
            try:
                if not interaction.guild:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["guild_only"], ephemeral=True
                    )
                    return

                queue_manager = self.get_queue_manager(interaction.guild.id)
                if not queue_manager:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["no_queue"], ephemeral=True
                    )
                    return

                # Get queue info
                current_song = queue_manager.current_song
                all_songs = queue_manager.get_all_songs()

                if not current_song and not all_songs:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["no_songs_in_queue"], ephemeral=True
                    )
                    return

                # Validate page number
                songs_per_page = 10
                total_pages = max(1, (len(all_songs) + songs_per_page - 1) // songs_per_page)
                is_valid, error_msg = ValidationUtils.validate_page_number(page, total_pages)
                if not is_valid:
                    await interaction.response.send_message(error_msg, ephemeral=True)
                    return
                queue_list = queue_manager.get_all_songs()

                if not current_song and not queue_list:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["no_queue"], ephemeral=True
                    )
                    return

                # Create queue embed
                embed = EmbedFactory.create_queue_embed(
                    current_song=current_song, queue_list=queue_list, page=page
                )
                await interaction.response.send_message(embed=embed)

            except Exception as e:
                await self.handle_command_error(interaction, e, "queue")
