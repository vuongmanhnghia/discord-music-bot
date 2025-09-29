"""
Advanced commands for the music bot
Handles help, aplay and other advanced features
"""

import discord
from discord import app_commands

from . import BaseCommandHandler
from ..config.config import config
from ..pkg.logger import logger

from ..config.constants import ERROR_MESSAGES


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
                embed = self._create_help_embed()
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

                from ..utils.youtube_playlist_handler import YouTubePlaylistHandler

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

    def _create_help_embed(self) -> discord.Embed:
        """Create comprehensive help embed"""
        embed = self.create_info_embed(
            f"❓ {config.BOT_NAME} - Hướng dẫn sử dụng",
            f"Bot phát nhạc Discord với AI processing và playlist management",
        )

        # Basic commands
        basic_cmds = [
            f"> **`/join`           - Tham gia voice channel**",
            f"> **`/leave`          - Rời voice channel**",
            f"> **`/ping`           - Kiểm tra độ trễ**",
        ]
        embed.add_field(name="Cơ bản", value="\n".join(basic_cmds), inline=False)

        # Playback commands
        playback_cmds = [
            f"> **`/play`           - Phát từ playlist hiện tại**",
            f"> **`/play <query>`   - Phát nhạc từ URL/tìm kiếm**",
            f"> **`/aplay <url>`    - Phát toàn bộ playlist từ URL (Async)**",
            f"> **`/pause`          - Tạm dừng phát**",
            f"> **`/resume`         - Tiếp tục phát**",
            f"> **`/skip`           - Bỏ qua bài hiện tại**",
            f"> **`/stop`           - Dừng và xóa queue**",
            f"> **`/volume <0-100>` - Đặt âm lượng**",
            f"> **`/nowplaying`     - Hiển thị bài đang phát**",
            f"> **`/repeat <mode>`  - Đặt chế độ lặp**",
        ]
        embed.add_field(name="Phát nhạc", value="\n".join(playback_cmds), inline=False)

        # Queue commands
        queue_cmds = [f"> **`/queue`          - Hiển thị hàng đợi**"]
        embed.add_field(name="Hàng đợi", value="\n".join(queue_cmds), inline=False)

        # Playlist commands
        playlist_cmds = [
            f"> **`/create <name>`      - Tạo playlist mới**",
            f"> **`/use <playlist>`     - Chọn playlist làm active**",
            f"> **`/add <song>`         - Thêm vào playlist hiện tại**",
            f"> **`/addto <pl> <song>`  - Thêm vào playlist chỉ định**",
            f"> **`/remove <pl> <idx>`  - Xóa bài khỏi playlist**",
            f"> **`/playlists`          - Liệt kê playlist**",
            f"> **`/playlist [name]`    - Xem nội dung playlist**",
            f"> **`/delete <name>`      - Xóa playlist**",
        ]
        embed.add_field(name="Playlist", value="\n".join(playlist_cmds), inline=False)

        # Features
        features = [
            "🎵 **Multi-source**: YouTube, Spotify, SoundCloud",
            "🚀 **Smart Processing**: AI-powered caching & optimization",
            "📋 **Playlist Management**: Persistent playlists",
            "⚡ **Async Processing**: Non-blocking operations",
            "🔍 **Smart Search**: Intelligent song matching",
        ]
        embed.add_field(
            name="Tính năng nổi bật", value="\n".join(features), inline=False
        )

        # URL handling info
        url_info = [
            "📺 **Single Video**: `youtube.com/watch?v=xyz&list=abc` → 1 bài",
            "📋 **Full Playlist**: `youtube.com/playlist?list=abc` → toàn bộ playlist",
        ]
        embed.add_field(
            name="Xử lý URL YouTube", value="\n".join(url_info), inline=False
        )

        embed.set_footer(text=f"Bot version: {getattr(config, 'VERSION', '1.0.0')}")

        return embed
