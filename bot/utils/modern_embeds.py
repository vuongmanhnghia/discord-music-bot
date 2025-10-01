"""
Modern Embed Factory - Phong cách embed mới
Tập trung vào UX tốt hơn với thông tin rõ ràng, hướng dẫn cụ thể
"""

import discord
from typing import Optional, List, Dict, Any


class ModernEmbedFactory:
    """Factory class for creating modern, user-friendly embeds"""

    @staticmethod
    def create_empty_state_embed(
        title: str,
        description: str,
        suggestions: List[str],
        footer: str,
        color: discord.Color = discord.Color.blue(),
    ) -> discord.Embed:
        """
        Create an embed for empty states (empty queue, no playlists, etc.)

        Args:
            title: Main title describing the empty state
            description: Detailed explanation and next steps
            suggestions: List of actionable suggestions
            footer: Call-to-action message
            color: Embed color (default: blue)
        """
        embed = discord.Embed(title=title, description=description, color=color)

        if suggestions:
            suggestion_text = "\n".join([f"▸ {s}" for s in suggestions])
            embed.add_field(name="Gợi ý", value=suggestion_text, inline=False)

        embed.set_footer(text=footer)
        return embed

    @staticmethod
    def create_success_embed(
        title: str,
        description: str,
        details: Optional[Dict[str, str]] = None,
        footer: Optional[str] = None,
        color: discord.Color = discord.Color.green(),
    ) -> discord.Embed:
        """
        Create a success embed with optional details

        Args:
            title: Success message title
            description: Detailed success message
            details: Optional dict of field_name: field_value for additional info
            footer: Optional footer text
            color: Embed color (default: green)
        """
        embed = discord.Embed(title=title, description=description, color=color)

        if details:
            for name, value in details.items():
                embed.add_field(name=name, value=value, inline=False)

        if footer:
            embed.set_footer(text=footer)

        return embed

    @staticmethod
    def create_error_embed(
        title: str,
        description: str,
        error_details: Optional[str] = None,
        suggestions: Optional[List[str]] = None,
        footer: str = "Vui lòng thử lại hoặc liên hệ admin nếu lỗi vẫn tiếp tục",
        color: discord.Color = discord.Color.red(),
    ) -> discord.Embed:
        """
        Create an error embed with helpful suggestions

        Args:
            title: Error title
            description: Main error message
            error_details: Technical error details (optional)
            suggestions: List of suggestions to fix the error
            footer: Footer with help text
            color: Embed color (default: red)
        """
        embed = discord.Embed(title=title, description=description, color=color)

        if error_details:
            embed.add_field(
                name="Chi tiết lỗi", value=f"> **```{error_details}```", inline=False
            )

        if suggestions:
            suggestion_text = "\n".join([f"▸ {s}" for s in suggestions])
            embed.add_field(name="Cách khắc phục", value=suggestion_text, inline=False)

        embed.set_footer(text=footer)
        return embed

    @staticmethod
    def create_info_embed(
        title: str,
        description: str,
        info_fields: Optional[Dict[str, str]] = None,
        footer: Optional[str] = None,
        color: discord.Color = discord.Color.blue(),
    ) -> discord.Embed:
        """
        Create an informational embed

        Args:
            title: Info title
            description: Main information
            info_fields: Optional dict of field_name: field_value
            footer: Optional footer text
            color: Embed color (default: blue)
        """
        embed = discord.Embed(title=title, description=description, color=color)

        if info_fields:
            for name, value in info_fields.items():
                embed.add_field(name=name, value=value, inline=False)

        if footer:
            embed.set_footer(text=footer)

        return embed

    @staticmethod
    def create_warning_embed(
        title: str,
        description: str,
        warning_details: Optional[str] = None,
        suggestions: Optional[List[str]] = None,
        footer: Optional[str] = None,
        color: discord.Color = discord.Color.orange(),
    ) -> discord.Embed:
        """
        Create a warning embed

        Args:
            title: Warning title
            description: Main warning message
            warning_details: Additional warning details
            suggestions: List of suggested actions
            footer: Optional footer text
            color: Embed color (default: orange)
        """
        embed = discord.Embed(title=title, description=description, color=color)

        if warning_details:
            embed.add_field(name="Chi tiết", value=warning_details, inline=False)

        if suggestions:
            suggestion_text = "\n".join([f"▸ {s}" for s in suggestions])
            embed.add_field(name="Khuyến nghị", value=suggestion_text, inline=False)

        if footer:
            embed.set_footer(text=footer)

        return embed

    @staticmethod
    def create_music_embed(
        title: str,
        description: str,
        song_info: Optional[Dict[str, str]] = None,
        player_controls: Optional[str] = None,
        footer: Optional[str] = None,
        thumbnail: Optional[str] = None,
        color: discord.Color = discord.Color.purple(),
    ) -> discord.Embed:
        """
        Create a music-related embed (now playing, added to queue, etc.)

        Args:
            title: Embed title
            description: Main message
            song_info: Dict with song details (Tên bài, Nghệ sĩ, Thời lượng, etc.)
            player_controls: Text showing available player controls
            footer: Footer text
            thumbnail: URL for thumbnail image
            color: Embed color (default: purple)
        """
        embed = discord.Embed(title=title, description=description, color=color)

        if song_info:
            for name, value in song_info.items():
                embed.add_field(name=name, value=value, inline=True)

        if player_controls:
            embed.add_field(name="Điều khiển", value=player_controls, inline=False)

        if thumbnail:
            embed.set_thumbnail(url=thumbnail)

        if footer:
            embed.set_footer(text=footer)

        return embed

    @staticmethod
    def create_progress_embed(
        title: str,
        current: int,
        total: int,
        status: str,
        additional_info: Optional[Dict[str, str]] = None,
        color: discord.Color = discord.Color.blue(),
    ) -> discord.Embed:
        """
        Create a progress tracking embed

        Args:
            title: Progress title
            current: Current progress count
            total: Total count
            status: Current status message
            additional_info: Optional additional fields
            color: Embed color (default: blue)
        """
        percentage = (current / total * 100) if total > 0 else 0
        progress_bar = ModernEmbedFactory._create_progress_bar(percentage)

        description = (
            f"{status}\n\n{progress_bar}\n**{current}/{total}** ({percentage:.1f}%)"
        )

        embed = discord.Embed(title=title, description=description, color=color)

        if additional_info:
            for name, value in additional_info.items():
                embed.add_field(name=name, value=value, inline=True)

        return embed

    @staticmethod
    def _create_progress_bar(percentage: float, length: int = 20) -> str:
        """Create a text-based progress bar"""
        filled = int(percentage / 100 * length)
        empty = length - filled
        return f"[{'█' * filled}{'░' * empty}]"

    @staticmethod
    def create_list_embed(
        title: str,
        description: str,
        items: List[str],
        footer: Optional[str] = None,
        color: discord.Color = discord.Color.blue(),
    ) -> discord.Embed:
        """
        Create an embed with a list of items

        Args:
            title: List title
            description: List description
            items: List of items to display
            footer: Optional footer
            color: Embed color (default: blue)
        """
        embed = discord.Embed(title=title, description=description, color=color)

        if items:
            items_text = "\n".join([f"▸ {item}" for item in items])
            embed.add_field(
                name=f"Tổng cộng: {len(items)} mục",
                value=items_text[:1024],  # Discord field value limit
                inline=False,
            )
        else:
            embed.add_field(
                name="Danh sách trống", value="Không có mục nào", inline=False
            )

        if footer:
            embed.set_footer(text=footer)

        return embed


