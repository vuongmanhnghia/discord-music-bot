"""
Playback commands for the music bot
Handles play, skip, pause, resume, stop, volume, now, repeat commands
"""

import discord
from discord import app_commands
from typing import Optional

from . import BaseCommandHandler
from ..pkg.logger import logger
from ..utils.core import Validator
from ..utils.decorators import require_same_voice_channel
from ..utils.discord_ui import (
    create_pause_embed,
    create_resume_embed,
    create_stop_embed,
    create_volume_embed,
    create_repeat_mode_embed,
    create_shuffle_embed,
    create_shuffle_failed_embed,
    create_skip_embed,
    create_skip_failed_embed,
    create_now_playing_embed,
)

from ..config.constants import ERROR_MESSAGES

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..music_bot import MusicBot


class PlaybackCommandHandler(BaseCommandHandler):
    """Handler for playback-related commands"""

    def __init__(self, bot: "MusicBot"):
        super().__init__(bot)
        self.audio_service = bot.audio_service
        self.playback_service = bot.playback_service
        self.event_bus_manager = bot.event_bus_manager

        # Utils
        self.playlist_processor = bot.playlist_processor
        self.youtube_handler = bot.youtube_handler

    def setup_commands(self):
        """Setup playback commands"""

        @self.bot.tree.command(
            name="play",
            description="Phát nhạc từ URL/tìm kiếm hoặc từ playlist hiện tại",
        )
        @app_commands.describe(query="URL hoặc từ khóa tìm kiếm (để trống để phát từ playlist hiện tại)")
        @app_commands.checks.cooldown(1, 3.0, key=lambda i: (i.guild_id, i.user.id))
        async def play_music(interaction: discord.Interaction, query: Optional[str] = None):
            """▶️ Play music from URL/search query or from active playlist"""
            try:
                # Check if in guild
                if not interaction.guild:
                    embed = self.create_error_embed("Server Only", "This command can only be used in a server.")
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                # Check if user is in voice channel
                if not interaction.user.voice:
                    embed = self.create_error_embed(
                        "Not in Voice Channel",
                        "You must be in a voice channel to use this command.",
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                # Validate
                if query:
                    query = Validator.sanitize_query(query)
                    is_valid, error_msg = Validator.validate_query_length(query)
                    if not is_valid:
                        await interaction.response.send_message(error_msg, ephemeral=True)
                        return

                    await self._handle_play_with_query(interaction, query)
                else:
                    await self._handle_play_from_playlist(interaction)

            except Exception as e:
                await self.handle_command_error(interaction, e, "play")

        @self.bot.tree.command(name="skip", description="Bỏ qua bài hiện tại")
        @require_same_voice_channel
        async def skip_song(interaction: discord.Interaction):
            try:
                # Skip current song
                success, song_title = await self.playback_service.skip_current_song(interaction.guild.id)

                if success:
                    embed = create_skip_embed(song_title)
                    await interaction.response.send_message(embed=embed)
                else:
                    embed = create_skip_failed_embed("")
                    await interaction.response.send_message(embed=embed, ephemeral=True)

            except Exception as e:
                await self.handle_command_error(interaction, e, "skip")

        @self.bot.tree.command(name="pause", description="Tạm dừng phát")
        @require_same_voice_channel
        async def pause_music(interaction: discord.Interaction):
            """⏸️ Pause playback"""
            try:
                success, message = await self.playback_service.pause_playback(
                    interaction.guild.id
                )

                if success:
                    embed = create_pause_embed()
                    await interaction.response.send_message(embed=embed)
                else:
                    embed = self.create_error_embed("Lỗi Tạm Dừng", message)
                    await interaction.response.send_message(
                        embed=embed, ephemeral=True
                    )

            except Exception as e:
                await self.handle_command_error(interaction, e, "pause")

        @self.bot.tree.command(name="resume", description="Tiếp tục phát nhạc")
        @require_same_voice_channel
        async def resume_music(interaction: discord.Interaction):
            """▶️ Resume playback"""
            try:
                success, message = await self.playback_service.resume_playback(
                    interaction.guild.id
                )

                if success:
                    embed = create_resume_embed()
                    await interaction.response.send_message(embed=embed)
                else:
                    embed = self.create_error_embed("Lỗi Tiếp Tục", message)
                    await interaction.response.send_message(
                        embed=embed, ephemeral=True
                    )

            except Exception as e:
                await self.handle_command_error(interaction, e, "resume")

        @self.bot.tree.command(name="stop", description="Dừng và xóa hàng đợi")
        @require_same_voice_channel
        async def stop_music(interaction: discord.Interaction):
            """⏹️ Stop music and clear queue"""
            try:
                success = await self.playback_service.stop_playback(interaction.guild.id)

                if success:
                    embed = create_stop_embed()
                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message(ERROR_MESSAGES["no_song_playing"], ephemeral=True)

            except Exception as e:
                await self.handle_command_error(interaction, e, "stop")

        @self.bot.tree.command(name="volume", description="Đặt âm lượng (0-100)")
        @app_commands.describe(volume="Âm lượng từ 0 đến 100")
        @require_same_voice_channel
        async def set_volume(interaction: discord.Interaction, volume: int):
            """🔊 Set playback volume"""
            try:
                # Validate volume using Validator
                is_valid, error_msg = Validator.validate_volume(volume)
                if not is_valid:
                    await interaction.response.send_message(error_msg, ephemeral=True)
                    return

                # Convert volume from 0-100 to 0.0-1.0 for audio player
                volume_float = volume / 100.0

                success, message = await self.playback_service.set_volume(interaction.guild.id, volume_float)

                if success:
                    embed = create_volume_embed(volume)
                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message(f"{ERROR_MESSAGES['cannot_set_volume']}\n{message}", ephemeral=True)

            except Exception as e:
                await self.handle_command_error(interaction, e, "volume")

        @self.bot.tree.command(name="now", description="Hiển thị bài đang phát")
        async def now_playing(interaction: discord.Interaction):
            """🎵 Show currently playing song"""
            try:
                if not interaction.guild:
                    await interaction.response.send_message(ERROR_MESSAGES["guild_only"], ephemeral=True)
                    return

                tracklist = self.get_tracklist(interaction.guild.id)
                current_song = tracklist.current_song
                if not current_song:
                    await interaction.response.send_message(ERROR_MESSAGES["no_song_playing"], ephemeral=True)
                    return

                embed = create_now_playing_embed(current_song)
                await interaction.response.send_message(embed=embed)

                # Track message for real-time updates
                response_msg = await interaction.original_response()
                if response_msg and current_song.id:
                    await self.event_bus_manager.track_message(
                        response_msg,
                        current_song.id,
                        interaction.guild.id,
                        "now_playing",
                    )

            except Exception as e:
                await self.handle_command_error(interaction, e, "now")

        @self.bot.tree.command(name="repeat", description="Set repeat mode")
        @app_commands.describe(mode="off: Tắt lặp, track: Lặp bài hiện tại, queue: Lặp hàng đợi")
        @app_commands.choices(
            mode=[
                app_commands.Choice(name="off", value="off"),
                app_commands.Choice(name="track", value="track"),
                app_commands.Choice(name="queue", value="queue"),
            ]
        )
        async def repeat_mode(interaction: discord.Interaction, mode: str):
            """Set repeat mode"""
            try:
                if not interaction.guild:
                    await interaction.response.send_message(ERROR_MESSAGES["guild_only"], ephemeral=True)
                    return

                success = await self.playback_service.set_repeat_mode(interaction.guild.id, mode)

                if success:
                    embed = create_repeat_mode_embed(mode)
                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message(ERROR_MESSAGES["cannot_set_repeat"], ephemeral=True)

            except Exception as e:
                await self.handle_command_error(interaction, e, "repeat")

        @self.bot.tree.command(name="shuffle", description="Xáo trộn thứ tự tracklist")
        @require_same_voice_channel
        async def shuffle_queue(interaction: discord.Interaction):
            """🔀 Shuffle the current tracklist"""
            try:
                tracklist = self.get_tracklist(interaction.guild.id)

                # Check if there are enough songs to shuffle
                total_songs = tracklist.queue_size
                upcoming_songs = len(tracklist.get_upcoming(limit=1000))

                if total_songs <= 1:
                    embed = create_shuffle_failed_embed("Tracklist chỉ có 1 bài hoặc rỗng, không thể shuffle")
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                if upcoming_songs == 0:
                    embed = create_shuffle_failed_embed("Không có bài nào tiếp theo để shuffle (chỉ còn bài đang phát)")
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                # Perform shuffle
                success = await tracklist.shuffle()

                if success:
                    embed = create_shuffle_embed(upcoming_songs)
                    await interaction.response.send_message(embed=embed)
                    logger.info(f"Shuffled tracklist in guild {interaction.guild.id} - {upcoming_songs} songs")
                else:
                    embed = create_shuffle_failed_embed("Không thể shuffle tracklist")
                    await interaction.response.send_message(embed=embed, ephemeral=True)

            except Exception as e:
                await self.handle_command_error(interaction, e, "shuffle")

    async def process_youtube_playlist(self, interaction: discord.Interaction, query: str):
        success, video_urls, message = await self.youtube_handler.extract_playlist(query)

        if not success or not video_urls:
            return self.create_error_embed("Lỗi Playlist", message)

        return await self.playlist_processor.process_playlist_videos(
            video_urls,
            message,
            interaction.guild.id,
            str(interaction.user),
        )

    async def _handle_play_with_query(self, interaction: discord.Interaction, query: str):
        # Check if YouTube playlist URL
        if self.youtube_handler.is_playlist_url(query):

            await self.bot.interaction_manager.handle_long_operation(
                interaction,
                self.process_youtube_playlist(interaction, query),
                "Đang xử lý YouTube Playlist...",
            )
            return
        else:
            # Regular single video/search - defer to prevent timeout
            await interaction.response.defer()

            # Send initial thinking message
            await interaction.followup.send(f"**Đang xử lý:** {query[:50]}{'...' if len(query) > 50 else ''}")

        try:
            # Check if safe to add (not during playlist switch)
            if interaction.guild.id in self.bot._switching_playlists:
                error_embed = self.create_error_embed("⚠️ Đang xử lý", "Bot đang chuyển playlist, vui lòng đợi...")
                await interaction.followup.send(embed=error_embed)
                return

            # Process the song request
            success, message, song = await self.playback_service.play_request(
                user_input=query,
                guild_id=interaction.guild.id,
                requested_by=str(interaction.user),
                auto_play=True,
            )

            if success and song:
                # Create detailed embed with song info
                embed = self._create_play_success_embed(song, message)
                response_msg = await interaction.followup.send(embed=embed)

                # Track message for real-time title updates
                if response_msg and song.id:
                    await self.event_bus_manager.track_message(response_msg, song.id, interaction.guild.id, "queue_add")
            else:
                # Show error
                error_embed = self.create_error_embed("Lỗi phát nhạc", message)
                await interaction.followup.send(embed=error_embed)

        except Exception as e:
            logger.error(f"Error in play command: {e}")
            error_embed = self.create_error_embed(ERROR_MESSAGES["unexpected_error"], f"Đã xảy ra lỗi: {str(e)}")
            await interaction.followup.send(embed=error_embed)

    async def _handle_play_from_playlist(self, interaction: discord.Interaction):
        """Handle play command without query (from active playlist)"""
        guild_id = interaction.guild.id
        active_playlist = getattr(self.bot, "active_playlists", {}).get(guild_id)

        if not active_playlist:
            await interaction.response.send_message(ERROR_MESSAGES["no_active_playlist"], ephemeral=True)
            return

        # Try to resume if paused
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message(f"**Tiếp tục phát từ playlist:** `{active_playlist}`")
            return

        # Respond immediately to avoid timeout
        embed = self.create_success_embed(
            "⏱ Đang tải playlist…",
            f"**{active_playlist}**\nĐang xử lý các bài hát...",
        )
        await interaction.response.send_message(embed=embed)

        # Start playback from active playlist (async, don't wait)
        try:
            success = await self.playback_service.start_playlist_playback(guild_id, active_playlist)

            # Update the message with result
            if success:
                updated_embed = self.create_success_embed("Đã bắt đầu phát nhạc từ playlist", f"**{active_playlist}**")
            else:
                updated_embed = self.create_error_embed(
                    ERROR_MESSAGES["playlist_playback_error"],
                    f"Không thể phát từ playlist `{active_playlist}`",
                )

            await interaction.edit_original_response(embed=updated_embed)

        except Exception as e:
            logger.error(f"Error in playlist playback: {e}")
            error_embed = self.create_error_embed(ERROR_MESSAGES["playlist_playback_error"], f"Đã xảy ra lỗi: {str(e)}")
            await interaction.edit_original_response(embed=error_embed)

    def _create_play_success_embed(self, song, message: str) -> discord.Embed:
        """Create embed for successful play request"""
        embed = self.create_success_embed("✅ Đã thêm vào hàng đợi", song.display_name)

        # Add song details
        embed.add_field(name="Nguồn", value=song.source_type.value.title(), inline=True)
        embed.add_field(name="Trạng thái", value=song.status.value.title(), inline=True)

        if song.metadata and hasattr(song, "duration_formatted"):
            embed.add_field(name="Thời lượng", value=song.duration_formatted, inline=True)

        return embed
