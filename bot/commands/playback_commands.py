"""
Playback commands for the music bot
Handles play, skip, pause, resume, stop, volume, nowplaying, repeat commands
"""

from typing import Optional
import discord
from discord import app_commands

from . import BaseCommandHandler
from ..pkg.logger import logger
from ..services.audio_service import audio_service
from ..services.playback import playback_service
from ..domain.valueobjects.source_type import SourceType
from ..utils.youtube_playlist_handler import YouTubePlaylistHandler


class PlaybackCommandHandler(BaseCommandHandler):
    """Handler for playback-related commands"""

    def setup_commands(self):
        """Setup playback commands"""

        @self.bot.tree.command(
            name="play",
            description="Phát nhạc từ URL/tìm kiếm hoặc từ playlist hiện tại",
        )
        @app_commands.describe(
            query="URL hoặc từ khóa tìm kiếm (để trống để phát từ playlist hiện tại)"
        )
        @app_commands.checks.cooldown(
            1, 3.0, key=lambda i: (i.guild_id, i.user.id)
        )  # 3 second cooldown per user per guild
        async def play_music(
            interaction: discord.Interaction, query: Optional[str] = None
        ):
            """▶️ Play music from URL/search query or from active playlist"""
            try:
                if not interaction.guild:
                    await interaction.response.send_message(
                        "⛔ Bot chưa kết nối voice!", ephemeral=True
                    )
                    return

                # Check voice requirements
                if not await self.ensure_user_in_voice(interaction):
                    return

                # Handle two modes: with query or from active playlist
                if query:
                    await self._handle_play_with_query(interaction, query)
                else:
                    await self._handle_play_from_playlist(interaction)

            except Exception as e:
                await self.handle_command_error(interaction, e, "play")

        @self.bot.tree.command(name="skip", description="Bỏ qua bài hiện tại")
        async def skip_song(interaction: discord.Interaction):
            """⏭️ Skip current song"""
            try:
                if not await self.ensure_same_voice_channel(interaction):
                    return

                queue_manager = self.get_queue_manager(interaction.guild.id)
                if not queue_manager:
                    await interaction.response.send_message(
                        "❌ Không có hàng đợi nào!", ephemeral=True
                    )
                    return

                current_song = queue_manager.get_current_song()
                if not current_song:
                    await interaction.response.send_message(
                        "❌ Không có bài nào đang phát!", ephemeral=True
                    )
                    return

                # Skip current song
                success = await playback_service.skip_song(interaction.guild.id)
                
                if success:
                    embed = self.create_success_embed(
                        "⏭️ Đã bỏ qua bài hát",
                        f"**{current_song.display_name}**"
                    )
                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message(
                        "❌ Không thể bỏ qua bài hát!", ephemeral=True
                    )

            except Exception as e:
                await self.handle_command_error(interaction, e, "skip")

        @self.bot.tree.command(name="pause", description="Tạm dừng phát")
        async def pause_music(interaction: discord.Interaction):
            """⏸️ Pause playback"""
            try:
                voice_client = await self.ensure_voice_connection(interaction)
                if not voice_client:
                    return

                if not await self.ensure_same_voice_channel(interaction):
                    return

                if voice_client.is_paused():
                    await interaction.response.send_message(
                        "⏸️ Nhạc đã được tạm dừng!", ephemeral=True
                    )
                    return

                voice_client.pause()
                embed = self.create_info_embed("⏸️ Tạm dừng", "Đã tạm dừng phát nhạc")
                await interaction.response.send_message(embed=embed)

            except Exception as e:
                await self.handle_command_error(interaction, e, "pause")

        @self.bot.tree.command(name="resume", description="Tiếp tục phát nhạc")
        async def resume_music(interaction: discord.Interaction):
            """▶️ Resume playback"""
            try:
                voice_client = await self.ensure_voice_connection(interaction)
                if not voice_client:
                    return

                if not await self.ensure_same_voice_channel(interaction):
                    return

                if not voice_client.is_paused():
                    await interaction.response.send_message(
                        "▶️ Nhạc đang phát!", ephemeral=True
                    )
                    return

                voice_client.resume()
                embed = self.create_success_embed("▶️ Tiếp tục", "Đã tiếp tục phát nhạc")
                await interaction.response.send_message(embed=embed)

            except Exception as e:
                await self.handle_command_error(interaction, e, "resume")

        @self.bot.tree.command(name="stop", description="Dừng và xóa hàng đợi")
        async def stop_music(interaction: discord.Interaction):
            """⏹️ Stop music and clear queue"""
            try:
                if not await self.ensure_same_voice_channel(interaction):
                    return

                success = await playback_service.stop_playback(interaction.guild.id)
                
                if success:
                    embed = self.create_info_embed(
                        "⏹️ Đã dừng phát nhạc", 
                        "Đã dừng phát và xóa hàng đợi"
                    )
                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message(
                        "❌ Không có nhạc nào đang phát!", ephemeral=True
                    )

            except Exception as e:
                await self.handle_command_error(interaction, e, "stop")

        @self.bot.tree.command(name="volume", description="Đặt âm lượng (0-100)")
        @app_commands.describe(volume="Âm lượng từ 0 đến 100")
        async def set_volume(interaction: discord.Interaction, volume: int):
            """🔊 Set playback volume"""
            try:
                if not await self.ensure_same_voice_channel(interaction):
                    return

                if not 0 <= volume <= 100:
                    await interaction.response.send_message(
                        "❌ Âm lượng phải từ 0 đến 100!", ephemeral=True
                    )
                    return

                success = await playback_service.set_volume(interaction.guild.id, volume)
                
                if success:
                    # Volume icon based on level
                    if volume == 0:
                        icon = "🔇"
                    elif volume <= 33:
                        icon = "🔉"
                    elif volume <= 66:
                        icon = "🔊"
                    else:
                        icon = "📢"

                    embed = self.create_success_embed(
                        f"{icon} Âm lượng đã đặt",
                        f"**{volume}%**"
                    )
                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message(
                        "❌ Không thể đặt âm lượng!", ephemeral=True
                    )

            except Exception as e:
                await self.handle_command_error(interaction, e, "volume")

        @self.bot.tree.command(name="nowplaying", description="Hiển thị bài đang phát")
        async def now_playing(interaction: discord.Interaction):
            """🎵 Show currently playing song"""
            try:
                if not interaction.guild:
                    await interaction.response.send_message(
                        "⛔ Lệnh này chỉ có thể sử dụng trong server!", ephemeral=True
                    )
                    return

                queue_manager = self.get_queue_manager(interaction.guild.id)
                if not queue_manager:
                    await interaction.response.send_message(
                        "❌ Không có hàng đợi nào!", ephemeral=True
                    )
                    return

                current_song = queue_manager.get_current_song()
                if not current_song:
                    await interaction.response.send_message(
                        "❌ Không có bài nào đang phát!", ephemeral=True
                    )
                    return

                embed = await self._create_now_playing_embed(current_song, interaction.guild.id)
                await interaction.response.send_message(embed=embed)

            except Exception as e:
                await self.handle_command_error(interaction, e, "nowplaying")

        @self.bot.tree.command(name="repeat", description="Set repeat mode")
        @app_commands.describe(mode="off: Tắt lặp, track: Lặp bài hiện tại, queue: Lặp hàng đợi")
        @app_commands.choices(mode=[
            app_commands.Choice(name="off", value="off"),
            app_commands.Choice(name="track", value="track"),
            app_commands.Choice(name="queue", value="queue"),
        ])
        async def repeat_mode(interaction: discord.Interaction, mode: str):
            """🔁 Set repeat mode"""
            try:
                if not interaction.guild:
                    await interaction.response.send_message(
                        "⛔ Lệnh này chỉ có thể sử dụng trong server!", ephemeral=True
                    )
                    return

                success = await playback_service.set_repeat_mode(interaction.guild.id, mode)
                
                if success:
                    mode_icons = {
                        "off": "📴",
                        "track": "🔂", 
                        "queue": "🔁"
                    }
                    mode_names = {
                        "off": "Tắt lặp",
                        "track": "Lặp bài hiện tại",
                        "queue": "Lặp hàng đợi"
                    }
                    
                    icon = mode_icons.get(mode, "🔁")
                    name = mode_names.get(mode, mode)
                    
                    embed = self.create_success_embed(
                        f"{icon} Chế độ lặp",
                        f"**{name}**"
                    )
                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message(
                        "❌ Không thể đặt chế độ lặp!", ephemeral=True
                    )

            except Exception as e:
                await self.handle_command_error(interaction, e, "repeat")

    async def _handle_play_with_query(self, interaction: discord.Interaction, query: str):
        """Handle play command with query parameter"""
        # Check if it's a YouTube playlist (only explicit playlist URLs)
        if YouTubePlaylistHandler.is_playlist_url(query):
            # Handle YouTube playlist - use InteractionManager for long operation
            async def process_youtube_playlist():
                # Extract playlist videos
                success, video_urls, message = (
                    await YouTubePlaylistHandler.extract_playlist_videos(query)
                )

                if not success or not video_urls:
                    return self.create_error_embed("❌ Playlist Error", message)

                return await self.bot._process_playlist_videos(
                    video_urls,
                    message,
                    interaction.guild.id,
                    str(interaction.user),
                )

            result = await self.bot.interaction_manager.handle_long_operation(
                interaction,
                process_youtube_playlist,
                "🎵 Processing YouTube Playlist...",
            )
            return
        else:
            # Regular single video/search - existing logic
            # This now includes single videos with playlist parameters
            await interaction.response.send_message(
                f"🔍 **{query[:50]}{'...' if len(query) > 50 else ''}**"
            )

        try:
            # Process the song request
            success, message, song = await playback_service.play_request(
                user_input=query,
                guild_id=interaction.guild.id,
                requested_by=str(interaction.user),
                auto_play=True,
            )

            if success and song:
                # Create detailed embed with song info
                embed = self._create_play_success_embed(song, message)
                await interaction.edit_original_response(content=None, embed=embed)
            else:
                # Show error
                error_embed = self.create_error_embed("❌ Lỗi phát nhạc", message)
                await interaction.edit_original_response(content=None, embed=error_embed)

        except Exception as e:
            logger.error(f"Error in play command: {e}")
            error_embed = self.create_error_embed(
                "❌ Lỗi không mong đợi", 
                f"Đã xảy ra lỗi: {str(e)}"
            )
            await interaction.edit_original_response(content=None, embed=error_embed)

    async def _handle_play_from_playlist(self, interaction: discord.Interaction):
        """Handle play command without query (from active playlist)"""
        guild_id = interaction.guild.id
        active_playlist = getattr(self.bot, 'active_playlists', {}).get(guild_id)

        if not active_playlist:
            await interaction.response.send_message(
                "❌ Chưa có playlist nào được chọn! Sử dụng `/use <playlist>` trước hoặc cung cấp query để tìm kiếm.",
                ephemeral=True,
            )
            return

        queue_manager = self.get_queue_manager(guild_id)
        if not queue_manager:
            await interaction.response.send_message(
                "❌ Không thể khởi tạo hàng đợi!", ephemeral=True
            )
            return

        # Try to resume if paused
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message(
                f"▶️ **Tiếp tục phát từ playlist:** `{active_playlist}`"
            )
            return

        # Start playback from active playlist
        success = await playback_service.start_playlist_playback(guild_id, active_playlist)
        
        if success:
            embed = self.create_success_embed(
                "▶️ Bắt đầu phát từ playlist",
                f"📋 **{active_playlist}**"
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                f"❌ Không thể phát từ playlist `{active_playlist}`!", ephemeral=True
            )

    def _create_play_success_embed(self, song, message: str) -> discord.Embed:
        """Create embed for successful play request"""
        embed = self.create_success_embed("✅ Đã thêm vào hàng đợi", song.display_name)
        
        # Add song details
        embed.add_field(name="Nguồn", value=song.source_type.value.title(), inline=True)
        embed.add_field(name="Trạng thái", value=song.status.value.title(), inline=True)
        
        if song.metadata and hasattr(song, 'duration_formatted'):
            embed.add_field(name="Thời lượng", value=song.duration_formatted, inline=True)

        return embed

    async def _create_now_playing_embed(self, song, guild_id: int) -> discord.Embed:
        """Create embed for now playing display"""
        embed = self.create_info_embed("🎵 Đang phát", song.display_name)
        
        # Add song details
        embed.add_field(name="Nguồn", value=song.source_type.value.title(), inline=True)
        
        if song.metadata and hasattr(song, 'duration_formatted'):
            embed.add_field(name="Thời lượng", value=song.duration_formatted, inline=True)

        # Add queue info
        queue_manager = self.get_queue_manager(guild_id)
        if queue_manager:
            queue_size = len(queue_manager.queue)
            if queue_size > 0:
                embed.add_field(name="Hàng đợi", value=f"{queue_size} bài", inline=True)

        return embed