# Convenience functions for common use cases


def create_empty_queue_embed() -> discord.Embed:
    """Create embed for empty queue"""
    return ModernEmbedFactory.create_empty_state_embed(
        title="Hàng đợi trống",
        description="Hiện tại không có bài hát nào trong hàng đợi.\n\nSử dụng `/play` để thêm nhạc vào hàng đợi.",
        suggestions=[
            "Dùng `/play [tên bài hát]` để phát nhạc",
            "Dùng `/playlist load [tên playlist]` để tải playlist",
        ],
        footer="Hãy thêm nhạc để bắt đầu nghe nhạc!",
    )


def create_no_playlists_embed() -> discord.Embed:
    """Create embed for no playlists"""
    return ModernEmbedFactory.create_empty_state_embed(
        title="Chưa có playlist nào",
        description="Bạn chưa tạo playlist nào.\n\nTạo playlist để lưu các bài hát yêu thích của bạn.",
        suggestions=[
            "Dùng `/playlist create [tên]` để tạo playlist mới",
            "Dùng `/playlist add [tên] [bài hát]` để thêm bài vào playlist",
        ],
        footer="Tạo playlist để quản lý nhạc dễ dàng hơn!",
    )


def create_not_in_voice_embed() -> discord.Embed:
    """Create embed for user not in voice channel"""
    return ModernEmbedFactory.create_error_embed(
        title="Không tìm thấy kênh voice",
        description="Bạn cần vào kênh voice trước khi sử dụng lệnh này.",
        suggestions=[
            "Tham gia vào một kênh voice",
            "Sử dụng lại lệnh sau khi đã vào voice channel",
        ],
        footer="Bot cần biết bạn đang ở voice channel nào để phát nhạc",
    )


