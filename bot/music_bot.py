"""
Modern Discord Music Bot with clean architecture
Implements the complete playback flow with proper separation of concerns
"""

import asyncio
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from .config.config import config
from .pkg.logger import logger
from .services.audio_service import audio_service
from .services.playback import playback_service
from .services.playlist_service import PlaylistService
from .domain.entities.library import LibraryManager
from .domain.valueobjects.source_type import SourceType
from .utils.youtube_playlist_handler import YouTubePlaylistHandler
from .utils.interaction_manager import InteractionManager


class MusicBot(commands.Bot):
    def __init__(self):
        # Discord intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        super().__init__(
            command_prefix=config.COMMAND_PREFIX,
            intents=intents,
            help_command=None,
            description="Modern Music Bot with intelligent processing",
        )

        # Initialize playlist services
        self.library_manager = LibraryManager()
        self.playlist_service = PlaylistService(self.library_manager)

        # Track current active playlist for each guild
        self.active_playlists: dict[int, str] = {}

        # Initialize InteractionManager
        self.interaction_manager = InteractionManager()

        # Setup commands
        self._setup_commands()

    async def setup_hook(self):
        """Initialize bot components"""
        try:
            logger.info("🚀 Initializing bot components...")

            # Start ResourceManager for memory leak prevention
            await audio_service.start_resource_management()
            logger.info("✅ Resource management started")

            # Sync slash commands globally only
            try:
                synced = await self.tree.sync()
                logger.info(f"✅ Synced {len(synced)} slash commands globally")

                # Remove guild-specific syncing to avoid rate limits
                # Guild commands will inherit from global commands

            except discord.RateLimited as e:
                logger.warning(
                    f"⚠️ Rate limited while syncing commands. Retry after: {e.retry_after}s"
                )
                await asyncio.sleep(e.retry_after)
                # Retry once
                try:
                    synced = await self.tree.sync()
                    logger.info(f"✅ Retried and synced {len(synced)} slash commands")
                except Exception as retry_e:
                    logger.error(f"❌ Failed to sync commands after retry: {retry_e}")
            except discord.HTTPException as e:
                logger.error(f"❌ HTTP error syncing commands: {e}")
            except Exception as e:
                logger.error(f"❌ Failed to sync slash commands: {e}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize bot: {e}")
            raise

    async def on_ready(self):
        """Bot ready event"""
        logger.info(f"🎵 {config.BOT_NAME} is ready!")
        logger.info(f"📊 Connected to {len(self.guilds)} guilds")

        if self.user:
            logger.info(f"🎯 Bot ID: {self.user.id}")

        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name="/help | High-quality streaming",
        )
        await self.change_presence(activity=activity)

    async def on_guild_join(self, guild: discord.Guild):
        """Handle joining new guild"""
        logger.info(f"🆕 Joined new guild: {guild.name} (ID: {guild.id})")
        # Guild state is managed by services automatically

    async def on_guild_remove(self, guild: discord.Guild):
        """Handle leaving guild"""
        logger.info(f"👋 Left guild: {guild.name} (ID: {guild.id})")

        # Cleanup audio connections
        await audio_service.disconnect_from_guild(guild.id)

    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Global command error handler"""
        logger.error(f"Command error in {ctx.command}: {error}")

        if isinstance(error, commands.CommandNotFound):
            embed = discord.Embed(
                title="❌ Unknown Command",
                description=f"Command `{ctx.invoked_with}` not found.\nUse `{config.COMMAND_PREFIX}help` to see available commands.",
                color=discord.Color.red(),
            )

        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="❌ Missing Argument",
                description=f"Missing required argument: `{error.param.name}`\nUse `{config.COMMAND_PREFIX}help {ctx.command}` for usage info.",
                color=discord.Color.red(),
            )

        elif isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                title="❌ Invalid Argument",
                description=f"Invalid argument provided.\nUse `{config.COMMAND_PREFIX}help {ctx.command}` for usage info.",
                color=discord.Color.red(),
            )

        elif isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Missing Permissions",
                description="You don't have the required permissions to use this command.",
                color=discord.Color.red(),
            )

        elif isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏰ Command Cooldown",
                description=f"Command is on cooldown. Try again in {error.retry_after:.1f} seconds.",
                color=discord.Color.orange(),
            )

        # Add rate limit handling
        elif isinstance(error, discord.HTTPException) and error.status == 429:
            retry_after = getattr(
                error, "retry_after", None
            ) or error.response.headers.get("Retry-After", "60")
            embed = discord.Embed(
                title="⚠️ Rate Limited",
                description=f"Bot is being rate limited. Please wait {retry_after} seconds and try again.",
                color=discord.Color.orange(),
            )

        else:
            # Unexpected error
            embed = discord.Embed(
                title="❌ Unexpected Error",
                description=f"An unexpected error occurred: {str(error)}",
                color=discord.Color.red(),
            )

            # Log full traceback for debugging
            logger.exception(f"Unexpected command error: {error}")

        try:
            await ctx.send(embed=embed, delete_after=30)
        except discord.HTTPException as send_error:
            if send_error.status == 429:
                # If we're rate limited sending the error message, just log it
                logger.warning(f"Rate limited when sending error message: {send_error}")
            else:
                # Fallback to simple message if embed fails
                try:
                    await ctx.send(f"❌ Error: {str(error)}", delete_after=30)
                except discord.HTTPException:
                    pass  # Can't send message, give up

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Handle voice state changes"""
        # Only handle when someone leaves
        if before.channel and not after.channel and member.guild:
            # No need for _ensure_guild_state method - services handle this automatically
            pass

        voice_client = discord.utils.get(self.voice_clients, guild=member.guild)
        if not voice_client:
            return

        # Check if bot is alone in voice channel
        channel = voice_client.channel
        if (
            channel
            and isinstance(channel, (discord.VoiceChannel, discord.StageChannel))
            and hasattr(channel, "members")
            and len([m for m in channel.members if not m.bot]) == 0
        ):
            if config.STAY_CONNECTED_24_7:
                logger.info(
                    f"Bot is alone in voice channel in {member.guild.name}, but staying connected (24/7 mode)"
                )
                # 🎵 24/7 Mode: Bot stays connected for continuous music
                # No auto-disconnect - bot remains in channel for 24/7 music service
                # Users can manually use /leave if needed
            else:
                logger.info(
                    f"Bot is alone in voice channel, will disconnect from {member.guild.name}"
                )

                await asyncio.sleep(60)  # Wait 60 seconds

                # Double-check still alone
                if (
                    channel
                    and isinstance(
                        channel, (discord.VoiceChannel, discord.StageChannel)
                    )
                    and hasattr(channel, "members")
                    and len([m for m in channel.members if not m.bot]) == 0
                ):
                    await audio_service.disconnect_from_guild(member.guild.id)

    def _setup_commands(self):
        """Setup all bot slash commands with clean implementation"""

        @self.tree.command(name="ping", description="Kiểm tra độ trễ bot")
        async def ping_bot(interaction: discord.Interaction):
            """🏓 Check bot latency"""
            latency_ms = int(self.latency * 1000)
            embed = discord.Embed(
                title="🏓 Pong!",
                description=f"Độ trễ bot: {latency_ms}ms",
                color=discord.Color.blue(),
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="join", description="Tham gia voice channel")
        async def join_voice(interaction: discord.Interaction):
            # ✅ FIX: Defer immediately để có thêm 15 phút
            await interaction.response.defer()

            try:
                if (
                    isinstance(interaction.user, discord.Member)
                    and interaction.user.voice
                ):
                    channel = interaction.user.voice.channel
                    if isinstance(
                        channel, (discord.VoiceChannel, discord.StageChannel)
                    ):
                        # Connect to voice - có thể mất vài giây
                        await audio_service.connect_to_channel(channel)

                        embed = discord.Embed(
                            title="🔊 Đã tham gia voice channel",
                            description=f"Đã kết nối tới **{channel.name}**",
                            color=discord.Color.green(),
                        )

                        # ✅ Use followup thay vì response (vì đã defer)
                        await interaction.followup.send(embed=embed)

                    else:
                        await interaction.followup.send(
                            "❌ Không thể tham gia channel này!", ephemeral=True
                        )
                else:
                    await interaction.followup.send(
                        "❌ Hãy tham gia voice channel trước!", ephemeral=True
                    )

            except Exception as e:
                logger.error(f"Error in join command: {e}")
                try:
                    await interaction.followup.send(
                        f"❌ Lỗi khi tham gia voice channel: {str(e)}",
                        ephemeral=True,
                    )
                except:
                    # Nếu followup cũng fail, log error
                    logger.error("Failed to send error message to user")

        @self.tree.command(name="leave", description="Rời voice channel")
        async def leave_voice(interaction: discord.Interaction):
            """👋 Leave voice channel"""
            if not interaction.guild:
                await interaction.response.send_message(
                    "⛔ Bot chưa kết nối voice!", ephemeral=True
                )
                return

            success = await audio_service.disconnect_from_guild(interaction.guild.id)

            if success:
                embed = discord.Embed(
                    title="Đã ngắt kết nối voice channel",
                    description=f"{config.BOT_NAME} ・ /help",
                    color=discord.Color.blue(),
                )
            else:
                embed = discord.Embed(
                    title="Chưa kết nối",
                    description=f"{config.BOT_NAME} ・ /help",
                    color=discord.Color.red(),
                )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(
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
            if not interaction.guild:
                await interaction.response.send_message(
                    "⛔ Bot chưa kết nối voice!", ephemeral=True
                )
                return

            # Ensure bot is connected to voice
            if not audio_service.is_connected(interaction.guild.id):
                if (
                    isinstance(interaction.user, discord.Member)
                    and interaction.user.voice
                ):
                    channel = interaction.user.voice.channel
                    if isinstance(
                        channel, (discord.VoiceChannel, discord.StageChannel)
                    ):
                        await audio_service.connect_to_channel(channel)
                    else:
                        await interaction.response.send_message(
                            "❌ Không thể tham gia channel này!", ephemeral=True
                        )
                        return
                else:
                    await interaction.response.send_message(
                        "Hãy tham gia voice channel trước!", ephemeral=True
                    )
                    return

            # Handle two modes: with query or from active playlist
            if query:
                # Mode 1: Play from URL/search query
                # Check if it's a YouTube playlist

                if YouTubePlaylistHandler.is_playlist_url(query):
                    # Handle YouTube playlist - use InteractionManager for long operation
                    async def process_youtube_playlist():
                        # Extract playlist videos
                        success, video_urls, message = (
                            await YouTubePlaylistHandler.extract_playlist_videos(query)
                        )

                        if not success or not video_urls:
                            return discord.Embed(
                                title="❌ Playlist Error",
                                description=message,
                                color=discord.Color.red(),
                            )

                        return await self._process_playlist_videos(
                            video_urls,
                            message,
                            interaction.guild.id,
                            str(interaction.user),
                        )

                    result = await self.interaction_manager.handle_long_operation(
                        interaction,
                        process_youtube_playlist,
                        "🎵 Processing YouTube Playlist...",
                    )
                    return
                else:
                    # Regular single video/search - existing logic
                    await interaction.response.send_message(
                        f"🔍 **{query[:50]}{'...' if len(query) > 50 else ''}**"
                    )
            else:
                # Mode 2: Play from active playlist
                guild_id = interaction.guild.id
                active_playlist = self.active_playlists.get(guild_id)

                if not active_playlist:
                    await interaction.response.send_message(
                        "❌ Chưa có playlist nào được chọn! Sử dụng `/use <playlist>` trước hoặc cung cấp query để tìm kiếm.",
                        ephemeral=True,
                    )
                    return

                queue_manager = audio_service.get_queue_manager(guild_id)
                if not queue_manager:
                    await interaction.response.send_message(
                        "❌ Không tìm thấy queue manager!", ephemeral=True
                    )
                    return

                await interaction.response.defer()

                # Load more songs from active playlist
                success, message = await self.playlist_service.load_playlist_to_queue(
                    active_playlist, queue_manager, str(interaction.user), guild_id
                )

                if success:
                    embed = discord.Embed(
                        title="Đã load playlist",
                        description=f"📋 **{active_playlist}**\n{message}",
                        color=discord.Color.green(),
                    )

                    # Auto-start playing if not currently playing
                    audio_player = audio_service.get_audio_player(guild_id)
                    if audio_player and not audio_player.is_playing:
                        # Start playing the first song in queue
                        try:
                            started = await audio_service.play_next_song(guild_id)
                            if started:
                                embed.add_field(
                                    name="🎵 Trạng thái",
                                    value="Đã bắt đầu phát nhạc!",
                                    inline=False,
                                )
                            else:
                                embed.add_field(
                                    name="⚠️ Lưu ý",
                                    value="Đã thêm vào queue, nhưng chưa có bài nào sẵn sàng phát",
                                    inline=False,
                                )
                        except Exception as e:
                            logger.error(
                                f"Failed to start playback after loading playlist: {e}"
                            )
                            embed.add_field(
                                name="⚠️ Lưu ý",
                                value="Đã thêm vào queue, có lỗi khi bắt đầu phát",
                                inline=False,
                            )
                else:
                    embed = discord.Embed(
                        title="❌ Lỗi", description=message, color=discord.Color.red()
                    )

                await interaction.followup.send(embed=embed)
                return

            try:
                # Process the play request
                success, response_message, song = await playback_service.play_request(
                    user_input=query,
                    guild_id=interaction.guild.id,
                    requested_by=str(interaction.user),
                    auto_play=True,
                )

                if success and song:
                    embed = discord.Embed(
                        title="Đã thêm vào hàng đợi",
                        description=response_message,
                        color=discord.Color.green(),
                    )

                    # Add source type info
                    embed.add_field(
                        name="Nguồn",
                        value=song.source_type.value.title(),
                        inline=True,
                    )

                    embed.add_field(
                        name="Trạng thái", value=song.status.value.title(), inline=True
                    )

                    if song.metadata:
                        embed.add_field(
                            name="Thời lượng",
                            value=song.duration_formatted,
                            inline=True,
                        )

                    # Update the processing message
                    await interaction.edit_original_response(embed=embed)

                else:
                    embed = discord.Embed(
                        title="❌ Lỗi phát nhạc",
                        description=response_message,
                        color=discord.Color.red(),
                    )
                    await interaction.edit_original_response(embed=embed)

            except Exception as e:
                logger.error(f"Error in play command: {e}")
                embed = discord.Embed(
                    title="❌ Lỗi không mong muốn",
                    description=f"Đã xảy ra lỗi: {str(e)}",
                    color=discord.Color.red(),
                )
                await interaction.edit_original_response(embed=embed)

        @self.tree.command(name="skip", description="Bỏ qua bài hiện tại")
        @app_commands.checks.cooldown(
            1, 2.0, key=lambda i: (i.guild_id, i.user.id)
        )  # 2 second cooldown
        async def skip_song(interaction: discord.Interaction):
            """⏭️ Skip current song"""
            if not interaction.guild:
                await interaction.response.send_message(
                    "⛔ Bot chưa kết nối voice!", ephemeral=True
                )
                return

            if not audio_service.is_connected(interaction.guild.id):
                await interaction.response.send_message(
                    "⛔ Bot chưa kết nối voice!", ephemeral=True
                )
                return

            success = await audio_service.skip_to_next(interaction.guild.id)

            if success:
                embed = discord.Embed(
                    title="Đã bỏ qua bài hiện tại",
                    description=f"{config.BOT_NAME} ・ /help",
                    color=discord.Color.blue(),
                )
            else:
                embed = discord.Embed(
                    title="❌ Không có bài nào",
                    description="Không có bài nào để bỏ qua",
                    color=discord.Color.red(),
                )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="pause", description="Tạm dừng phát")
        async def pause_music(interaction: discord.Interaction):
            """⏸️ Pause current playback"""
            if not interaction.guild:
                await interaction.response.send_message(
                    "💢 Chỉ sử dụng trong server!", ephemeral=True
                )
                return

            audio_player = audio_service.get_audio_player(interaction.guild.id)
            if not audio_player:
                await interaction.response.send_message(
                    "⛔ Bot chưa kết nối voice!", ephemeral=True
                )
                return

            success = audio_player.pause()

            if success:
                embed = discord.Embed(
                    title="Đã tạm dừng",
                    description=f"{config.BOT_NAME} ・ /help",
                    color=discord.Color.orange(),
                )
            else:
                embed = discord.Embed(
                    title="Không có gì đang phát",
                    description="💢 Có đang phát nhạc đâu mà tạm dừng",
                    color=discord.Color.red(),
                )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="resume", description="Tiếp tục phát nhạc")
        async def resume_music(interaction: discord.Interaction):
            """Resume paused playback"""
            if not interaction.guild:
                await interaction.response.send_message(
                    "💢 Chỉ sử dụng trong server!", ephemeral=True
                )
                return

            audio_player = audio_service.get_audio_player(interaction.guild.id)
            if not audio_player:
                await interaction.response.send_message(
                    "⛔ Bot chưa kết nối voice!", ephemeral=True
                )
                return

            success = audio_player.resume()

            if success:
                embed = discord.Embed(
                    title="Đã tiếp tục phát nhạc",
                    description=f"{config.BOT_NAME} ・ /help",
                    color=discord.Color.green(),
                )
            else:
                embed = discord.Embed(
                    title=" Không có gì bị tạm dừng",
                    description="Không có nhạc nào bị tạm dừng",
                    color=discord.Color.red(),
                )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="stop", description="Dừng và xóa hàng đợi")
        async def stop_music(interaction: discord.Interaction):
            """⏹️ Stop playback and clear queue"""
            if not interaction.guild:
                await interaction.response.send_message(
                    "⛔ Bot chưa kết nối voice!", ephemeral=True
                )
                return

            audio_player = audio_service.get_audio_player(interaction.guild.id)
            if not audio_player:
                await interaction.response.send_message(
                    "⛔ Bot chưa kết nối voice!", ephemeral=True
                )
                return

            audio_player.stop()
            queue_manager = audio_service.get_queue_manager(interaction.guild.id)
            if queue_manager:
                queue_manager.clear()
                # Clear playlist loaded tracking since queue is cleared
                self.playlist_service.clear_loaded_playlist_tracking(
                    interaction.guild.id
                )

            embed = discord.Embed(
                title="Đã dừng",
                description=f"{config.BOT_NAME} ・ /help",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="queue", description="Hiển thị hàng đợi hiện tại")
        async def show_queue(interaction: discord.Interaction):
            """📋 Show current queue"""
            if not interaction.guild:
                await interaction.response.send_message(
                    "⛔ Bot chưa kết nối voice!", ephemeral=True
                )
                return

            queue_manager = audio_service.get_queue_manager(interaction.guild.id)
            if not queue_manager:
                await interaction.response.send_message(
                    "🚫 Không có hàng đợi nào!", ephemeral=True
                )
                return

            current_song = queue_manager.current_song
            upcoming_songs = queue_manager.get_upcoming(limit=10)

            if not current_song and not upcoming_songs:
                embed = discord.Embed(
                    title="Không có bài nào trong hàng đợi",
                    description=f"{config.BOT_NAME} ・ /help",
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed)
                return

            embed = discord.Embed(
                title="Hàng đợi hiện tại",
                color=discord.Color.blue(),
            )

            # Current song
            if current_song:
                embed.add_field(
                    name="Đang phát",
                    value=f"**{current_song.display_name}**",
                    inline=False,
                )

            # Upcoming songs
            if upcoming_songs:
                queue_text = ""
                for i, song in enumerate(upcoming_songs[:10], 1):
                    queue_text += f"{i}. {song.display_name}\n"

                if len(upcoming_songs) > 10:
                    queue_text += f"... và {len(upcoming_songs) - 10} bài khác"

                embed.add_field(
                    name="Tiếp theo",
                    value=queue_text or "Không có",
                    inline=False,
                )

            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="volume", description="Đặt âm lượng (0-100)")
        @app_commands.describe(volume="Âm lượng từ 0 đến 100")
        async def set_volume(
            interaction: discord.Interaction, volume: Optional[int] = None
        ):
            """🔊 Set playback volume (0-100)"""
            if not interaction.guild:
                await interaction.response.send_message(
                    "⛔ Bot chưa kết nối voice!", ephemeral=True
                )
                return

            audio_player = audio_service.get_audio_player(interaction.guild.id)
            if not audio_player:
                await interaction.response.send_message(
                    "⛔ Bot chưa kết nối voice!", ephemeral=True
                )
                return

            if volume is None:
                # Show current volume
                current_volume = int(audio_player.volume * 100)
                embed = discord.Embed(
                    title=f"Âm lượng hiện tại: {current_volume}%",
                    description=f"{config.BOT_NAME} ・ /help",
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed)
                return

            # Validate volume
            if volume < 0 or volume > 100:
                await interaction.response.send_message(
                    "💢 Âm lượng chỉ có từ 0 đến 100 từ thôi =))", ephemeral=True
                )
                return

            # Set volume
            audio_player.set_volume(volume / 100.0)

            embed = discord.Embed(
                title=f"Đã đặt âm lượng: {volume}%",
                description=f"{config.BOT_NAME} ・ /help",
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="nowplaying", description="Hiển thị bài đang phát")
        async def now_playing(interaction: discord.Interaction):
            """🎵 Show currently playing song"""
            if not interaction.guild:
                await interaction.response.send_message(
                    "⛔ Bot chưa kết nối voice!", ephemeral=True
                )
                return

            audio_player = audio_service.get_audio_player(interaction.guild.id)
            if not audio_player or not audio_player.current_song:
                await interaction.response.send_message(
                    "🚫 Không có bài nào đang phát!", ephemeral=True
                )
                return

            song = audio_player.current_song

            embed = discord.Embed(
                title=f"Đang phát: {song.display_name}",
                description=f"{config.BOT_NAME} ・ /help",
                color=discord.Color.green(),
            )

            # Add metadata if available
            if song.metadata:
                embed.add_field(
                    name="Thời lượng",
                    value=song.duration_formatted,
                    inline=True,
                )

                if song.metadata.artist:
                    embed.add_field(
                        name="Nghệ sĩ",
                        value=song.metadata.artist,
                        inline=True,
                    )

                if song.metadata.album:
                    embed.add_field(
                        name="Album",
                        value=song.metadata.album,
                        inline=True,
                    )

            embed.add_field(
                name="Trạng thái",
                value="Đang phát" if audio_player.is_playing else "Tạm dừng",
                inline=True,
            )

            embed.add_field(
                name="Âm lượng",
                value=f"{int(audio_player.volume * 100)}%",
                inline=True,
            )

            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="repeat", description="Set repeat mode")
        @app_commands.describe(mode="Repeat mode: off, song, queue")
        async def repeat_mode(interaction: discord.Interaction, mode: str):
            """Set repeat mode for the queue"""
            if not interaction.guild:
                await interaction.response.send_message(
                    "This command can only be used in a server."
                )
                return

            guild_id = interaction.guild.id
            queue_manager = audio_service.get_queue_manager(guild_id)

            if not queue_manager:
                await interaction.response.send_message(
                    "No queue found. Use `/play` first."
                )
                return

            if mode.lower() not in ["off", "song", "queue"]:
                await interaction.response.send_message(
                    "Invalid mode. Use: off, song, or queue"
                )
                return

            queue_manager._repeat_mode = mode.lower()

            mode_names = {
                "off": "Tắt lặp",
                "song": "Lặp bài hát",
                "queue": "Lặp hàng đợi",
            }

            await interaction.response.send_message(
                f"Repeat mode set to: **{mode_names[mode.lower()]}**"
            )

        # ===============================
        # PLAYLIST COMMANDS
        # ===============================

        @self.tree.command(
            name="use", description="Chuyển sang playlist và nạp vào queue"
        )
        @app_commands.describe(playlist_name="Tên playlist cần nạp")
        async def use_playlist(interaction: discord.Interaction, playlist_name: str):
            """🎵 Load playlist into queue"""
            if not interaction.guild:
                await interaction.response.send_message(
                    "⛔ Bot chưa kết nối voice!", ephemeral=True
                )
                return

            # Check if bot is connected to voice
            if not audio_service.is_connected(interaction.guild.id):
                await interaction.response.send_message(
                    "❌ Bot cần kết nối voice channel trước! Sử dụng `/join`",
                    ephemeral=True,
                )
                return

            queue_manager = audio_service.get_queue_manager(interaction.guild.id)
            if not queue_manager:
                await interaction.response.send_message(
                    "❌ Không tìm thấy queue manager!", ephemeral=True
                )
                return

            # Use InteractionManager for loading playlist operation
            async def load_playlist_operation():
                success, message = await self.playlist_service.load_playlist_to_queue(
                    playlist_name,
                    queue_manager,
                    str(interaction.user),
                    interaction.guild.id,
                )

                return self._create_use_playlist_result(
                    success, message, playlist_name, interaction.guild.id
                )

            result = await self.interaction_manager.handle_long_operation(
                interaction,
                load_playlist_operation,
                f"🎵 Loading playlist '{playlist_name}'...",
            )
            return

        @self.tree.command(name="create", description="Tạo playlist mới")
        @app_commands.describe(name="Tên playlist")
        async def create_playlist(interaction: discord.Interaction, name: str):
            """📝 Create new playlist"""
            success, message = self.playlist_service.create_playlist(name)

            if success:
                embed = discord.Embed(
                    title=f"Tạo playlist **{name}** thành công",
                    description=message,
                    color=discord.Color.green(),
                )
            else:
                embed = discord.Embed(
                    title="❌ Lỗi", description=message, color=discord.Color.red()
                )

            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="add", description="Thêm bài hát vào playlist hiện tại")
        @app_commands.describe(song_input="URL hoặc tên bài hát")
        async def add_to_active_playlist(
            interaction: discord.Interaction, song_input: str
        ):
            """➕ Add song to active playlist (with processing like /play)"""
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

            # Check if it's a YouTube playlist
            from .utils.youtube_playlist_handler import YouTubePlaylistHandler

            if YouTubePlaylistHandler.is_playlist_url(song_input):
                # Handle YouTube playlist - use InteractionManager for long operation
                async def process_add_playlist():
                    # Extract playlist videos
                    success_playlist, video_urls, message = (
                        await YouTubePlaylistHandler.extract_playlist_videos(song_input)
                    )

                    if not success_playlist or not video_urls:
                        return discord.Embed(
                            title="❌ Playlist Error",
                            description=message,
                            color=discord.Color.red(),
                        )

                    return await self._process_add_playlist_videos(
                        video_urls,
                        message,
                        active_playlist,
                        interaction.guild.id,
                        str(interaction.user),
                    )

                result = await self.interaction_manager.handle_long_operation(
                    interaction,
                    process_add_playlist,
                    "🎵 Adding YouTube Playlist to queue and active playlist...",
                )
                return

            # Regular single video/search - existing logic
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
                            active_playlist,
                            song.original_input,
                            song.source_type,
                            title,
                        )
                    )

                    if playlist_success:
                        embed = discord.Embed(
                            title="✅ Đã thêm vào playlist và queue",
                            description=f"📋 **{active_playlist}**\n🎵 **{song.display_name}**",
                            color=discord.Color.green(),
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

                        if song.metadata:
                            embed.add_field(
                                name="Thời lượng",
                                value=song.duration_formatted,
                                inline=True,
                            )

                        # Show queue position
                        queue_manager = audio_service.get_queue_manager(guild_id)
                        if queue_manager:
                            queue_position = len(queue_manager.get_upcoming()) + 1
                            embed.add_field(
                                name="Vị trí queue",
                                value=f"#{queue_position}",
                                inline=True,
                            )

                    else:
                        embed = discord.Embed(
                            title="⚠️ Đã thêm vào queue nhưng lỗi playlist",
                            description=f"🎵 Song: {song.display_name}\n❌ Playlist: {playlist_message}",
                            color=discord.Color.orange(),
                        )

                else:
                    embed = discord.Embed(
                        title="❌ Lỗi xử lý bài hát",
                        description=response_message,
                        color=discord.Color.red(),
                    )

                # Update the processing message
                await interaction.edit_original_response(embed=embed)

            except Exception as e:
                logger.error(f"Error in enhanced add command: {e}")
                embed = discord.Embed(
                    title="❌ Lỗi không mong muốn",
                    description=f"Đã xảy ra lỗi: {str(e)}",
                    color=discord.Color.red(),
                )
                await interaction.edit_original_response(embed=embed)

        @self.tree.command(
            name="addto", description="Thêm bài hát vào playlist chỉ định"
        )
        @app_commands.describe(
            playlist_name="Tên playlist", song_input="URL hoặc tên bài hát"
        )
        async def add_to_specific_playlist(
            interaction: discord.Interaction, playlist_name: str, song_input: str
        ):
            """➕ Add song to specific playlist"""

            # Check if it's a YouTube playlist
            from .utils.youtube_playlist_handler import YouTubePlaylistHandler

            if YouTubePlaylistHandler.is_playlist_url(song_input):
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

                    embed = discord.Embed(
                        title="🎵 Processing YouTube Playlist",
                        description=f"{message}\n⏳ Adding to playlist '{playlist_name}'...",
                        color=discord.Color.blue(),
                    )

                    # Send initial message
                    await interaction.followup.send(embed=embed)

                    # Process videos
                    for i, video_url in enumerate(
                        video_urls[:50]
                    ):  # Limit to 50 videos
                        try:
                            # Detect source type from input
                            source_type = (
                                SourceType.YOUTUBE
                            )  # Default for playlist videos

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
                                progress_embed = discord.Embed(
                                    title="🎵 Processing YouTube Playlist",
                                    description=f"📋 **{playlist_name}**\n"
                                    f"✅ Added: {added_count} videos\n"
                                    f"❌ Failed: {failed_count} videos\n"
                                    f"⏳ Progress: {i+1}/{len(video_urls)}",
                                    color=discord.Color.blue(),
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
                    final_embed = discord.Embed(
                        title=f"Đã cập nhật playlist {playlist_name}",
                        description=f"Đã thêm: {added_count} bài hát\n"
                        f"Lỗi: {failed_count} bài hát\n"
                        f"Sử dụng `/playlist {playlist_name}` để xem nội dung playlist",
                        color=(
                            discord.Color.green()
                            if added_count > 0
                            else discord.Color.red()
                        ),
                    )

                    await interaction.edit_original_response(embed=final_embed)
                    return

                else:
                    # Failed to process playlist
                    embed = discord.Embed(
                        title="❌ YouTube Playlist Error",
                        description=message,
                        color=discord.Color.red(),
                    )
                    await interaction.followup.send(embed=embed)
                    return

            # Regular single video/search - existing logic
            # Detect source type from input
            source_type = SourceType.YOUTUBE  # Default
            if "spotify.com" in song_input:
                source_type = SourceType.SPOTIFY
            elif "soundcloud.com" in song_input:
                source_type = SourceType.SOUNDCLOUD
            elif not ("http://" in song_input or "https://" in song_input):
                source_type = SourceType.SEARCH_QUERY

            success, message = self.playlist_service.add_to_playlist(
                playlist_name, song_input, source_type, song_input
            )

            if success:
                embed = discord.Embed(
                    title="✅ Đã thêm vào playlist",
                    description=message,
                    color=discord.Color.green(),
                )
            else:
                embed = discord.Embed(
                    title="❌ Lỗi", description=message, color=discord.Color.red()
                )

            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="remove", description="Xóa bài hát khỏi playlist")
        @app_commands.describe(
            playlist_name="Tên playlist", index="Số thứ tự bài hát (bắt đầu từ 1)"
        )
        async def remove_from_playlist(
            interaction: discord.Interaction, playlist_name: str, index: int
        ):
            """➖ Remove song from playlist"""
            success, message = self.playlist_service.remove_from_playlist(
                playlist_name, index
            )

            if success:
                embed = discord.Embed(
                    title="✅ Đã xóa khỏi playlist",
                    description=message,
                    color=discord.Color.green(),
                )
            else:
                embed = discord.Embed(
                    title="❌ Lỗi", description=message, color=discord.Color.red()
                )

            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="playlists", description="Liệt kê tất cả playlist")
        async def list_playlists(interaction: discord.Interaction):
            """📋 List all playlists"""
            playlists = self.playlist_service.list_playlists()

            if not playlists:
                embed = discord.Embed(
                    title="📋 Danh sách playlist",
                    description="Chưa có playlist nào. Sử dụng `/create` để tạo playlist mới.",
                    color=discord.Color.blue(),
                )
            else:
                playlist_text = "\n".join([f"• {name}" for name in playlists])
                embed = discord.Embed(
                    title="📋 Danh sách playlist",
                    description=playlist_text,
                    color=discord.Color.blue(),
                )
                embed.set_footer(text=f"Tổng: {len(playlists)} playlist")

            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="playlist", description="Hiển thị nội dung playlist")
        @app_commands.describe(name="Tên playlist")
        async def show_playlist(interaction: discord.Interaction, name: str):
            """📄 Show playlist contents"""
            playlist_info = self.playlist_service.get_playlist_info(name)

            if not playlist_info:
                embed = discord.Embed(
                    title="❌ Không tìm thấy",
                    description=f"Playlist '{name}' không tồn tại.",
                    color=discord.Color.red(),
                )
            else:
                embed = discord.Embed(
                    title=f"📄 Playlist: {playlist_info['name']}",
                    color=discord.Color.blue(),
                )

                embed.add_field(
                    name="Thông tin",
                    value=f"Tổng số bài: {playlist_info['total_songs']}\n"
                    f"Tạo: {playlist_info['created_at'].strftime('%d/%m/%Y %H:%M')}\n"
                    f"Cập nhật: {playlist_info['updated_at'].strftime('%d/%m/%Y %H:%M')}",
                    inline=False,
                )

                if playlist_info["entries"]:
                    songs_text = ""
                    for i, entry in enumerate(playlist_info["entries"][:10], 1):
                        songs_text += f"{i}. {entry['title'][:50]}{'...' if len(entry['title']) > 50 else ''}\n"

                    if len(playlist_info["entries"]) > 10:
                        songs_text += (
                            f"... và {len(playlist_info['entries']) - 10} bài khác"
                        )

                        embed.add_field(
                            name="Bài hát", value=songs_text or "Trống", inline=False
                        )
                else:
                    embed.add_field(
                        name="Bài hát", value="Playlist trống", inline=False
                    )

            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="delete", description="Xóa playlist")
        @app_commands.describe(name="Tên playlist cần xóa")
        async def delete_playlist(interaction: discord.Interaction, name: str):
            """🗑️ Delete playlist"""
            success, message = self.playlist_service.delete_playlist(name)

            if success:
                embed = discord.Embed(
                    title=f"Đã xóa playlist {name}",
                    description=message,
                    color=discord.Color.green(),
                )
            else:
                embed = discord.Embed(
                    title="❌ Lỗi", description=message, color=discord.Color.red()
                )

            await interaction.response.send_message(embed=embed)

        @self.tree.command(
            name="help",
            description=f"Hiển thị thông tin về {config.BOT_NAME} và các tính năng",
        )
        async def show_help(interaction: discord.Interaction):
            """❓ Show help information"""
            embed = discord.Embed(
                title=f"{config.BOT_NAME} ・ Tổng quan",
                color=discord.Color.blue(),
            )

            # Connection commands
            connection_cmds = [
                f"> `/join`  - Tham gia voice channel",
                f"> `/leave` - Rời voice channel",
            ]

            embed.add_field(name="", value="\n".join(connection_cmds), inline=False)

            # Playlist commands
            playlist_cmds = [
                f"> `/use <name>`      - Chọn playlist và nạp playlist vào `queue`",
                f"> `/create <name>`       - Tạo playlist mới",
                f"> `/add <song>`          - Thêm bài vào playlist hiện tại",
                f"> `/addto <playlist> <song>` - Thêm bài vào playlist chỉ định",
                f"> `/remove <name> <#>`   - Xóa bài khỏi playlist",
                f"> `/playlists`           - Liệt kê tất cả playlist",
                f"> `/playlist <name>`     - Hiển thị thông tin playlist",
                f"> `/delete <name>`       - Xóa playlist",
            ]

            embed.add_field(
                name="Playlist", value="\n".join(playlist_cmds), inline=False
            )

            # Playback commands
            playback_cmds = [
                f"> `/play`           - Phát từ playlist hiện tại",
                f"> `/play <query>`   - Phát nhạc từ URL/tìm kiếm",
                f"> `/pause`          - Tạm dừng phát",
                f"> `/resume`         - Tiếp tục phát",
                f"> `/skip`           - Bỏ qua bài hiện tại",
                f"> `/stop`           - Dừng và xóa hàng đợi",
            ]

            embed.add_field(
                name="Điều khiển", value="\n".join(playback_cmds), inline=False
            )

            # Queue commands
            queue_cmds = [
                f"> `/queue`          - Hiển thị hàng đợi hiện tại",
                f"> `/nowplaying`     - Hiển thị bài đang phát",
                f"> `/volume <0-100>` - Đặt âm lượng",
                f"> `/repeat <mode>`  - Đặt chế độ lặp",
            ]

            embed.add_field(name="Queue", value="\n".join(queue_cmds), inline=False)

            embed.add_field(
                name="Nguồn hỗ trợ",
                value="**• YouTube (Single videos + Playlists)\n• Spotify [comming soon =))]\n• SoundCloud [comming soon too =))]**",
                inline=False,
            )

            embed.add_field(
                name="YouTube Playlist Features",
                value="**• `/play <playlist_url>` - Phát toàn bộ playlist\n• `/add <playlist_url>` - Thêm playlist vào active playlist\n• `/addto <name> <playlist_url>` - Thêm playlist vào playlist chỉ định**",
                inline=False,
            )

            await interaction.response.send_message(embed=embed)

        # ===============================
        # 🔧 Resource Management Commands
        # ===============================

        @self.tree.command(
            name="resources", description="🔧 [Admin] Hiển thị thống kê tài nguyên bot"
        )
        async def show_resources(interaction: discord.Interaction):
            """🔧 Show bot resource statistics (Admin only)"""

            # Simple admin check (you can enhance this)
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ Chỉ admin mới có quyền xem thống kê tài nguyên!", ephemeral=True
                )
                return

            stats = audio_service.get_resource_stats()

            embed = discord.Embed(
                title="🔧 Bot Resource Statistics",
                description="Thống kê sử dụng tài nguyên và hiệu suất",
                color=discord.Color.blue(),
            )

            # Connection Stats
            embed.add_field(
                name="🎵 Audio Connections",
                value=f"**Active Voice Clients**: {stats['total_voice_clients']}\n"
                f"**Audio Players**: {stats['total_audio_players']}\n"
                f"**Queue Managers**: {stats['total_queue_managers']}\n"
                f"**Connections Created**: {stats['connections_created']}\n"
                f"**Connections Cleaned**: {stats['connections_cleaned']}",
                inline=True,
            )

            # Cache Stats
            embed.add_field(
                name="💾 Cache Performance",
                value=f"**Cache Size**: {stats['cache_size']}\n"
                f"**Cache Hits**: {stats['cache_hits']}\n"
                f"**Cache Misses**: {stats['cache_misses']}\n"
                f"**Hit Rate**: {stats['cache_hit_rate']:.1f}%",
                inline=True,
            )

            # Cleanup Stats
            embed.add_field(
                name="🧹 Cleanup Statistics",
                value=f"**Memory Cleanups**: {stats['memory_cleanups']}\n"
                f"**Active Connections**: {stats['active_connections']}\n"
                f"**Status**: {'🟢 Healthy' if stats['active_connections'] < 8 else '🟡 High Usage'}",
                inline=True,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(
            name="cleanup", description="🧹 [Admin] Force cleanup idle resources"
        )
        async def force_cleanup(interaction: discord.Interaction):
            """🧹 Force cleanup of idle resources (Admin only)"""

            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ Chỉ admin mới có quyền force cleanup!", ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            try:
                cleanup_stats = await audio_service.force_cleanup_idle_connections()

                embed = discord.Embed(
                    title="🧹 Cleanup Complete",
                    description="Đã thực hiện dọn dẹp tài nguyên không sử dụng",
                    color=discord.Color.green(),
                )

                embed.add_field(
                    name="📊 Cleanup Results",
                    value=f"**Expired Cache Items**: {cleanup_stats['expired_cache_items']}\n"
                    f"**Idle Connections Removed**: {cleanup_stats['idle_connections']}\n"
                    f"**Remaining Connections**: {cleanup_stats['total_connections'] - cleanup_stats['idle_connections']}",
                    inline=False,
                )

                await interaction.followup.send(embed=embed, ephemeral=True)

            except Exception as e:
                logger.error(f"Error in force cleanup: {e}")
                await interaction.followup.send(
                    f"❌ Lỗi khi cleanup: {str(e)}", ephemeral=True
                )

    async def _process_playlist_videos(
        self, video_urls: list, playlist_message: str, guild_id: int, requested_by: str
    ):
        """Helper method to process YouTube playlist videos with progress tracking"""
        added_count = 0
        failed_count = 0

        # Process videos in batches to avoid timeout
        for i, video_url in enumerate(video_urls[:50]):  # Limit to 50 videos
            try:
                success_video, _, song = await playback_service.play_request(
                    user_input=video_url,
                    guild_id=guild_id,
                    requested_by=requested_by,
                    auto_play=(i == 0),  # Auto-play first song only
                )

                if success_video:
                    added_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                logger.error(f"Error processing playlist video {video_url}: {e}")
                failed_count += 1

        # Return final result embed
        final_embed = discord.Embed(
            title="✅ YouTube Playlist Processed",
            description=f"📋 **{playlist_message}**\n"
            f"✅ Successfully added: {added_count} videos\n"
            f"❌ Failed: {failed_count} videos",
            color=(discord.Color.green() if added_count > 0 else discord.Color.red()),
        )

        if added_count > 0:
            final_embed.add_field(
                name="🎵 Status",
                value="Started playing!" if added_count > 0 else "Added to queue",
                inline=False,
            )

        return final_embed

    async def _process_add_playlist_videos(
        self,
        video_urls: list,
        playlist_message: str,
        active_playlist: str,
        guild_id: int,
        requested_by: str,
    ):
        """Helper method to process YouTube playlist videos for /add command"""
        added_count = 0
        failed_count = 0
        playlist_added_count = 0

        # Process videos in batches to avoid timeout
        for i, video_url in enumerate(video_urls[:50]):  # Limit to 50 videos
            try:
                # Step 1: Process song like /play (but without auto_play)
                success, response_message, song = await playback_service.play_request(
                    user_input=video_url,
                    guild_id=guild_id,
                    requested_by=requested_by,
                    auto_play=False,  # Don't auto-start playback
                )

                if success and song:
                    added_count += 1

                    # Step 2: Add processed song to playlist
                    title = song.metadata.title if song.metadata else video_url
                    playlist_success, playlist_message = (
                        self.playlist_service.add_to_playlist(
                            active_playlist,
                            song.original_input,
                            song.source_type,
                            title,
                        )
                    )

                    if playlist_success:
                        playlist_added_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                logger.error(f"Error processing add playlist video {video_url}: {e}")
                failed_count += 1

        # Return final result embed
        final_embed = discord.Embed(
            title=f"✅ Đã cập nhật playlist {active_playlist}",
            description=f"📋 **{playlist_message}**\n"
            f"✅ Đã thêm vào queue: {added_count} bài hát\n"
            f"✅ Đã thêm vào playlist: {playlist_added_count} bài hát\n"
            f"❌ Lỗi: {failed_count} bài hát",
            color=(discord.Color.green() if added_count > 0 else discord.Color.red()),
        )

        return final_embed

    def _create_use_playlist_result(
        self, success: bool, message: str, playlist_name: str, guild_id: int
    ):
        """Helper method to create result embed for /use command"""
        if success:
            # Always track the active playlist for this guild, even if empty
            self.active_playlists[guild_id] = playlist_name

            # Check if playlist was empty
            if "is empty" in message:
                embed = discord.Embed(
                    title="✅ Đã chọn playlist trống",
                    description=f"📋 **{playlist_name}** đã được đặt làm playlist hiện tại\n"
                    + f"⚠️ {message}\n"
                    + f"💡 Sử dụng `/add <song>` để thêm bài hát",
                    color=discord.Color.orange(),
                )
            else:
                embed = discord.Embed(
                    title="✅ Đã load playlist",
                    description=message
                    + f"\n🎵 Playlist hiện tại: **{playlist_name}**",
                    color=discord.Color.green(),
                )
        else:
            embed = discord.Embed(
                title="❌ Lỗi", description=message, color=discord.Color.red()
            )

        return embed

    async def close(self):
        """Clean shutdown"""
        logger.info("🛑 Shutting down bot...")

        try:
            # Cleanup audio connections
            await audio_service.cleanup_all()
            logger.info("✅ Bot shutdown complete")

        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")

        await super().close()
