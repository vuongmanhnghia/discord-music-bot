"""
Playlist commands for the music bot
Handles playlist creation, management, and operations with pagination
"""

import asyncio
from typing import Optional
import discord
from discord import app_commands

from . import BaseCommandHandler
from ..pkg.logger import logger
from ..services.playback import playback_service
from ..domain.valueobjects.source_type import SourceType
from ..utils.youtube_playlist_handler import YouTubePlaylistHandler
from ..utils.validation import ValidationUtils
from ..utils.pagination import PaginationHelper, send_paginated_embed

from ..config.constants import SUCCESS_MESSAGES, ERROR_MESSAGES


class PlaylistCommandHandler(BaseCommandHandler):
    """Handler for playlist-related commands"""

    def __init__(self, bot):
        super().__init__(bot)
        # Access bot services
        self.playlist_service = getattr(bot, "playlist_service", None)
        self.active_playlists = getattr(bot, "active_playlists", {})

    def setup_commands(self):
        """Setup playlist commands"""

        @self.bot.tree.command(
            name="use", description="Chọn playlist và chuyển sang phát ngay lập tức"
        )
        @app_commands.describe(playlist_name="Tên playlist muốn sử dụng")
        async def use_playlist(interaction: discord.Interaction, playlist_name: str):
            """📋 Safe playlist switch"""
            try:
                if not self.playlist_service:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["playlist_service_unavailable"], ephemeral=True
                    )
                    return

                # Check if user is in voice channel
                if not await self.ensure_user_in_voice(interaction):
                    return

                # Check if playlist exists first
                success, message = self.playlist_service.load_playlist(playlist_name)
                if not success:
                    error_embed = self.create_error_embed("❌ Lỗi playlist", message)
                    await interaction.response.send_message(
                        embed=error_embed, ephemeral=True
                    )
                    return

                # Respond immediately to avoid timeout
                embed = self.create_info_embed(
                    "🔄 Đang chuyển playlist",
                    f"📋 **{playlist_name}**\nĐang dừng phát hiện tại và tải playlist mới...",
                )
                await interaction.response.send_message(embed=embed)

                # Perform safe playlist switch
                from ..services.playlist_switch import playlist_switch_manager

                switch_success, switch_message = (
                    await playlist_switch_manager.safe_playlist_switch(
                        interaction.guild.id, playlist_name, str(interaction.user)
                    )
                )

                if switch_success:
                    # Set as active playlist
                    self.active_playlists[interaction.guild.id] = playlist_name

                    # Update with success message
                    success_embed = self.create_success_embed(
                        "✅ Đã chuyển playlist thành công", switch_message
                    )
                else:
                    # Update with error message
                    success_embed = self.create_error_embed(
                        "❌ Lỗi khi chuyển playlist", switch_message
                    )

                await interaction.edit_original_response(embed=success_embed)

            except Exception as e:
                await self.handle_command_error(interaction, e, "use")

        @self.bot.tree.command(name="create", description="Tạo playlist mới")
        @app_commands.describe(name="Tên playlist")
        async def create_playlist(interaction: discord.Interaction, name: str):
            """📝 Create new playlist"""
            try:
                if not self.playlist_service:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["playlist_service_unavailable"], ephemeral=True
                    )
                    return

                # Validate playlist name
                is_valid, error_msg = ValidationUtils.validate_playlist_name(name)
                if not is_valid:
                    await interaction.response.send_message(error_msg, ephemeral=True)
                    return

                success, message = self.playlist_service.create_playlist(name)

                if success:
                    embed = self.create_success_embed(
                        "✅ Tạo playlist thành công", message
                    )
                    await interaction.response.send_message(embed=embed)
                else:
                    error_embed = self.create_error_embed(
                        "❌ Lỗi tạo playlist", message
                    )
                    await interaction.response.send_message(
                        embed=error_embed, ephemeral=True
                    )

            except Exception as e:
                await self.handle_command_error(interaction, e, "create")

        @self.bot.tree.command(
            name="add", description="Thêm bài hát (vào playlist hiện tại nếu có) và phát ngay"
        )
        @app_commands.describe(song_input="URL hoặc tên bài hát")
        async def add_song(
            interaction: discord.Interaction, song_input: str
        ):
            """➕ Add song to queue + active playlist + play immediately"""
            try:
                if not interaction.guild:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["guild_only"], ephemeral=True
                    )
                    return

                # Validate and sanitize song input
                song_input = ValidationUtils.sanitize_query(song_input)
                is_valid, error_msg = ValidationUtils.validate_query_length(song_input)
                if not is_valid:
                    await interaction.response.send_message(error_msg, ephemeral=True)
                    return

                # Check voice requirements
                if not await self.ensure_user_in_voice(interaction):
                    return

                guild_id = interaction.guild.id
                active_playlist = self.active_playlists.get(guild_id)

                # Defer response as processing may take time
                await interaction.response.defer()

                # Process song using playback service (same as /play)
                success, message, song = await playback_service.play_request(
                    user_input=song_input,
                    guild_id=guild_id,
                    requested_by=str(interaction.user),
                    auto_play=True,  # Start playing if not already
                )

                if not success or not song:
                    error_embed = self.create_error_embed("❌ Lỗi thêm bài hát", message)
                    await interaction.followup.send(embed=error_embed)
                    return

                # If active playlist exists, also add to playlist file
                playlist_saved = False
                if active_playlist:
                    # Wait for metadata to be ready
                    max_wait = 10
                    for _ in range(max_wait):
                        if song.metadata and song.metadata.title:
                            break
                        await asyncio.sleep(1)

                    title = song.metadata.title if song.metadata else song.original_input
                    playlist_success, playlist_message = (
                        self.playlist_service.add_to_playlist(
                            active_playlist,
                            song.original_input,
                            song.source_type,
                            title,
                        )
                    )
                    playlist_saved = playlist_success

                # Create success embed
                if active_playlist and playlist_saved:
                    embed = self.create_success_embed(
                        "✅ Đã thêm vào queue & playlist",
                        f"📋 **Playlist:** {active_playlist}\n🎵 **Bài hát:** {song.display_name}",
                    )
                else:
                    embed = self.create_success_embed(
                        "✅ Đã thêm vào queue",
                        f"🎵 **{song.display_name}**",
                    )

                # Add song details
                embed.add_field(
                    name="Nguồn", value=song.source_type.value.title(), inline=True
                )
                embed.add_field(
                    name="Trạng thái", value=song.status.value.title(), inline=True
                )

                if song.metadata and hasattr(song.metadata, "duration_formatted"):
                    embed.add_field(
                        name="Thời lượng",
                        value=song.metadata.duration_formatted,
                        inline=True,
                    )

                # Show queue position
                queue_manager = self.get_queue_manager(guild_id)
                if queue_manager:
                    current_pos, total_songs = queue_manager.position
                    embed.add_field(
                        name="Vị trí trong queue",
                        value=f"#{total_songs}",
                        inline=True,
                    )

                await interaction.followup.send(embed=embed)

            except Exception as e:
                await self.handle_command_error(interaction, e, "add")

        @self.bot.tree.command(name="remove", description="Xóa bài hát khỏi playlist")
        @app_commands.describe(
            playlist_name="Tên playlist", song_index="Số thứ tự bài hát (bắt đầu từ 1)"
        )
        async def remove_from_playlist(
            interaction: discord.Interaction, playlist_name: str, song_index: int
        ):
            """🗑️ Remove song from playlist"""
            try:
                if not self.playlist_service:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["playlist_service_unavailable"], ephemeral=True
                    )
                    return

                success, message = self.playlist_service.remove_from_playlist(
                    playlist_name, song_index - 1  # Convert to 0-based index
                )

                if success:
                    embed = self.create_success_embed("✅ Đã xóa bài hát", message)
                    await interaction.response.send_message(embed=embed)
                else:
                    error_embed = self.create_error_embed("❌ Lỗi xóa bài hát", message)
                    await interaction.response.send_message(
                        embed=error_embed, ephemeral=True
                    )

            except Exception as e:
                await self.handle_command_error(interaction, e, "remove")

        @self.bot.tree.command(name="playlists", description="Liệt kê tất cả playlist")
        async def list_playlists(interaction: discord.Interaction):
            """📚 List all playlists"""
            try:
                if not self.playlist_service:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["playlist_service_unavailable"], ephemeral=True
                    )
                    return

                playlists = self.playlist_service.list_playlists()

                if not playlists:
                    await interaction.response.send_message(
                        "📚 Chưa có playlist nào được tạo!", ephemeral=True
                    )
                    return

                # Get active playlist for this guild
                active_playlist = self.active_playlists.get(interaction.guild.id)

                embed = self.create_info_embed("📚 Danh sách Playlist", "")

                playlist_text = ""
                for i, playlist_name in enumerate(playlists, 1):
                    indicator = "📋" if playlist_name == active_playlist else "📝"
                    playlist_text += f"{indicator} `{i}.` **{playlist_name}**\n"

                embed.add_field(
                    name=f"Có {len(playlists)} playlist",
                    value=playlist_text,
                    inline=False,
                )

                if active_playlist:
                    embed.add_field(
                        name="📋 Đang sử dụng",
                        value=f"**{active_playlist}**",
                        inline=False,
                    )

                await interaction.response.send_message(embed=embed)

            except Exception as e:
                await self.handle_command_error(interaction, e, "playlists")

        @self.bot.tree.command(
            name="playlist", description="Hiển thị nội dung playlist"
        )
        @app_commands.describe(name="Tên playlist (để trống để xem playlist hiện tại)")
        async def show_playlist(
            interaction: discord.Interaction, name: Optional[str] = None
        ):
            """📋 Show playlist contents with interactive pagination"""
            try:
                if not self.playlist_service:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["playlist_service_unavailable"], ephemeral=True
                    )
                    return

                # Use active playlist if no name provided
                playlist_name = name or self.active_playlists.get(interaction.guild.id)

                if not playlist_name:
                    await interaction.response.send_message(
                        "❌ Không có playlist nào được chọn! Chỉ định tên playlist hoặc sử dụng `/use <playlist>`",
                        ephemeral=True,
                    )
                    return

                success, songs = self.playlist_service.get_playlist_content(
                    playlist_name
                )

                if not success:
                    error_embed = self.create_error_embed(
                        "❌ Lỗi playlist", songs
                    )  # songs contains error message
                    await interaction.response.send_message(
                        embed=error_embed, ephemeral=True
                    )
                    return

                if not songs:
                    await interaction.response.send_message(
                        f"📋 Playlist **{playlist_name}** trống!",
                        ephemeral=True,
                    )
                    return

                # Create paginated pages
                items_per_page = 10
                total_pages = max(1, (len(songs) + items_per_page - 1) // items_per_page)
                pages = []

                for page_num in range(1, total_pages + 1):
                    start_idx = (page_num - 1) * items_per_page
                    end_idx = min(start_idx + items_per_page, len(songs))
                    page_songs = songs[start_idx:end_idx]

                    embed = PaginationHelper.create_playlist_embed(
                        songs=page_songs,
                        page_num=page_num,
                        total_pages=total_pages,
                        playlist_name=playlist_name,
                        total_songs=len(songs),
                    )
                    pages.append(embed)

                # Send paginated embed
                await send_paginated_embed(interaction, pages)

            except Exception as e:
                await self.handle_command_error(interaction, e, "playlist")

        @self.bot.tree.command(name="delete", description="Xóa playlist")
        @app_commands.describe(name="Tên playlist cần xóa")
        async def delete_playlist(interaction: discord.Interaction, name: str):
            """🗑️ Delete playlist"""
            try:
                if not self.playlist_service:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["playlist_service_unavailable"], ephemeral=True
                    )
                    return

                success, message = self.playlist_service.delete_playlist(name)

                if success:
                    # Remove from active playlists if it was active
                    if self.active_playlists.get(interaction.guild.id) == name:
                        del self.active_playlists[interaction.guild.id]

                    embed = self.create_success_embed("✅ Đã xóa playlist", message)
                    await interaction.response.send_message(embed=embed)
                else:
                    error_embed = self.create_error_embed(
                        "❌ Lỗi xóa playlist", message
                    )
                    await interaction.response.send_message(
                        embed=error_embed, ephemeral=True
                    )

            except Exception as e:
                await self.handle_command_error(interaction, e, "delete")

    async def _handle_add_to_playlist(
        self, interaction: discord.Interaction, song_input: str, playlist_name: str
    ):
        """Handle adding song to playlist (shared logic for /add and /addto)"""
        # Check if it's a YouTube playlist (only explicit playlist URLs)
        if YouTubePlaylistHandler.is_playlist_url(song_input):
            await self._handle_add_playlist_to_playlist(
                interaction, song_input, playlist_name
            )
        else:
            await self._handle_add_single_song_to_playlist(
                interaction, song_input, playlist_name
            )

    async def _handle_add_single_song_to_playlist(
        self, interaction: discord.Interaction, song_input: str, playlist_name: str
    ):
        """Handle adding single song to playlist"""
        # Show processing message
        await interaction.response.send_message(
            f"🔍 **Processing:** {song_input[:50]}{'...' if len(song_input) > 50 else ''}"
        )

        try:
            # Step 1: Process song like /play (but without auto_play)
            success, response_message, song = await playback_service.play_request(
                user_input=song_input,
                guild_id=interaction.guild.id,
                requested_by=str(interaction.user),
                auto_play=False,  # Don't auto-start playback
            )

            if success and song:
                # Step 2: Wait for metadata to be ready before adding to playlist
                # This ensures we save the real title, not "Video X"
                max_wait = 30  # Wait up to 30 seconds for metadata
                for _ in range(max_wait):
                    if song.metadata and song.metadata.title:
                        break
                    await asyncio.sleep(1)
                
                # Use processed metadata for better title
                title = song.metadata.title if song.metadata else song_input
                playlist_success, playlist_message = (
                    self.playlist_service.add_to_playlist(
                        playlist_name,
                        song.original_input,
                        song.source_type,
                        title,
                    )
                )

                if playlist_success:
                    embed = self.create_success_embed(
                        "✅ Đã thêm vào playlist và queue",
                        f"📋 **{playlist_name}**\n🎵 **{song.display_name}**",
                    )

                    # Add detailed info like /play
                    embed.add_field(
                        name="Nguồn",
                        value=song.source_type.value.title(),
                        inline=True,
                    )

                    embed.add_field(
                        name="Trạng thái",
                        value=song.status.value.title(),
                        inline=True,
                    )

                    if song.metadata and hasattr(song, "duration_formatted"):
                        embed.add_field(
                            name="Thời lượng",
                            value=song.duration_formatted,
                            inline=True,
                        )

                    # Show queue position
                    queue_manager = self.get_queue_manager(interaction.guild.id)
                    if queue_manager:
                        position = queue_manager.queue_size
                        embed.add_field(
                            name="Vị trí trong queue",
                            value=f"#{position}",
                            inline=True,
                        )

                    await interaction.edit_original_response(content=None, embed=embed)
                else:
                    error_embed = self.create_error_embed(
                        "❌ Lỗi thêm vào playlist", playlist_message
                    )
                    await interaction.edit_original_response(
                        content=None, embed=error_embed
                    )
            else:
                error_embed = self.create_error_embed(
                    "❌ Lỗi xử lý bài hát", response_message
                )
                await interaction.edit_original_response(
                    content=None, embed=error_embed
                )

        except Exception as e:
            logger.error(f"Error in add to playlist: {e}")
            error_embed = self.create_error_embed(
                "❌ Lỗi không mong đợi", f"Đã xảy ra lỗi: {str(e)}"
            )
            await interaction.edit_original_response(content=None, embed=error_embed)

    async def _handle_add_playlist_to_playlist(
        self, interaction: discord.Interaction, song_input: str, playlist_name: str
    ):
        """Handle adding YouTube playlist to playlist"""
        # Handle YouTube playlist
        await interaction.response.defer()

        # Extract playlist videos
        success_playlist, video_urls, message = (
            await YouTubePlaylistHandler.extract_playlist_videos(song_input)
        )

        if success_playlist and video_urls:
            # Process each video in playlist
            added_count = 0
            failed_count = 0

            embed = self.create_info_embed(
                "🎵 Processing YouTube Playlist",
                f"{message}\n⏳ Adding to playlist '{playlist_name}'...",
            )

            # Send initial message
            await interaction.followup.send(embed=embed)

            # Process videos
            for i, video_url in enumerate(video_urls[:50]):  # Limit to 50 videos
                try:
                    # Create and process song to get metadata
                    from ..domain.entities.song import Song
                    from ..services.playback import playback_service
                    
                    # Create song object
                    song = Song(
                        original_input=video_url,
                        source_type=SourceType.YOUTUBE,
                        requested_by=str(interaction.user),
                        guild_id=interaction.guild.id
                    )
                    
                    # Try to get metadata (with timeout)
                    try:
                        # Process song to extract metadata
                        process_success = await playback_service.processing_service.process_song(song)
                        
                        # Wait briefly for metadata (max 5 seconds per song)
                        if process_success:
                            for _ in range(5):
                                if song.metadata and song.metadata.title:
                                    break
                                await asyncio.sleep(1)
                        
                        # Use real title if available, otherwise use generic
                        title = song.metadata.title if song.metadata else f"Video {i+1}"
                    except Exception as e:
                        logger.warning(f"Could not extract metadata for {video_url}: {e}")
                        title = f"Video {i+1}"
                    
                    # Add to playlist with proper title
                    success, message_single = self.playlist_service.add_to_playlist(
                        playlist_name,
                        video_url,
                        SourceType.YOUTUBE,
                        title,
                    )

                    if success:
                        added_count += 1
                    else:
                        failed_count += 1
                        logger.warning(
                            f"Failed to add video to playlist: {message_single}"
                        )

                    # Update progress every 10 songs
                    if (i + 1) % 10 == 0:
                        progress_embed = self.create_info_embed(
                            "🎵 Processing YouTube Playlist",
                            f"📋 **{playlist_name}**\n"
                            f"✅ Added: {added_count} videos\n"
                            f"❌ Failed: {failed_count} videos\n"
                            f"⏳ Progress: {i+1}/{len(video_urls)}",
                        )
                        await interaction.edit_original_response(embed=progress_embed)

                except Exception as e:
                    logger.error(
                        f"Error adding playlist video to playlist {playlist_name}: {e}"
                    )
                    failed_count += 1

            # Final result
            final_embed = self.create_success_embed(
                f"✅ Đã cập nhật playlist {playlist_name}",
                f"Đã thêm: {added_count} bài hát\n"
                f"Lỗi: {failed_count} bài hát\n"
                f"Sử dụng `/playlist {playlist_name}` để xem nội dung playlist",
            )

            await interaction.edit_original_response(embed=final_embed)
            return

        else:
            # Failed to process playlist
            error_embed = self.create_error_embed("❌ YouTube Playlist Error", message)
            await interaction.followup.send(embed=error_embed)
            return

    # Helper methods removed - now using PaginationHelper

