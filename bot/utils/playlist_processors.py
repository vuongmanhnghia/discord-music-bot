"""Playlist processing utilities for bot"""

from typing import List, Optional
import discord

from ..pkg.logger import logger
from ..services.playback import playback_service


class PlaylistProcessor:
    """Handles YouTube playlist video processing"""

    @staticmethod
    async def process_playlist_videos(
        video_urls: List[str],
        playlist_message: str,
        guild_id: int,
        requested_by: str,
        limit: int = 50,
    ) -> discord.Embed:
        """Process YouTube playlist videos with progress tracking"""
        added_count = 0
        failed_count = 0

        # Process videos in batches
        for i, video_url in enumerate(video_urls[:limit]):
            try:
                success, _, song = await playback_service.play_request_cached(
                    user_input=video_url,
                    guild_id=guild_id,
                    requested_by=requested_by,
                    auto_play=(i == 0),  # Auto-play first song only
                )

                if success:
                    added_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                logger.error(f"Error processing playlist video {video_url}: {e}")
                failed_count += 1

        # Return result embed
        return discord.Embed(
            title="✅ YouTube Playlist Processed",
            description=(
                f"📋 **{playlist_message}**\n"
                f"✅ Successfully added: {added_count} videos\n"
                f"❌ Failed: {failed_count} videos"
            ),
            color=discord.Color.green() if added_count > 0 else discord.Color.red(),
        )

    @staticmethod
    async def process_add_playlist_videos(
        video_urls: List[str],
        playlist_message: str,
        active_playlist: str,
        guild_id: int,
        requested_by: str,
        playlist_service,
        limit: int = 50,
    ) -> discord.Embed:
        """Process YouTube playlist videos for /add command"""
        added_count = 0
        failed_count = 0
        playlist_added_count = 0

        # Process videos in batches
        for video_url in video_urls[:limit]:
            try:
                # Process song without auto-play
                success, _, song = await playback_service.play_request_cached(
                    user_input=video_url,
                    guild_id=guild_id,
                    requested_by=requested_by,
                    auto_play=False,
                )

                if success and song:
                    added_count += 1

                    # Add to playlist
                    title = song.metadata.title if song.metadata else video_url
                    playlist_success, _ = playlist_service.add_to_playlist(
                        active_playlist,
                        song.original_input,
                        song.source_type,
                        title,
                    )

                    if playlist_success:
                        playlist_added_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                logger.error(f"Error processing add playlist video {video_url}: {e}")
                failed_count += 1

        # Return result embed
        return discord.Embed(
            title=f"✅ Đã cập nhật playlist {active_playlist}",
            description=(
                f"📋 **{playlist_message}**\n"
                f"✅ Đã thêm vào queue: {added_count} bài hát\n"
                f"✅ Đã thêm vào playlist: {playlist_added_count} bài hát\n"
                f"❌ Lỗi: {failed_count} bài hát"
            ),
            color=discord.Color.green() if added_count > 0 else discord.Color.red(),
        )


class PlaylistResultFactory:
    """Factory for creating playlist result embeds"""

    @staticmethod
    def create_use_result(
        success: bool,
        message: str,
        playlist_name: str,
        guild_id: int,
        active_playlists: dict,
    ) -> discord.Embed:
        """Create result embed for /use command"""
        if success:
            active_playlists[guild_id] = playlist_name

            if "is empty" in message:
                return discord.Embed(
                    title="✅ Đã chọn playlist trống",
                    description=(
                        f"📋 **{playlist_name}** đã được đặt làm playlist hiện tại\n"
                        f"⚠️ {message}\n"
                        f"💡 Sử dụng `/add <song>` để thêm bài hát"
                    ),
                    color=discord.Color.orange(),
                )
            else:
                return discord.Embed(
                    title="✅ Đã load playlist",
                    description=message,
                    color=discord.Color.green(),
                )
        else:
            return discord.Embed(
                title="❌ Lỗi",
                description=message,
                color=discord.Color.red(),
            )

    @staticmethod
    def create_lazy_use_result(
        success: bool,
        message: str,
        playlist_name: str,
        guild_id: int,
        job_id: Optional[str],
        active_playlists: dict,
    ) -> discord.Embed:
        """Create result embed for lazy /use command"""
        if success:
            active_playlists[guild_id] = playlist_name

            embed = discord.Embed(
                title="Kích hoạt playlist thành công",
                description=f"**{playlist_name} đã được load**\n\n{message}\n\n",
                color=discord.Color.blue(),
            )

            if job_id:
                embed.add_field(
                    name="📊 Lazy Loading Info",
                    value=(
                        f"**Job ID**: `{job_id}`\n"
                        f"**Strategy**: Load 3 songs immediately, rest in background\n"
                        f"**Progress**: Use `/playlist_status` to check progress"
                    ),
                    inline=False,
                )

            embed.set_footer(
                text="💡 First few songs load instantly, others process in background"
            )
        else:
            embed = discord.Embed(
                title="❌ Lỗi",
                description=message,
                color=discord.Color.red(),
            )

        return embed
