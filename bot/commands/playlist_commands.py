"""
Playlist commands for the music bot
Handles playlist creation, management, and operations
"""

from typing import Optional
import discord
from discord import app_commands

from . import BaseCommandHandler
from ..pkg.logger import logger
from ..services.playback import playback_service
from ..domain.valueobjects.source_type import SourceType
from ..utils.youtube_playlist_handler import YouTubePlaylistHandler


class PlaylistCommandHandler(BaseCommandHandler):
    """Handler for playlist-related commands"""

    def __init__(self, bot):
        super().__init__(bot)
        # Access bot services
        self.playlist_service = getattr(bot, 'playlist_service', None)
        self.active_playlists = getattr(bot, 'active_playlists', {})

    def setup_commands(self):
        """Setup playlist commands"""

        @self.bot.tree.command(
            name="use",
            description="Chọn playlist để sử dụng làm queue mặc định"
        )
        @app_commands.describe(playlist_name="Tên playlist muốn sử dụng")
        async def use_playlist(interaction: discord.Interaction, playlist_name: str):
            """📋 Set active playlist"""
            try:
                if not self.playlist_service:
                    await interaction.response.send_message(
                        "❌ Playlist service không khả dụng!", ephemeral=True
                    )
                    return

                # Check if playlist exists
                success, message = self.playlist_service.load_playlist(playlist_name)
                
                if success:
                    # Set as active playlist
                    self.active_playlists[interaction.guild.id] = playlist_name
                    
                    embed = self.create_success_embed(
                        "✅ Đã chọn playlist",
                        f"📋 **{playlist_name}**\n{message}"
                    )
                    await interaction.response.send_message(embed=embed)
                else:
                    error_embed = self.create_error_embed("❌ Lỗi playlist", message)
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)

            except Exception as e:
                await self.handle_command_error(interaction, e, "use")

        @self.bot.tree.command(name="create", description="Tạo playlist mới")
        @app_commands.describe(name="Tên playlist")
        async def create_playlist(interaction: discord.Interaction, name: str):
            """📝 Create new playlist"""
            try:
                if not self.playlist_service:
                    await interaction.response.send_message(
                        "❌ Playlist service không khả dụng!", ephemeral=True
                    )
                    return

                success, message = self.playlist_service.create_playlist(name)
                
                if success:
                    embed = self.create_success_embed("✅ Tạo playlist thành công", message)
                    await interaction.response.send_message(embed=embed)
                else:
                    error_embed = self.create_error_embed("❌ Lỗi tạo playlist", message)
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)

            except Exception as e:
                await self.handle_command_error(interaction, e, "create")

        @self.bot.tree.command(name="add", description="Thêm bài hát vào playlist hiện tại")
        @app_commands.describe(song_input="URL hoặc tên bài hát")
        async def add_to_active_playlist(
            interaction: discord.Interaction, song_input: str
        ):
            """➕ Add song to active playlist (with processing like /play)"""
            try:
                if not interaction.guild:
                    await interaction.response.send_message(
                        "⛔ Bot chưa kết nối voice!", ephemeral=True
                    )
                    return

                # Check if there's an active playlist
                guild_id = interaction.guild.id
                active_playlist = self.active_playlists.get(guild_id)

                if not active_playlist:
                    await interaction.response.send_message(
                        "❌ Chưa có playlist nào được chọn! Sử dụng `/use <playlist>` trước hoặc sử dụng `/addto <playlist> <song>`",
                        ephemeral=True,
                    )
                    return

                await self._handle_add_to_playlist(interaction, song_input, active_playlist)

            except Exception as e:
                await self.handle_command_error(interaction, e, "add")

        @self.bot.tree.command(
            name="addto", description="Thêm bài hát vào playlist chỉ định"
        )
        @app_commands.describe(
            playlist_name="Tên playlist", song_input="URL hoặc tên bài hát"
        )
        async def add_to_specific_playlist(
            interaction: discord.Interaction, playlist_name: str, song_input: str
        ):
            """➕ Add song to specific playlist"""
            try:
                await self._handle_add_to_playlist(interaction, song_input, playlist_name)

            except Exception as e:
                await self.handle_command_error(interaction, e, "addto")

        @self.bot.tree.command(name="remove", description="Xóa bài hát khỏi playlist")
        @app_commands.describe(
            playlist_name="Tên playlist", 
            song_index="Số thứ tự bài hát (bắt đầu từ 1)"
        )
        async def remove_from_playlist(
            interaction: discord.Interaction, playlist_name: str, song_index: int
        ):
            """🗑️ Remove song from playlist"""
            try:
                if not self.playlist_service:
                    await interaction.response.send_message(
                        "❌ Playlist service không khả dụng!", ephemeral=True
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
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)

            except Exception as e:
                await self.handle_command_error(interaction, e, "remove")

        @self.bot.tree.command(name="playlists", description="Liệt kê tất cả playlist")
        async def list_playlists(interaction: discord.Interaction):
            """📚 List all playlists"""
            try:
                if not self.playlist_service:
                    await interaction.response.send_message(
                        "❌ Playlist service không khả dụng!", ephemeral=True
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
                    inline=False
                )

                if active_playlist:
                    embed.add_field(
                        name="📋 Đang sử dụng",
                        value=f"**{active_playlist}**",
                        inline=False
                    )

                await interaction.response.send_message(embed=embed)

            except Exception as e:
                await self.handle_command_error(interaction, e, "playlists")

        @self.bot.tree.command(name="playlist", description="Hiển thị nội dung playlist")
        @app_commands.describe(name="Tên playlist (để trống để xem playlist hiện tại)")
        async def show_playlist(interaction: discord.Interaction, name: Optional[str] = None):
            """📋 Show playlist contents"""
            try:
                if not self.playlist_service:
                    await interaction.response.send_message(
                        "❌ Playlist service không khả dụ!", ephemeral=True
                    )
                    return

                # Use active playlist if no name provided
                playlist_name = name or self.active_playlists.get(interaction.guild.id)
                
                if not playlist_name:
                    await interaction.response.send_message(
                        "❌ Không có playlist nào được chọn! Chỉ định tên playlist hoặc sử dụng `/use <playlist>`",
                        ephemeral=True
                    )
                    return

                success, songs = self.playlist_service.get_playlist_content(playlist_name)
                
                if not success:
                    error_embed = self.create_error_embed("❌ Lỗi playlist", songs)  # songs contains error message
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)
                    return

                embed = self._create_playlist_display_embed(playlist_name, songs)
                await interaction.response.send_message(embed=embed)

            except Exception as e:
                await self.handle_command_error(interaction, e, "playlist")

        @self.bot.tree.command(name="delete", description="Xóa playlist")
        @app_commands.describe(name="Tên playlist cần xóa")
        async def delete_playlist(interaction: discord.Interaction, name: str):
            """🗑️ Delete playlist"""
            try:
                if not self.playlist_service:
                    await interaction.response.send_message(
                        "❌ Playlist service không khả dụng!", ephemeral=True
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
                    error_embed = self.create_error_embed("❌ Lỗi xóa playlist", message)
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)

            except Exception as e:
                await self.handle_command_error(interaction, e, "delete")

    async def _handle_add_to_playlist(self, interaction: discord.Interaction, song_input: str, playlist_name: str):
        """Handle adding song to playlist (shared logic for /add and /addto)"""
        # Check if it's a YouTube playlist (only explicit playlist URLs)
        if YouTubePlaylistHandler.is_playlist_url(song_input):
            await self._handle_add_playlist_to_playlist(interaction, song_input, playlist_name)
        else:
            await self._handle_add_single_song_to_playlist(interaction, song_input, playlist_name)

    async def _handle_add_single_song_to_playlist(self, interaction: discord.Interaction, song_input: str, playlist_name: str):
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
                # Step 2: Add processed song to playlist
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
                        f"📋 **{playlist_name}**\n🎵 **{song.display_name}**"
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

                    if song.metadata and hasattr(song, 'duration_formatted'):
                        embed.add_field(
                            name="Thời lượng",
                            value=song.duration_formatted,
                            inline=True,
                        )

                    # Show queue position
                    queue_manager = self.get_queue_manager(interaction.guild.id)
                    if queue_manager:
                        position = len(queue_manager.queue)
                        embed.add_field(
                            name="Vị trí trong queue",
                            value=f"#{position}",
                            inline=True,
                        )

                    await interaction.edit_original_response(content=None, embed=embed)
                else:
                    error_embed = self.create_error_embed("❌ Lỗi thêm vào playlist", playlist_message)
                    await interaction.edit_original_response(content=None, embed=error_embed)
            else:
                error_embed = self.create_error_embed("❌ Lỗi xử lý bài hát", response_message)
                await interaction.edit_original_response(content=None, embed=error_embed)

        except Exception as e:
            logger.error(f"Error in add to playlist: {e}")
            error_embed = self.create_error_embed(
                "❌ Lỗi không mong đợi", 
                f"Đã xảy ra lỗi: {str(e)}"
            )
            await interaction.edit_original_response(content=None, embed=error_embed)

    async def _handle_add_playlist_to_playlist(self, interaction: discord.Interaction, song_input: str, playlist_name: str):
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
                f"{message}\n⏳ Adding to playlist '{playlist_name}'..."
            )

            # Send initial message
            await interaction.followup.send(embed=embed)

            # Process videos
            for i, video_url in enumerate(
                video_urls[:50]
            ):  # Limit to 50 videos
                try:
                    # Detect source type from input
                    source_type = SourceType.YOUTUBE  # Default for playlist videos

                    # Use video URL as title initially, will be updated when processed
                    success, message_single = (
                        self.playlist_service.add_to_playlist(
                            playlist_name,
                            video_url,
                            source_type,
                            f"Video {i+1}",
                        )
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
                            f"⏳ Progress: {i+1}/{len(video_urls)}"
                        )
                        await interaction.edit_original_response(
                            embed=progress_embed
                        )

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
                f"Sử dụng `/playlist {playlist_name}` để xem nội dung playlist"
            )

            await interaction.edit_original_response(embed=final_embed)
            return

        else:
            # Failed to process playlist
            error_embed = self.create_error_embed("❌ YouTube Playlist Error", message)
            await interaction.followup.send(embed=error_embed)
            return

    def _create_playlist_display_embed(self, playlist_name: str, songs: list) -> discord.Embed:
        """Create embed for playlist display"""
        embed = self.create_info_embed(f"📋 Playlist: {playlist_name}", "")
        
        if not songs:
            embed.add_field(
                name="📄 Nội dung",
                value="Playlist trống",
                inline=False
            )
            return embed

        # Show first 20 songs
        display_songs = songs[:20]
        songs_text = ""
        
        for i, song in enumerate(display_songs, 1):
            # Extract title from song data
            title = song.get('title', song.get('input', 'Unknown'))
            source = song.get('source_type', 'Unknown')
            songs_text += f"`{i}.` **{title}** `({source})`\n"

        embed.add_field(
            name=f"📄 Nội dung ({len(songs)} bài)",
            value=songs_text,
            inline=False
        )

        if len(songs) > 20:
            embed.set_footer(text=f"Hiển thị 20/{len(songs)} bài đầu tiên")

        return embed
