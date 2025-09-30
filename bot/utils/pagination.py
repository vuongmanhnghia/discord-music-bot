"""
Pagination utility for Discord embeds with button controls
Provides beautiful, interactive pagination for playlists and queues
"""

import discord
from discord.ui import Button, View
from typing import List, Callable, Optional
import asyncio

from ..pkg.logger import logger


class PaginationView(View):
    """Interactive pagination view with navigation buttons"""

    def __init__(
        self,
        pages: List[discord.Embed],
        author_id: int,
        timeout: float = 180.0,
    ):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.author_id = author_id
        self.current_page = 0
        self.message: Optional[discord.Message] = None

        # Update button states
        self._update_buttons()

    def _update_buttons(self):
        """Update button states based on current page"""
        # Disable first/previous on first page
        self.children[0].disabled = self.current_page == 0  # First
        self.children[1].disabled = self.current_page == 0  # Previous

        # Disable next/last on last page
        self.children[3].disabled = self.current_page >= len(self.pages) - 1  # Next
        self.children[4].disabled = self.current_page >= len(self.pages) - 1  # Last

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the command author to use buttons"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Chỉ người dùng lệnh mới có thể điều khiển!",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.primary)
    async def first_page(
        self, interaction: discord.Interaction, button: Button
    ):
        """Go to first page"""
        self.current_page = 0
        self._update_buttons()
        await interaction.response.edit_message(
            embed=self.pages[self.current_page], view=self
        )

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.primary)
    async def previous_page(
        self, interaction: discord.Interaction, button: Button
    ):
        """Go to previous page"""
        self.current_page = max(0, self.current_page - 1)
        self._update_buttons()
        await interaction.response.edit_message(
            embed=self.pages[self.current_page], view=self
        )

    @discord.ui.button(emoji="🗑️", style=discord.ButtonStyle.danger)
    async def delete_message(
        self, interaction: discord.Interaction, button: Button
    ):
        """Delete the pagination message"""
        await interaction.response.defer()
        if self.message:
            try:
                await self.message.delete()
            except discord.NotFound:
                pass

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.primary)
    async def next_page(
        self, interaction: discord.Interaction, button: Button
    ):
        """Go to next page"""
        self.current_page = min(len(self.pages) - 1, self.current_page + 1)
        self._update_buttons()
        await interaction.response.edit_message(
            embed=self.pages[self.current_page], view=self
        )

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.primary)
    async def last_page(
        self, interaction: discord.Interaction, button: Button
    ):
        """Go to last page"""
        self.current_page = len(self.pages) - 1
        self._update_buttons()
        await interaction.response.edit_message(
            embed=self.pages[self.current_page], view=self
        )

    async def on_timeout(self):
        """Disable all buttons when view times out"""
        for child in self.children:
            child.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass


class PaginationHelper:
    """Helper class for creating paginated embeds"""

    @staticmethod
    def create_pages(
        items: List[dict],
        items_per_page: int,
        create_embed_func: Callable[[List[dict], int, int], discord.Embed],
        title: str,
    ) -> List[discord.Embed]:
        """
        Create paginated embeds from items

        Args:
            items: List of items to paginate
            items_per_page: Number of items per page
            create_embed_func: Function to create embed for a page
            title: Base title for embeds

        Returns:
            List of Discord embeds
        """
        if not items:
            empty_embed = discord.Embed(
                title=title,
                description="Không có dữ liệu để hiển thị",
                color=discord.Color.greyple(),
            )
            return [empty_embed]

        total_pages = (len(items) + items_per_page - 1) // items_per_page
        pages = []

        for page_num in range(total_pages):
            start_idx = page_num * items_per_page
            end_idx = min(start_idx + items_per_page, len(items))
            page_items = items[start_idx:end_idx]

            embed = create_embed_func(page_items, page_num + 1, total_pages)
            pages.append(embed)

        return pages

    @staticmethod
    def create_queue_embed(
        songs: List[dict],
        page_num: int,
        total_pages: int,
        current_song: Optional[dict] = None,
        queue_position: tuple = (0, 0),
    ) -> discord.Embed:
        """Create embed for queue page"""
        embed = discord.Embed(
            title=f"🎵 Hàng Đợi Phát Nhạc",
            color=discord.Color.blue(),
        )

        # Add current song if exists
        if current_song:
            current_title = current_song.get("title", "Unknown")
            embed.add_field(
                name="▶️ Đang phát",
                value=f"**{current_title}**\n`Vị trí: {queue_position[0]}/{queue_position[1]}`",
                inline=False,
            )

        # Add songs for this page
        if songs:
            songs_text = ""
            for i, song in enumerate(songs, 1):
                # Calculate actual position in queue
                actual_pos = (page_num - 1) * 10 + i + queue_position[0]
                title = song.get("title", song.get("display_name", "Unknown"))

                # Truncate if too long
                if len(title) > 50:
                    title = title[:47] + "..."

                status = song.get("status", "unknown")
                status_emoji = {
                    "ready": "✅",
                    "processing": "⏳",
                    "failed": "❌",
                    "pending": "⏸️",
                }.get(status, "❓")

                songs_text += f"`{actual_pos}.` {status_emoji} **{title}**\n"

            embed.add_field(
                name=f"📋 Danh sách ({len(songs)} bài)",
                value=songs_text or "Trống",
                inline=False,
            )

        embed.set_footer(text=f"Trang {page_num}/{total_pages} • Tổng cộng {queue_position[1]} bài")
        return embed

    @staticmethod
    def create_playlist_embed(
        songs: List[dict],
        page_num: int,
        total_pages: int,
        playlist_name: str,
        total_songs: int,
    ) -> discord.Embed:
        """Create embed for playlist page"""
        embed = discord.Embed(
            title=f"📋 Playlist: {playlist_name}",
            color=discord.Color.green(),
        )

        if songs:
            songs_text = ""
            start_idx = (page_num - 1) * 10

            for i, song in enumerate(songs, 1):
                actual_pos = start_idx + i
                title = song.get("title", song.get("input", "Unknown"))
                source = song.get("source_type", "Unknown")

                # Truncate if too long
                if len(title) > 50:
                    title = title[:47] + "..."

                songs_text += f"`{actual_pos}.` **{title}** `({source})`\n"

            embed.add_field(
                name=f"🎵 Nội dung",
                value=songs_text or "Trống",
                inline=False,
            )

        embed.set_footer(text=f"Trang {page_num}/{total_pages} • Tổng cộng {total_songs} bài")
        return embed


async def send_paginated_embed(
    interaction: discord.Interaction,
    pages: List[discord.Embed],
    ephemeral: bool = False,
) -> Optional[discord.Message]:
    """
    Send paginated embed with navigation buttons

    Args:
        interaction: Discord interaction
        pages: List of embed pages
        ephemeral: Whether message should be ephemeral

    Returns:
        The sent message or None
    """
    if not pages:
        await interaction.response.send_message(
            "❌ Không có dữ liệu để hiển thị", ephemeral=True
        )
        return None

    # Single page, no pagination needed
    if len(pages) == 1:
        await interaction.response.send_message(embed=pages[0], ephemeral=ephemeral)
        return None

    # Multiple pages, add pagination
    view = PaginationView(pages=pages, author_id=interaction.user.id)

    await interaction.response.send_message(
        embed=pages[0], view=view, ephemeral=ephemeral
    )

    # Get the message for later editing
    message = await interaction.original_response()
    view.message = message

    return message