def create_bot_not_playing_embed() -> discord.Embed:
    """Create embed for bot not playing"""
    return ModernEmbedFactory.create_info_embed(
        title="Không có nhạc đang phát",
        description="Hiện tại bot không phát nhạc gì.\n\nDùng `/play` để bắt đầu phát nhạc.",
        info_fields={
            "Gợi ý": "▸ `/play [tên bài]` - Phát nhạc\n▸ `/queue` - Xem hàng đợi"
        },
        footer="Hãy thêm nhạc vào hàng đợi!",
    )


def create_pause_embed() -> discord.Embed:
    """Create embed for music paused"""
    return ModernEmbedFactory.create_info_embed(
        title="Tạm dừng",
        description="Đã tạm dừng phát nhạc.",
        info_fields={"Điều khiển": "▸ `/resume` - Tiếp tục phát\n▸ `/stop` - Dừng hẳn"},
        footer="Nhạc sẽ được giữ nguyên cho đến khi bạn resume hoặc stop",
    )


def create_resume_embed() -> discord.Embed:
    """Create embed for music resumed"""
    return ModernEmbedFactory.create_success_embed(
        title="Tiếp tục phát",
        description="Đã tiếp tục phát nhạc.",
        details={"Điều khiển": "▸ `/pause` - Tạm dừng\n▸ `/skip` - Bỏ qua bài"},
        footer="Đang phát nhạc...",
    )


def create_stop_embed() -> discord.Embed:
    """Create embed for music stopped"""
    return ModernEmbedFactory.create_info_embed(
        title="Đã dừng phát nhạc",
        description="Hàng đợi đã được xóa.",
        info_fields={
            "Gợi ý": "▸ `/play [bài hát]` - Phát nhạc mới\n▸ `/playlist load [tên]` - Tải playlist"
        },
        footer="Dùng /play để bắt đầu lại",
    )


def create_skip_embed(song_title: str) -> discord.Embed:
    """Create embed for song skipped"""
    return ModernEmbedFactory.create_success_embed(
        title="Đã bỏ qua bài hát",
        description=f"**{song_title}**",
        details={"Tiếp theo": "Đang chuyển sang bài tiếp theo..."},
        footer="Dùng /nowplaying để xem bài đang phát",
    )


