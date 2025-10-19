"""Playlist processing utilities for bot"""

from typing import List
import discord

from ..pkg.logger import logger
from ..services import playback_service


class PlaylistProcessor:
    """Handles YouTube playlist video processing"""

    @staticmethod
    async def process_playlist_videos(
        video_urls: List[str],  # Danh sách URL video từ playlist
        playlist_message: str,  # Thông điệp mô tả playlist (tên, số video)
        guild_id: int,  # ID của Discord server
        requested_by: str,  # Tên người yêu cầu
        limit: int = 50,  # Giới hạn số video xử lý (mặc định 50)
    ) -> discord.Embed:  # Trả về embed thông báo kết quả
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
