"""
Queue commands for the music bot
Handles queue display and management
"""

import discord
from discord import app_commands

from . import BaseCommandHandler
from ..pkg.logger import logger
from ..utils.embed_factory import EmbedFactory


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
                        "⛔ Lệnh này chỉ có thể sử dụng trong server!", ephemeral=True
                    )
                    return

                queue_manager = self.get_queue_manager(interaction.guild.id)
                if not queue_manager:
                    await interaction.response.send_message(
                        "❌ Không có hàng đợi nào!", ephemeral=True
                    )
                    return

                # Get queue info
                current_song = queue_manager.get_current_song()
                queue_list = queue_manager.queue
                
                if not current_song and not queue_list:
                    await interaction.response.send_message(
                        "📋 Hàng đợi trống!", ephemeral=True
                    )
                    return

                # Create queue embed
                embed = EmbedFactory.create_queue_embed(
                    current_song=current_song, 
                    queue_list=queue_list, 
                    page=page
                )
                await interaction.response.send_message(embed=embed)

            except Exception as e:
                await self.handle_command_error(interaction, e, "queue")