def create_volume_embed(volume: int) -> discord.Embed:
    """Create embed for volume changed"""
    # Volume level indicator
    if volume == 0:
        level = "Tắt tiếng"
        icon = "🔇"
    elif volume <= 33:
        level = "Thấp"
        icon = "🔉"
    elif volume <= 66:
        level = "Trung bình"
        icon = "🔊"
    else:
        level = "Cao"
        icon = "🔊"

    # Visual volume bar
    bar_length = 20
    filled = int(volume / 100 * bar_length)
    empty = bar_length - filled
    volume_bar = f"[{'█' * filled}{'░' * empty}]"

    return ModernEmbedFactory.create_success_embed(
        title=f"{icon} Âm lượng đã đặt",
        description=f"**{volume}%** ({level})\n\n{volume_bar}",
        details={"Mức": f"{level} - {volume}%"},
        footer="Dùng /volume [0-100] để thay đổi âm lượng",
    )


def create_repeat_mode_embed(mode: str) -> discord.Embed:
    """Create embed for repeat mode changed"""
    mode_config = {
        "off": {
            "icon": "📴",
            "name": "Tắt lặp",
            "description": "Phát hết hàng đợi rồi dừng",
            "detail": "Các bài sẽ phát một lần duy nhất",
        },
        "track": {
            "icon": "🔂",
            "name": "Lặp bài hiện tại",
            "description": "Lặp lại bài đang phát",
            "detail": "Bài này sẽ được lặp lại liên tục",
        },
        "queue": {
            "icon": "🔁",
            "name": "Lặp hàng đợi",
            "description": "Lặp lại toàn bộ hàng đợi",
            "detail": "Quay lại đầu hàng đợi sau khi phát hết",
        },
    }

    config = mode_config.get(mode, mode_config["off"])

    return ModernEmbedFactory.create_success_embed(
        title=f"{config['icon']} Chế độ lặp",
        description=f"**{config['name']}**\n\n{config['description']}",
        details={"Chi tiết": config["detail"]},
        footer="Dùng /repeat để thay đổi chế độ lặp",
    )


def create_already_paused_embed() -> discord.Embed:
    """Create embed for already paused"""
    return ModernEmbedFactory.create_info_embed(
        title="Nhạc đã tạm dừng rồi",
        description="Nhạc hiện đang trong trạng thái tạm dừng.",
        info_fields={
            "Gợi ý": "▸ `/resume` - Tiếp tục phát\n▸ `/stop` - Dừng hẳn và xóa queue"
        },
        footer="Dùng /resume để tiếp tục",
    )


def create_already_playing_embed() -> discord.Embed:
    """Create embed for already playing"""
    return ModernEmbedFactory.create_info_embed(
        title="Nhạc đang phát rồi",
        description="Nhạc hiện đang được phát.",
        info_fields={
            "Gợi ý": "▸ `/pause` - Tạm dừng\n▸ `/skip` - Bỏ qua bài\n▸ `/nowplaying` - Xem thông tin bài hát"
        },
        footer="Nhạc đang phát...",
    )


# ============ Playlist-specific embeds ============


def create_playlist_created_embed(playlist_name: str) -> discord.Embed:
    """Create embed for playlist created"""
    return ModernEmbedFactory.create_success_embed(
        title="Playlist đã tạo",
        description=f"Playlist **{playlist_name}** đã được tạo thành công!",
        details={"Tên playlist": playlist_name, "Số bài hát": "0 bài (playlist trống)"},
        footer="Dùng /playlist add để thêm nhạc vào playlist",
    )


def create_playlist_deleted_embed(playlist_name: str, song_count: int) -> discord.Embed:
    """Create embed for playlist deleted"""
    return ModernEmbedFactory.create_success_embed(
        title="Playlist đã xóa",
        description=f"Playlist **{playlist_name}** đã được xóa.",
        details={"Đã xóa": f"{song_count} bài hát"},
        footer="Dùng /playlist list để xem các playlist còn lại",
    )


def create_song_added_to_playlist_embed(
    song_title: str, playlist_name: str, total_songs: int
) -> discord.Embed:
    """Create embed for song added to playlist"""
    return ModernEmbedFactory.create_success_embed(
        title="Đã thêm vào playlist",
        description=f"**{song_title}**",
        details={"Playlist": playlist_name, "Tổng số bài": f"{total_songs} bài"},
        footer="Dùng /playlist show để xem chi tiết playlist",
    )


