"""
Advanced embed builders for complex displays
Specialized embed creation for specific bot features
"""

import discord
from typing import List, Optional, Dict, Any
from ..utils.embed_factory import EmbedFactory
from ..config.constants import EMOJIS, COLORS
from ..utils.validation import FormatUtils


class MusicEmbedBuilder:
    """Builder for music-related embeds with advanced features"""

    @staticmethod
    def create_now_playing_embed(
        song, guild_id: int, audio_player=None
    ) -> discord.Embed:
        """Create detailed now playing embed"""
        embed = EmbedFactory.create_music_embed(
            "Đang phát", song.display_name, song=song
        )

        # Add playback status
        if audio_player:
            status = "Đang phát" if audio_player.is_playing else "Tạm dừng"
            embed.add_field(name="Trạng thái", value=status, inline=True)

            volume = int(audio_player.volume * 100)
            volume_emoji = EmbedFactory.get_volume_emoji(volume)
            embed.add_field(
                name="Âm lượng", value=f"{volume_emoji} {volume}%", inline=True
            )

        return embed

    @staticmethod
    def create_play_success_embed(
        song, queue_position: Optional[int] = None
    ) -> discord.Embed:
        """Create embed for successful play request"""
        embed = EmbedFactory.create_success_embed(
            "Đã thêm vào hàng đợi", song.display_name
        )

        # Add song details
        EmbedFactory._add_song_fields(embed, song)

        # Add queue position
        if queue_position is not None:
            embed.add_field(
                name="Vị trí queue", value=f"#{queue_position}", inline=True
            )

        return embed

    @staticmethod
    def create_playlist_progress_embed(
        playlist_name: str,
        added_count: int,
        failed_count: int,
        current_index: int,
        total_count: int,
    ) -> discord.Embed:
        """Create embed showing playlist processing progress"""
        progress_bar = FormatUtils.create_progress_bar(current_index, total_count)

        embed = EmbedFactory.create_info_embed(
            "Processing YouTube Playlist", f"📋 **{playlist_name}**\n{progress_bar}"
        )

        embed.add_field(name="✅ Đã thêm", value=str(added_count), inline=True)
        embed.add_field(name="❌ Lỗi", value=str(failed_count), inline=True)
        embed.add_field(
            name="⏳ Tiến độ", value=f"{current_index}/{total_count}", inline=True
        )

        return embed


class SystemEmbedBuilder:
    """Builder for system and admin embeds"""

    @staticmethod
    def create_resource_stats_embed(stats: Dict[str, Any]) -> discord.Embed:
        """Create resource statistics embed"""
        embed = EmbedFactory.create_info_embed(
            "Bot Resource Statistics", "Thống kê sử dụng tài nguyên và hiệu suất"
        )

        # Connection Stats
        embed.add_field(
            name="🎵 Audio Connections",
            value=f"**Active Voice Clients**: {stats.get('total_voice_clients', 0)}\n"
            f"**Audio Players**: {stats.get('total_audio_players', 0)}\n"
            f"**Queue Managers**: {stats.get('total_queue_managers', 0)}",
            inline=True,
        )

        # Cache Stats
        cache_hit_rate = stats.get("cache_hit_rate", 0)
        embed.add_field(
            name="💾 Cache Performance",
            value=f"**Cache Size**: {stats.get('cache_size', 0)}\n"
            f"**Hit Rate**: {cache_hit_rate:.1f}%\n"
            f"**Cache Hits**: {stats.get('cache_hits', 0)}",
            inline=True,
        )

        # Status indicator
        active_connections = stats.get("active_connections", 0)
        status_emoji = "🟢" if active_connections < 8 else "🟡"
        status_text = "Healthy" if active_connections < 8 else "High Usage"

        embed.add_field(
            name="📊 Status",
            value=f"{status_emoji} {status_text}\n**Active**: {active_connections}",
            inline=True,
        )

        return embed

    @staticmethod
    def create_cache_performance_embed(cache_stats: Dict[str, Any]) -> discord.Embed:
        """Create cache performance embed"""
        embed = EmbedFactory.create_info_embed(
            "Smart Cache Performance", "Thống kê hiệu suất cache thông minh"
        )

        hit_rate = cache_stats.get("hit_rate", 0)
        status_emoji = "🟢" if hit_rate > 50 else "🟡"
        status_text = "Optimal" if hit_rate > 50 else "Building"

        embed.add_field(
            name="📊 Performance",
            value=f"**Hit Rate**: {hit_rate:.1f}%\n"
            f"**Total Requests**: {cache_stats.get('total_requests', 0)}\n"
            f"**Status**: {status_emoji} {status_text}",
            inline=True,
        )

        embed.add_field(
            name="💾 Storage",
            value=f"**Current Size**: {cache_stats.get('cache_size', 0)}\n"
            f"**Popular Songs**: {cache_stats.get('popular_count', 0)}",
            inline=True,
        )

        time_saved = cache_stats.get("processing_time_saved", 0)
        embed.add_field(
            name="⚡ Impact",
            value=f"**Time Saved**: {time_saved:.1f}s\n"
            f"**Processed**: {cache_stats.get('total_processed', 0)}",
            inline=True,
        )

        return embed


