"""
Queue commands for the music bot
Handles queue display and management with pagination
"""

import discord
from discord import app_commands

from . import BaseCommandHandler
from ..utils.embed_factory import EmbedFactory
from ..utils.validation import ValidationUtils
from ..utils.pagination import PaginationHelper, send_paginated_embed

from ..config.constants import SUCCESS_MESSAGES, ERROR_MESSAGES


class QueueCommandHandler(BaseCommandHandler):
    """Handler for queue-related commands"""

    def setup_commands(self):
        """Setup queue commands"""

        @self.bot.tree.command(name="queue", description="Hiển thị hàng đợi hiện tại")
        async def show_queue(interaction: discord.Interaction):
            """📋 Display current queue with interactive pagination"""
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

                # Convert songs to dict format for pagination
                song_dicts = []
                for song in all_songs:
                    # Get best available title
                    title = song.display_name
                    
                    # If metadata exists and has title, use it (more detailed)
                    if song.metadata and song.metadata.title:
                        title = song.metadata.display_name
                    
                    song_dicts.append({
                        "title": title,
                        "status": song.status.value,
                    })

                # Get queue position
                queue_position = (queue_manager.position, len(all_songs))

                # Current song dict
                current_song_dict = None
                if current_song:
                    # Get best available title
                    title = current_song.display_name
                    if current_song.metadata and current_song.metadata.title:
                        title = current_song.metadata.display_name
                    
                    current_song_dict = {
                        "title": title,
                        "status": current_song.status.value,
                    }

                # Create paginated pages
                items_per_page = 10
                total_pages = max(1, (len(song_dicts) + items_per_page - 1) // items_per_page)
                pages = []

                for page_num in range(1, total_pages + 1):
                    start_idx = (page_num - 1) * items_per_page
                    end_idx = min(start_idx + items_per_page, len(song_dicts))
                    page_songs = song_dicts[start_idx:end_idx]

                    embed = PaginationHelper.create_queue_embed(
                        songs=page_songs,
                        page_num=page_num,
                        total_pages=total_pages,
                        current_song=current_song_dict,
                        queue_position=queue_position,
                    )
                    pages.append(embed)

                # Send paginated embed
                await send_paginated_embed(interaction, pages)

            except Exception as e:
                await self.handle_command_error(interaction, e, "queue")