def create_song_removed_from_playlist_embed(
    position: int, playlist_name: str, remaining: int
) -> discord.Embed:
    """Create embed for song removed from playlist"""
    return ModernEmbedFactory.create_success_embed(
        title="Đã xóa khỏi playlist",
        description=f"Đã xóa bài hát ở vị trí **{position}** khỏi playlist **{playlist_name}**.",
        details={"Còn lại": f"{remaining} bài"},
        footer="Dùng /playlist show để xem playlist hiện tại",
    )


def create_playlist_loaded_embed(
    playlist_name: str, song_count: int, added_to_queue: int
) -> discord.Embed:
    """Create embed for playlist loaded to queue"""
    return ModernEmbedFactory.create_success_embed(
        title="Đã tải playlist",
        description=f"Playlist **{playlist_name}** đã được tải vào hàng đợi.",
        details={
            "Số bài trong playlist": f"{song_count} bài",
            "Đã thêm vào queue": f"{added_to_queue} bài",
        },
        footer="Dùng /queue để xem hàng đợi",
    )


def create_no_playlists_found_embed() -> discord.Embed:
    """Create embed when no playlists exist"""
    return ModernEmbedFactory.create_empty_state_embed(
        title="Chưa có playlist nào",
        description="Bạn chưa tạo playlist nào.\n\nTạo playlist để lưu các bài hát yêu thích của bạn.",
        suggestions=[
            "Dùng `/playlist create [tên]` để tạo playlist mới",
            "Dùng `/play [bài hát]` rồi `/playlist add` để lưu bài vào playlist",
        ],
        footer="Playlist giúp bạn quản lý nhạc dễ dàng hơn!",
    )


def create_playlist_not_found_embed(playlist_name: str) -> discord.Embed:
    """Create embed when playlist not found"""
    return ModernEmbedFactory.create_error_embed(
        title="Không tìm thấy playlist",
        description=f"Playlist **{playlist_name}** không tồn tại.",
        suggestions=[
            "Kiểm tra lại tên playlist",
            "Dùng `/playlist list` để xem danh sách playlist",
            "Dùng `/playlist create [tên]` để tạo playlist mới",
        ],
        footer="Tên playlist phân biệt chữ hoa/thường",
    )


def create_playlist_already_exists_embed(playlist_name: str) -> discord.Embed:
    """Create embed when playlist already exists"""
    return ModernEmbedFactory.create_error_embed(
        title="Playlist đã tồn tại",
        description=f"Playlist **{playlist_name}** đã tồn tại.",
        suggestions=[
            "Chọn tên khác cho playlist mới",
            "Dùng `/playlist add {playlist_name}` để thêm nhạc vào playlist hiện có",
            "Dùng `/playlist delete {playlist_name}` để xóa playlist cũ",
        ],
        footer="Mỗi playlist cần có tên riêng biệt",
    )


def create_youtube_playlist_loading_embed(
    playlist_title: str, video_count: int
) -> discord.Embed:
    """Create embed for YouTube playlist loading"""
    return ModernEmbedFactory.create_progress_embed(
        title="Đang tải YouTube Playlist",
        current=0,
        total=video_count,
        status=f"Đang xử lý playlist: **{playlist_title}**",
        additional_info={
            "Tổng số video": f"{video_count} videos",
            "Trạng thái": "Đang tải thông tin...",
        },
    )