class HelpEmbedBuilder:
    """Builder for help and documentation embeds"""

    @staticmethod
    def create_main_help_embed(bot_name: str) -> discord.Embed:
        """Create main help embed with command categories"""
        embed = EmbedFactory.create_info_embed(
            f"{bot_name} - Hướng dẫn sử dụng",
            "Bot phát nhạc Discord với AI processing và playlist management",
        )

        # Basic commands
        basic_cmds = [
            "> **`/join`** - Tham gia voice channel",
            "> **`/leave`** - Rời voice channel",
            "> **`/ping`** - Kiểm tra độ trễ",
        ]
        embed.add_field(name="🔧 Cơ bản", value="\n".join(basic_cmds), inline=False)

        # Playback commands
        playback_cmds = [
            "> **`/play`** - Phát từ playlist hiện tại",
            "> **`/play <query>`** - Phát nhạc từ URL/tìm kiếm",
            "> **`/skip`** - Bỏ qua bài hiện tại",
            "> **`/pause`** - Tạm dừng phát",
            "> **`/resume`** - Tiếp tục phát",
            "> **`/stop`** - Dừng và xóa queue",
            "> **`/volume <0-100>`** - Đặt âm lượng",
        ]
        embed.add_field(
            name="▶️ Phát nhạc", value="\n".join(playback_cmds), inline=False
        )

        # Playlist commands
        playlist_cmds = [
            "> **`/create <name>`** - Tạo playlist mới",
            "> **`/use <playlist>`** - Chọn playlist làm active",
            "> **`/add <song>`** - Thêm vào playlist hiện tại",
            "> **`/playlists`** - Liệt kê playlist",
        ]
        embed.add_field(
            name="📋 Playlist", value="\n".join(playlist_cmds), inline=False
        )

        # Features
        features = [
            "🎵 **Multi-source**: YouTube, Spotify, SoundCloud",
            "🚀 **Smart Processing**: AI-powered caching & optimization",
            "📋 **Playlist Management**: Persistent playlists",
            "⚡ **Async Processing**: Non-blocking operations",
        ]
        embed.add_field(name="✨ Tính năng", value="\n".join(features), inline=False)

        return embed

    @staticmethod
    def create_url_handling_info_embed() -> discord.Embed:
        """Create embed explaining URL handling"""
        embed = EmbedFactory.create_info_embed(
            "YouTube URL Handling", "Cách bot xử lý các loại URL YouTube khác nhau"
        )

        embed.add_field(
            name="🎵 Single Video",
            value="`youtube.com/watch?v=xyz&list=abc`\n→ Chỉ phát **1 bài hát**",
            inline=False,
        )

        embed.add_field(
            name="📋 Full Playlist",
            value="`youtube.com/playlist?list=abc`\n→ Phát **toàn bộ playlist**",
            inline=False,
        )

        embed.add_field(
            name="💡 Tip",
            value="Sử dụng `/aplay` để xử lý playlist lớn nhanh hơn với async processing!",
            inline=False,
        )

        return embed


# Extend FormatUtils with progress bar
class FormatUtils(FormatUtils):
    @staticmethod
    def create_progress_bar(current: int, total: int, length: int = 15) -> str:
        """Create a visual progress bar"""
        if total == 0:
            return "▬" * length

        filled = int((current / total) * length)
        bar = "▰" * filled + "▱" * (length - filled)
        percentage = (current / total) * 100
        return f"{bar} {percentage:.1f}%"
