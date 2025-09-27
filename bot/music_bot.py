"""
Modern Discord Music Bot with clean architecture
Implements the complete playback flow with proper separation of concerns
"""

import asyncio
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from .config import config
from .logger import logger
from .services.audio import audio_service
from .services.playback import playback_service


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

        # Setup commands
        self._setup_commands()

    async def setup_hook(self):
        """Initialize bot components"""
        try:
            logger.info("🚀 Initializing bot components...")

            # Services are initialized on first use
            logger.info("✅ Bot components ready")

            # Sync slash commands globally only
            try:
                synced = await self.tree.sync()
                logger.info(f"✅ Synced {len(synced)} slash commands globally")
                
                # Remove guild-specific syncing to avoid rate limits
                # Guild commands will inherit from global commands
                
            except discord.RateLimited as e:
                logger.warning(f"⚠️ Rate limited while syncing commands. Retry after: {e.retry_after}s")
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
        logger.info(f"🔑 Command prefix: {config.COMMAND_PREFIX}")
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
            retry_after = getattr(error, 'retry_after', None) or error.response.headers.get('Retry-After', '60')
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
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
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
        if (channel and 
            isinstance(channel, (discord.VoiceChannel, discord.StageChannel)) and 
            hasattr(channel, 'members') and
            len([m for m in channel.members if not m.bot]) == 0):
            logger.info(f"Bot is alone in voice channel, will disconnect from {member.guild.name}")
            
            await asyncio.sleep(60)  # Wait 60 seconds

            # Double-check still alone
            if (channel and 
                isinstance(channel, (discord.VoiceChannel, discord.StageChannel)) and 
                hasattr(channel, 'members') and
                len([m for m in channel.members if not m.bot]) == 0):
                await audio_service.disconnect_from_guild(member.guild.id)

    def _setup_commands(self):
        """Setup all bot slash commands with clean implementation"""

        @self.tree.command(name="join", description="Tham gia voice channel")
        async def join_voice(interaction: discord.Interaction):
            """Join your voice channel"""
            # Check if user is a Member and has voice state
            if not isinstance(interaction.user, discord.Member) or not interaction.user.voice:
                await interaction.response.send_message(
                    "❌ Bạn cần ở trong voice channel!", ephemeral=True
                )
                return

            channel = interaction.user.voice.channel
            if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                await interaction.response.send_message(
                    "❌ Không thể tham gia channel này!", ephemeral=True
                )
                return

            success = await audio_service.connect_to_channel(channel)

            if success:
                embed = discord.Embed(
                    title=f"Đã tham gia kênh voice {channel.mention}",
                    description=f"{config.BOT_NAME} ・ /help",
                    color=discord.Color.green(),
                )
            else:
                embed = discord.Embed(
                    title="Không thể tham gia voice channel",
                    description=f"{config.BOT_NAME} ・ /help",
                    color=discord.Color.red(),
                )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="leave", description="Rời voice channel")
        async def leave_voice(interaction: discord.Interaction):
            """👋 Leave voice channel"""
            if not interaction.guild:
                await interaction.response.send_message("❌ Chỉ sử dụng trong server!", ephemeral=True)
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

        @self.tree.command(name="play", description="Phát nhạc từ URL hoặc tìm kiếm")
        @app_commands.describe(query="URL hoặc từ khóa tìm kiếm")
        @app_commands.checks.cooldown(1, 3.0, key=lambda i: (i.guild_id, i.user.id))  # 3 second cooldown per user per guild
        async def play_music(interaction: discord.Interaction, query: str):
            """▶️ Play music from URL or search query"""
            if not interaction.guild:
                await interaction.response.send_message("❌ Chỉ sử dụng trong server!", ephemeral=True)
                return
                
            # Ensure bot is connected to voice
            if not audio_service.is_connected(interaction.guild.id):
                if isinstance(interaction.user, discord.Member) and interaction.user.voice:
                    channel = interaction.user.voice.channel
                    if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
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

            # Send processing message
            await interaction.response.send_message(
                f"**{query[:50]}{'...' if len(query) > 50 else ''}**"
            )

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
        @app_commands.checks.cooldown(1, 2.0, key=lambda i: (i.guild_id, i.user.id))  # 2 second cooldown
        async def skip_song(interaction: discord.Interaction):
            """⏭️ Skip current song"""
            if not interaction.guild:
                await interaction.response.send_message("❌ Chỉ sử dụng trong server!", ephemeral=True)
                return
                
            if not audio_service.is_connected(interaction.guild.id):
                await interaction.response.send_message(
                    "❌ Bot chưa kết nối voice!", ephemeral=True
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

        @self.tree.command(name="pause", description="⏸️ Tạm dừng phát")
        async def pause_music(interaction: discord.Interaction):
            """⏸️ Pause current playback"""
            if not interaction.guild:
                await interaction.response.send_message("❌ Chỉ sử dụng trong server!", ephemeral=True)
                return
                
            audio_player = audio_service.get_audio_player(interaction.guild.id)
            if not audio_player:
                await interaction.response.send_message(
                    "❌ Bot chưa kết nối voice!", ephemeral=True
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
                    title="❌ Không có gì đang phát",
                    description="Không có nhạc nào đang phát",
                    color=discord.Color.red(),
                )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="resume", description="Tiếp tục phát nhạc")
        async def resume_music(interaction: discord.Interaction):
            """▶️ Resume paused playback"""
            if not interaction.guild:
                await interaction.response.send_message("❌ Chỉ sử dụng trong server!", ephemeral=True)
                return
                
            audio_player = audio_service.get_audio_player(interaction.guild.id)
            if not audio_player:
                await interaction.response.send_message(
                    "❌ Bot chưa kết nối voice!", ephemeral=True
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
                    title="❌ Không có gì bị tạm dừng",
                    description="Không có nhạc nào bị tạm dừng",
                    color=discord.Color.red(),
                )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="stop", description="Dừng và xóa hàng đợi")
        async def stop_music(interaction: discord.Interaction):
            """⏹️ Stop playback and clear queue"""
            if not interaction.guild:
                await interaction.response.send_message("❌ Chỉ sử dụng trong server!", ephemeral=True)
                return
                
            audio_player = audio_service.get_audio_player(interaction.guild.id)
            if not audio_player:
                await interaction.response.send_message(
                    "❌ Bot chưa kết nối voice!", ephemeral=True
                )
                return

            audio_player.stop()
            queue_manager = audio_service.get_queue_manager(interaction.guild.id)
            if queue_manager:
                queue_manager.clear()

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
                await interaction.response.send_message("❌ Chỉ sử dụng trong server!", ephemeral=True)
                return
                
            queue_manager = audio_service.get_queue_manager(interaction.guild.id)
            if not queue_manager:
                await interaction.response.send_message(
                    "❌ Không có hàng đợi nào!", ephemeral=True
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
        async def set_volume(interaction: discord.Interaction, volume: Optional[int] = None):
            """🔊 Set playback volume (0-100)"""
            if not interaction.guild:
                await interaction.response.send_message("❌ Chỉ sử dụng trong server!", ephemeral=True)
                return
                
            audio_player = audio_service.get_audio_player(interaction.guild.id)
            if not audio_player:
                await interaction.response.send_message(
                    "❌ Bot chưa kết nối voice!", ephemeral=True
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
                    "❌ Âm lượng phải từ 0 đến 100!", ephemeral=True
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
                await interaction.response.send_message("❌ Chỉ sử dụng trong server!", ephemeral=True)
                return
                
            audio_player = audio_service.get_audio_player(interaction.guild.id)
            if not audio_player or not audio_player.current_song:
                await interaction.response.send_message(
                    "❌ Không có bài nào đang phát!", ephemeral=True
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
                await interaction.response.send_message("This command can only be used in a server.")
                return

            guild_id = interaction.guild.id
            queue_manager = audio_service.get_queue_manager(guild_id)
            
            if not queue_manager:
                await interaction.response.send_message("No queue found. Use `/play` first.")
                return

            if mode.lower() not in ["off", "song", "queue"]:
                await interaction.response.send_message("Invalid mode. Use: off, song, or queue")
                return

            queue_manager._repeat_mode = mode.lower()
            
            mode_names = {
                "off": "Tắt lặp",
                "song": "Lặp bài hát",
                "queue": "Lặp hàng đợi"
            }
            
            await interaction.response.send_message(f"Repeat mode set to: **{mode_names[mode.lower()]}**")


        @self.tree.command(name="help", description="Hiển thị thông tin trợ giúp")
        async def show_help(interaction: discord.Interaction):
            """❓ Show help information"""
            embed = discord.Embed(
                title=f"{config.BOT_NAME} - Trợ giúp",
                color=discord.Color.blue(),
            )

            # Connection commands
            connection_cmds = [
                f"> `/join`  - Tham gia voice channel",
                f"> `/leave` - Rời voice channel",
            ]

            embed.add_field(name="", value="\n".join(connection_cmds), inline=False)

            # Playback commands
            playback_cmds = [
                f"> `/play <query>` - Phát nhạc (URL hoặc tìm kiếm)",
                f"> `/pause`        - Tạm dừng phát",
                f"> `/resume`       - Tiếp tục phát",
                f"> `/skip`         - Bỏ qua bài hiện tại",
                f"> `/stop`         - Dừng và xóa hàng đợi",
            ]

            embed.add_field(name="", value="\n".join(playback_cmds), inline=False)

            # Queue commands
            queue_cmds = [
                f"> `/queue`          - Hiển thị hàng đợi hiện tại",
                f"> `/nowplaying`     - Hiển thị bài hiện tại",
                f"> `/volume <0-100>` - Đặt âm lượng",
            ]

            embed.add_field(name="", value="\n".join(queue_cmds), inline=False)

            embed.add_field(
                name="",
                value="• YouTube URLs\n• Spotify URLs (chuyển đổi thành YouTube)\n• Tìm kiếm\n• SoundCloud URLs",
                inline=False,
            )

            await interaction.response.send_message(embed=embed)

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