def create_youtube_playlist_complete_embed(
    playlist_title: str, total_videos: int, success_count: int, failed_count: int
) -> discord.Embed:
    """Create embed for YouTube playlist loading complete"""
    description = f"Đã tải xong playlist: **{playlist_title}**"

    if failed_count > 0:
        embed = ModernEmbedFactory.create_warning_embed(
            title="Tải playlist hoàn tất (có lỗi)",
            description=description,
            warning_details=f"Một số video không thể tải được",
            suggestions=[
                f"Đã tải thành công: {success_count}/{total_videos} videos",
                f"Không thể tải: {failed_count} videos",
                "Các video lỗi có thể bị private hoặc đã xóa",
            ],
            footer="Hàng đợi đã được cập nhật với các bài hát hợp lệ",
        )
    else:
        embed = ModernEmbedFactory.create_success_embed(
            title="Tải playlist thành công",
            description=description,
            details={
                "Tổng số video": f"{total_videos} videos",
                "Đã thêm vào queue": f"{success_count} bài",
            },
            footer="Dùng /queue để xem hàng đợi",
        )

    return embed


# ============ Basic command embeds ============


def create_ping_embed(discord_latency: int, response_time: int) -> discord.Embed:
    """Create embed for ping command"""
    # Determine status based on latency
    if discord_latency < 100:
        status = "Tuyệt vời"
        color = discord.Color.green()
    elif discord_latency < 200:
        status = "Tốt"
        color = discord.Color.blue()
    elif discord_latency < 300:
        status = "Bình thường"
        color = discord.Color.orange()
    else:
        status = "Chậm"
        color = discord.Color.red()

    return ModernEmbedFactory.create_info_embed(
        title="🏓 Pong!",
        description=f"Độ trễ bot: **{status}**",
        info_fields={
            "Discord Latency": f"{discord_latency}ms",
            "Response Time": f"{response_time}ms",
        },
        footer=f"Trạng thái kết nối: {status}",
        color=color,
    )


def create_join_success_embed(channel_name: str) -> discord.Embed:
    """Create embed for successful voice join"""
    return ModernEmbedFactory.create_success_embed(
        title="Đã kết nối voice",
        description=f"Bot đã tham gia kênh **{channel_name}**",
        details={
            "Gợi ý": "▸ Dùng `/play` để phát nhạc\n▸ Dùng `/queue` để xem hàng đợi"
        },
        footer="Bot sẵn sàng phát nhạc!",
    )


def create_already_in_channel_embed(channel_name: str) -> discord.Embed:
    """Create embed when already in voice channel"""
    return ModernEmbedFactory.create_info_embed(
        title="Đã ở trong kênh voice",
        description=f"Bot đang ở trong kênh **{channel_name}**",
        info_fields={
            "Gợi ý": "▸ Dùng `/play` để phát nhạc\n▸ Dùng `/leave` để bot rời khỏi kênh"
        },
        footer="Bot đang sẵn sàng",
    )


def create_moved_channel_embed(channel_name: str) -> discord.Embed:
    """Create embed when moved to different channel"""
    return ModernEmbedFactory.create_success_embed(
        title="Đã chuyển kênh",
        description=f"Bot đã di chuyển sang kênh **{channel_name}**",
        footer="Bot sẵn sàng phát nhạc trong kênh mới",
    )


def create_leave_success_embed() -> discord.Embed:
    """Create embed for successful voice leave"""
    return ModernEmbedFactory.create_info_embed(
        title="Đã rời khỏi voice",
        description="Bot đã ngắt kết nối khỏi kênh voice.",
        info_fields={
            "Gợi ý": "▸ Dùng `/join` để bot quay lại\n▸ Dùng `/play` để phát nhạc và tự động join"
        },
        footer="Hẹn gặp lại!",
    )


# ============================================================================
# Advanced Commands - Help, Recovery, Stream, Switch
# ============================================================================


