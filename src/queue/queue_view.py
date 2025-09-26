import discord
from discord.ui import View, Button, button
import os


class QueueView(View):
    """View for paginated queue display"""

    def __init__(self, queue, page=0, items_per_page=10):
        super().__init__(timeout=60)
        self.queue = queue
        self.page = page
        self.items_per_page = items_per_page
        self.max_pages = (len(queue) + items_per_page - 1) // items_per_page

    def get_queue_text(self):
        """Get queue text for current page"""
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        page_songs = self.queue[start:end]

        song_names = []
        for i, song_path in enumerate(page_songs, start + 1):
            filename = os.path.basename(song_path)
            name_without_ext = os.path.splitext(filename)[0]
            song_names.append(f"{i}. {name_without_ext}")

        return "\n".join(song_names)

    @button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, disabled=True)
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        if self.page > 0:
            self.page -= 1
            await self.update_embed(interaction)

    @button(label="➡️ Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        if self.page < self.max_pages - 1:
            self.page += 1
            await self.update_embed(interaction)

    async def update_embed(self, interaction: discord.Interaction):
        """Update the embed with current page"""
        queue_text = self.get_queue_text()

        embed = discord.Embed(
            title="🎵 Current Queue", description=queue_text, color=0x00FF00
        )

        embed.set_footer(
            text=f"Page {self.page + 1}/{self.max_pages} • Total: {len(self.queue)} songs"
        )

        # Update button states
        self.previous_button.disabled = self.page == 0
        self.next_button.disabled = self.page >= self.max_pages - 1

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        """Disable buttons when view times out"""
        for item in self.children:
            item.disabled = True
