"""
Queue commands for the music bot
Handles queue display and management with pagination
"""

from typing import TYPE_CHECKING
import discord

from . import BaseCommandHandler
from ..utils.discord_ui import Paginator, send_paginated_embed, create_empty_queue_embed

from ..config.constants import ERROR_MESSAGES
from ..pkg.logger import logger

if TYPE_CHECKING:
    from ..music_bot import MusicBot


class QueueCommandHandler(BaseCommandHandler):
    """Handler for queue-related commands"""

    def __init__(self, bot: "MusicBot"):
        super().__init__(bot)
        self.audio_service = bot.audio_service

    def setup_commands(self):
        """Setup queue commands"""

        @self.bot.tree.command(name="queue", description="Hiển thị hàng đợi hiện tại")
        async def show_queue(interaction: discord.Interaction):
            """📋 Display current queue with interactive pagination"""
            try:
                if not interaction.guild:
                    logger.error("Queue command invoked outside of a guild")
                    await interaction.response.send_message(ERROR_MESSAGES["guild_only"], ephemeral=True)
                    return

                tracklist = self.get_tracklist(interaction.guild.id)

                # Get tracklist info
                current_song = tracklist.current_song
                all_songs = tracklist.get_all_songs()

                if not current_song and not all_songs:
                    logger.info(f"Queue is empty in guild {interaction.guild.id}")

                    # Use modern empty queue embed
                    empty_embed = create_empty_queue_embed()
                    await interaction.response.send_message(embed=empty_embed, ephemeral=True)
                    return

                # Get queue position first
                current_pos, total_songs = tracklist.position

                # Convert songs to dict format for pagination
                # Only show songs AFTER current song (upcoming songs)
                song_dicts = []
                for idx, song in enumerate(all_songs):
                    # Skip songs before and including current song
                    if idx < current_pos:
                        continue

                    # Get best available title
                    title = song.display_name

                    # If metadata exists and has title, use it (more detailed)
                    if song.metadata and song.metadata.title:
                        title = song.metadata.display_name

                    song_dicts.append({"title": title, "status": song.status.value})

                queue_position = (current_pos, total_songs)

                # Current song dict
                current_song_dict = None
                if current_song:
                    # Get best available title
                    title = current_song.display_name
                    if current_song.metadata and current_song.metadata.title:
                        title = current_song.metadata.display_name

                    current_song_dict = {"title": title, "status": current_song.status.value}

                # Create paginated pages
                items_per_page = 10
                total_pages = max(1, (len(song_dicts) + items_per_page - 1) // items_per_page)
                pages = []

                for page_num in range(1, total_pages + 1):
                    start_idx = (page_num - 1) * items_per_page
                    end_idx = min(start_idx + items_per_page, len(song_dicts))
                    page_songs = song_dicts[start_idx:end_idx]

                    embed = Paginator.create_queue_embed(
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