def create_help_embed(bot_name: str, version: str = "1.0.0") -> discord.Embed:
    """Create modern help embed with all commands"""
    embed = ModernEmbedFactory.create_info_embed(
        title=f"{bot_name} - Hướng dẫn sử dụng",
        description="",
        color=discord.Color.blue(),
    )

    # Basic commands
    basic_cmds = [
        "> **`/join`           - Tham gia voice channel**",
        "> **`/leave`          - Rời voice channel**",
        "> **`/ping`           - Kiểm tra độ trễ**",
    ]
    embed.add_field(name="Lệnh cơ bản", value="\n".join(basic_cmds), inline=False)

    # Playback commands
    playback_cmds = [
        "> **`/play`           - Phát từ playlist hiện tại**",
        "> **`/play <query>`   - Phát nhạc từ URL/tìm kiếm**",
        "> **`/aplay <url>`    - Phát toàn bộ playlist từ URL (Async)**",
        "> **`/pause`          - Tạm dừng phát**",
        "> **`/resume`         - Tiếp tục phát**",
        "> **`/skip`           - Bỏ qua bài hiện tại**",
        "> **`/stop`           - Dừng và xóa queue**",
        "> **`/volume <0-100>` - Đặt âm lượng**",
        "> **`/nowplaying`     - Hiển thị bài đang phát**",
        "> **`/repeat <mode>`  - Đặt chế độ lặp**",
    ]
    embed.add_field(name="Phát nhạc", value="\n".join(playback_cmds), inline=False)

    # Queue commands
    queue_cmds = ["> **`/queue`          - Hiển thị hàng đợi**"]
    embed.add_field(name="Hàng đợi", value="\n".join(queue_cmds), inline=False)

    # Playlist commands
    playlist_cmds = [
        "> **`/create <name>`      - Tạo playlist mới**",
        "> **`/use <playlist>`     - Chọn playlist làm active**",
        "> **`/add <song>`         - Thêm vào queue & playlist + phát**",
        "> **`/remove <pl> <idx>`  - Xóa bài khỏi playlist**",
        "> **`/playlists`          - Liệt kê playlist**",
        "> **`/playlist [name]`    - Xem nội dung playlist**",
        "> **`/delete <name>`      - Xóa playlist**",
    ]
    embed.add_field(name="Playlist", value="\n".join(playlist_cmds), inline=False)

    embed.set_footer(text=f"{bot_name} - ver {version}")

    return embed


def create_recovery_status_embed(stats: Dict[str, Any]) -> discord.Embed:
    """Create embed for auto-recovery system status"""
    is_enabled = stats.get("auto_recovery_enabled", True)
    color = discord.Color.green() if is_enabled else discord.Color.red()

    embed = discord.Embed(
        title="🛠️ Auto-Recovery System Status",
        description="Hệ thống tự động xử lý lỗi và bảo trì",
        color=color,
    )

    # Status
    status = "🟢 Enabled" if is_enabled else "🔴 Disabled"
    embed.add_field(name="Trạng thái", value=status, inline=True)

    # Recovery count
    recovery_count = stats.get("recovery_count", 0)
    embed.add_field(name="Số lần recovery", value=f"{recovery_count} lần", inline=True)

    # Last recovery
    last_recovery_time = stats.get("last_recovery_time", 0)
    if last_recovery_time > 0:
        import datetime

        last_recovery = datetime.datetime.fromtimestamp(last_recovery_time)
        embed.add_field(
            name="Recovery cuối",
            value=f"{last_recovery.strftime('%H:%M:%S %d/%m')}",
            inline=True,
        )
    else:
        embed.add_field(name="Recovery cuối", value="Chưa có", inline=True)

    # Cooldown
    cooldown_remaining = stats.get("cooldown_remaining", 0)
    if cooldown_remaining > 0:
        embed.add_field(
            name="Cooldown còn lại",
            value=f"{cooldown_remaining:.0f}s",
            inline=True,
        )
    else:
        embed.add_field(name="Cooldown", value="✅ Sẵn sàng", inline=True)

    # Features info
    features_info = [
        "▸ Tự động clear cache khi gặp lỗi 403",
        "▸ Cập nhật yt-dlp tự động",
        "▸ Bảo trì định kỳ mỗi 6 giờ",
        "▸ Retry với format khác nhau",
        "▸ Cooldown 5 phút giữa các lần recovery",
    ]

    embed.add_field(name="Tính năng", value="\n".join(features_info), inline=False)

    embed.set_footer(text="Auto-recovery giúp bot tự động xử lý lỗi YouTube")

    return embed


def create_stream_status_embed(stats: Dict[str, Any]) -> discord.Embed:
    """Create embed for stream URL refresh status"""
    is_enabled = stats.get("enabled", True)
    color = discord.Color.green() if is_enabled else discord.Color.red()

    embed = discord.Embed(
        title="🔄 Stream URL Refresh Status",
        description="Hệ thống tự động refresh stream URL cho bot 24/7",
        color=color,
    )

    # Status
    status = "🟢 Enabled" if is_enabled else "🔴 Disabled"
    embed.add_field(name="Trạng thái", value=status, inline=True)

    # Refresh count
    refresh_count = stats.get("refresh_count", 0)
    embed.add_field(name="Số lần refresh", value=f"{refresh_count} lần", inline=True)

    # Cached URLs
    cached_urls = stats.get("cached_urls", 0)
    embed.add_field(name="URLs đã cache", value=f"{cached_urls} URLs", inline=True)

    # Last refresh
    last_refresh_time = stats.get("last_refresh_time", 0)
    if last_refresh_time > 0:
        import datetime

        last_refresh = datetime.datetime.fromtimestamp(last_refresh_time)
        embed.add_field(
            name="Refresh cuối",
            value=f"{last_refresh.strftime('%H:%M:%S %d/%m')}",
            inline=True,
        )
    else:
        embed.add_field(name="Refresh cuối", value="Chưa có", inline=True)

    # Time since last refresh
    time_since = stats.get("time_since_last_refresh", 0)
    if time_since > 0:
        hours = time_since / 3600
        embed.add_field(
            name="Thời gian từ lần cuối", value=f"{hours:.1f} giờ", inline=True
        )

    # Features info
    features_info = [
        "▸ Tự động refresh URL hết hạn (5 giờ)",
        "▸ Proactive refresh mỗi 6 giờ",
        "▸ Retry khi URL fail",
        "▸ Cache URL để tối ưu performance",
        "▸ Hỗ trợ bot hoạt động 24/7",
    ]

    embed.add_field(name="Tính năng", value="\n".join(features_info), inline=False)

    embed.set_footer(text="Stream refresh đảm bảo bot hoạt động liên tục")

    return embed


def create_switch_status_embed(
    is_switching: bool,
    switching_to: Optional[str] = None,
    active_playlist: Optional[str] = None,
) -> discord.Embed:
    """Create embed for playlist switch status"""
    color = discord.Color.orange() if is_switching else discord.Color.green()

    embed = discord.Embed(
        title="🔄 Playlist Switch Status",
        description="Trạng thái chuyển đổi playlist",
        color=color,
    )

    # Switch status
    status = "⏳ Switching..." if is_switching else "✅ Ready"
    embed.add_field(name="Switch Status", value=status, inline=True)

    # Switching to
    if switching_to:
        embed.add_field(name="Switching To", value=f"**{switching_to}**", inline=True)

    # Active playlist
    if active_playlist:
        embed.add_field(
            name="Active Playlist", value=f"**{active_playlist}**", inline=False
        )

    # Info
    info = [
        "▸ Switch locks auto-clear sau khi hoàn tất",
        "▸ Không cần thao tác thủ công",
        "▸ Hệ thống tự động quản lý",
    ]
    embed.add_field(name="Thông tin", value="\n".join(info), inline=False)

    embed.set_footer(text="Dùng /use <playlist> để chuyển playlist")

    return embed


def create_switch_auto_clear_embed() -> discord.Embed:
    """Create embed for switch auto-clear info"""
    return ModernEmbedFactory.create_info_embed(
        title="ℹ️ Switch Auto-Clear",
        description="Switch locks tự động clear khi playlist switch hoàn tất.",
        info_fields={
            "Thông tin": "▸ Không cần thao tác thủ công\n▸ Hệ thống tự động quản lý locks\n▸ Đảm bảo không bị deadlock"
        },
        footer="Switch system hoạt động tự động",
    )
