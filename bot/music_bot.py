"""
Modern Discord Music Bot with clean architecture
Implements the complete playback flow with proper separation of concerns
"""

import asyncio
from typing import Dict, Optional

import discord
from discord.ext import commands

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

        except Exception as e:
            logger.error(f"❌ Failed to initialize bot: {e}")
            raise

    async def on_ready(self):
        """Bot ready event"""
        logger.info(f"🎵 {config.BOT_NAME} is ready!")
        logger.info(f"📊 Connected to {len(self.guilds)} guilds")
        logger.info(f"🔑 Command prefix: {config.COMMAND_PREFIX}")
        logger.info(f"🎯 Bot ID: {self.user.id}")

        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{config.COMMAND_PREFIX}help | High-quality streaming",
        )
        await self.change_presence(activity=activity)

    async def on_guild_join(self, guild: discord.Guild):
        """Handle joining new guild"""
        logger.info(f"🆕 Joined new guild: {guild.name} (ID: {guild.id})")
        self._ensure_guild_state(guild.id)

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
        except discord.HTTPException:
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
        """Handle voice state changes - auto disconnect if alone"""
        if member == self.user:
            return

        voice_client = discord.utils.get(self.voice_clients, guild=member.guild)
        if not voice_client:
            return

        # Check if bot is alone in voice channel
        channel = voice_client.channel
        if channel and len([m for m in channel.members if not m.bot]) == 0:
            logger.info(
                f"Bot is alone in voice channel, will disconnect from {member.guild.name}"
            )
            await asyncio.sleep(60)  # Wait 60 seconds

            # Double-check still alone
            if channel and len([m for m in channel.members if not m.bot]) == 0:
                await audio_service.disconnect_from_guild(member.guild.id)

    def _setup_commands(self):
        """Setup all bot commands with clean implementation"""

        @self.command(name="join", aliases=["connect"])
        async def join_voice(ctx):
            """🔗 Join your voice channel"""
            if not ctx.author.voice:
                await ctx.send("❌ You need to be in a voice channel!")
                return

            channel = ctx.author.voice.channel
            success = await audio_service.connect_to_channel(channel)

            if success:
                embed = discord.Embed(
                    title="✅ Connected",
                    description=f"Joined {channel.mention}",
                    color=discord.Color.green(),
                )
            else:
                embed = discord.Embed(
                    title="❌ Connection Failed",
                    description="Failed to join voice channel",
                    color=discord.Color.red(),
                )
            await ctx.send(embed=embed)

        @self.command(name="leave", aliases=["disconnect"])
        async def leave_voice(ctx):
            """👋 Leave voice channel"""
            success = await audio_service.disconnect_from_guild(ctx.guild.id)

            if success:
                embed = discord.Embed(
                    title="👋 Disconnected",
                    description="Left voice channel",
                    color=discord.Color.blue(),
                )
            else:
                embed = discord.Embed(
                    title="❌ Not Connected",
                    description="Not connected to any voice channel",
                    color=discord.Color.red(),
                )
            await ctx.send(embed=embed)

        @self.command(name="play", aliases=["p"])
        async def play_music(ctx, *, query: str):
            """▶️ Play music from URL or search query"""
            # Ensure bot is connected to voice
            if not audio_service.is_connected(ctx.guild.id):
                if ctx.author.voice:
                    await audio_service.connect_to_channel(ctx.author.voice.channel)
                else:
                    await ctx.send("❌ Join a voice channel first!")
                    return

            # Send processing message
            message = await ctx.send(
                f"🔍 Processing: **{query[:50]}{'...' if len(query) > 50 else ''}**"
            )

            try:
                # Process the play request
                success, response_message, song = await playback_service.play_request(
                    user_input=query,
                    guild_id=ctx.guild.id,
                    requested_by=str(ctx.author),
                    auto_play=True,
                )

                if success and song:
                    embed = discord.Embed(
                        title="✅ Added to Queue",
                        description=response_message,
                        color=discord.Color.green(),
                    )

                    # Add source type info
                    embed.add_field(
                        name="Source Type",
                        value=song.source_type.value.title(),
                        inline=True,
                    )

                    embed.add_field(
                        name="Status", value=song.status.value.title(), inline=True
                    )

                    if song.metadata:
                        embed.add_field(
                            name="Duration",
                            value=song.metadata.duration_formatted,
                            inline=True,
                        )

                        if song.metadata.thumbnail_url:
                            embed.set_thumbnail(url=song.metadata.thumbnail_url)
                else:
                    embed = discord.Embed(
                        title="❌ Failed",
                        description=response_message,
                        color=discord.Color.red(),
                    )

                await message.edit(content=None, embed=embed)

            except Exception as e:
                logger.error(f"Error in play command: {e}")
                embed = discord.Embed(
                    title="❌ Error",
                    description=f"An error occurred: {str(e)}",
                    color=discord.Color.red(),
                )
                await message.edit(content=None, embed=embed)

        @self.command(name="skip", aliases=["next"])
        async def skip_song(ctx):
            """⏭️ Skip current song"""
            success, message = await playback_service.skip_current_song(ctx.guild.id)

            if success:
                embed = discord.Embed(
                    title="⏭️ Skipped", description=message, color=discord.Color.blue()
                )
            else:
                embed = discord.Embed(
                    title="❌ Cannot Skip",
                    description=message,
                    color=discord.Color.red(),
                )
            await ctx.send(embed=embed)

        @self.command(name="pause")
        async def pause_music(ctx):
            """⏸️ Pause current playback"""
            success, message = await playback_service.pause_playback(ctx.guild.id)

            color = discord.Color.orange() if success else discord.Color.red()
            title = "⏸️ Paused" if success else "❌ Cannot Pause"

            embed = discord.Embed(title=title, description=message, color=color)
            await ctx.send(embed=embed)

        @self.command(name="resume")
        async def resume_music(ctx):
            """▶️ Resume paused playback"""
            success, message = await playback_service.resume_playback(ctx.guild.id)

            color = discord.Color.green() if success else discord.Color.red()
            title = "▶️ Resumed" if success else "❌ Cannot Resume"

            embed = discord.Embed(title=title, description=message, color=color)
            await ctx.send(embed=embed)

        @self.command(name="stop")
        async def stop_music(ctx):
            """⏹️ Stop playback and clear queue"""
            success, message = await playback_service.stop_playback(ctx.guild.id)

            color = discord.Color.blue() if success else discord.Color.red()
            title = "⏹️ Stopped" if success else "❌ Cannot Stop"

            embed = discord.Embed(title=title, description=message, color=color)
            await ctx.send(embed=embed)

        @self.command(name="queue", aliases=["q"])
        async def show_queue(ctx):
            """📋 Show current queue"""
            status = await playback_service.get_queue_status(ctx.guild.id)

            if not status:
                await ctx.send("❌ No queue information available")
                return

            embed = discord.Embed(title="📋 Current Queue", color=discord.Color.blue())

            # Current song
            current = status["current_song"]
            if current:
                current_info = f"**{current.display_name}**"
                if current.metadata:
                    current_info += f" ({current.metadata.duration_formatted})"

                status_emoji = (
                    "▶️" if status["is_playing"] else "⏸️" if status["is_paused"] else "⏹️"
                )
                embed.add_field(
                    name=f"{status_emoji} Now Playing", value=current_info, inline=False
                )

            # Upcoming songs
            upcoming = status["upcoming_songs"]
            if upcoming:
                upcoming_list = []
                for i, song in enumerate(upcoming, 1):
                    song_info = f"{i}. {song.display_name}"
                    if song.metadata:
                        song_info += f" ({song.metadata.duration_formatted})"
                    upcoming_list.append(song_info)

                embed.add_field(
                    name="⏭️ Up Next", value="\\n".join(upcoming_list), inline=False
                )

            # Queue stats
            position = status["position"]
            embed.add_field(
                name="📊 Stats",
                value=f"Position: {position[0]}/{position[1]}\\nVolume: {status['volume']:.0%}",
                inline=True,
            )

            await ctx.send(embed=embed)

        @self.command(name="volume", aliases=["vol"])
        async def set_volume(ctx, volume: int = None):
            """🔊 Set playback volume (0-100)"""
            if volume is None:
                status = await playback_service.get_queue_status(ctx.guild.id)
                if status:
                    current_vol = int(status["volume"] * 100)
                    embed = discord.Embed(
                        title="🔊 Current Volume",
                        description=f"Volume is **{current_vol}%**",
                        color=discord.Color.blue(),
                    )
                    await ctx.send(embed=embed)
                return

            if not (0 <= volume <= 100):
                await ctx.send("❌ Volume must be between 0 and 100")
                return

            success, message = await playback_service.set_volume(
                ctx.guild.id, volume / 100.0
            )

            if success:
                emoji = (
                    "🔇"
                    if volume == 0
                    else "🔈" if volume < 30 else "🔉" if volume < 70 else "🔊"
                )
                embed = discord.Embed(
                    title=f"{emoji} Volume Set",
                    description=message,
                    color=discord.Color.green(),
                )
            else:
                embed = discord.Embed(
                    title="❌ Volume Error",
                    description=message,
                    color=discord.Color.red(),
                )
            await ctx.send(embed=embed)

        @self.command(name="nowplaying", aliases=["np"])
        async def now_playing(ctx):
            """🎵 Show currently playing song"""
            status = await playback_service.get_queue_status(ctx.guild.id)

            if not status or not status["current_song"]:
                await ctx.send("❌ Nothing is currently playing")
                return

            song = status["current_song"]
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"**{song.display_name}**",
                color=discord.Color.green(),
            )

            if song.metadata:
                embed.add_field(
                    name="Duration", value=song.metadata.duration_formatted, inline=True
                )
                embed.add_field(
                    name="Source", value=song.source_type.value.title(), inline=True
                )

                if song.metadata.album:
                    embed.add_field(
                        name="Album", value=song.metadata.album, inline=True
                    )

                if song.metadata.thumbnail_url:
                    embed.set_thumbnail(url=song.metadata.thumbnail_url)

            # Playback status
            status_parts = []
            if status["is_paused"]:
                status_parts.append("⏸️ Paused")
            elif status["is_playing"]:
                status_parts.append("▶️ Playing")
            else:
                status_parts.append("⏹️ Stopped")

            position = status["position"]
            status_parts.append(f"Position: {position[0]}/{position[1]}")

            embed.add_field(name="Status", value=" • ".join(status_parts), inline=False)

            if song.requested_by:
                embed.set_footer(text=f"Requested by {song.requested_by}")

            await ctx.send(embed=embed)

        @self.command(name="help", aliases=["h"])
        async def show_help(ctx):
            """❓ Show help information"""
            embed = discord.Embed(
                title=f"{config.BOT_NAME} - Help",
                # description="Modern music bot with intelligent processing",
                color=discord.Color.blue(),
            )

            # Connection commands
            connection_cmds = [
                f"> `{config.COMMAND_PREFIX}join`  - Tham gia voice channel",
                f"> `{config.COMMAND_PREFIX}leave` - Rời voice channel",
            ]

            embed.add_field(name="", value="\n".join(connection_cmds), inline=False)

            # Playback commands
            playback_cmds = [
                f"> `{config.COMMAND_PREFIX}play <query>` - Phát nhạc (URL hoặc tìm kiếm)",
                f"> `{config.COMMAND_PREFIX}pause`        - Tạm dừng phát",
                f"> `{config.COMMAND_PREFIX}resume`       - Tiếp tục phát",
                f"> `{config.COMMAND_PREFIX}skip`         - Bỏ qua bài hiện tại",
                f"> `{config.COMMAND_PREFIX}stop`         - Dừng và xóa hàng đợi",
            ]

            embed.add_field(name="", value="\n".join(playback_cmds), inline=False)

            # Queue commands
            queue_cmds = [
                f"> `{config.COMMAND_PREFIX}queue`          - Hiển thị hàng đợi hiện tại",
                f"> `{config.COMMAND_PREFIX}nowplaying`     - Hiển thị bài hiện tại",
                f"> `{config.COMMAND_PREFIX}volume <0-100>` - Đặt âm lượng",
            ]

            embed.add_field(name="", value="\n".join(queue_cmds), inline=False)

            embed.add_field(
                name="",
                value="• YouTube URLs\n• Spotify URLs (chuyển đổi thành YouTube)\n• Tìm kiếm\n• SoundCloud URLs",
                inline=False,
            )

            # embed.set_footer(
            #     text="Bot sử dụng xử lý thông minh để xử lý các nguồn nhạc khác nhau"
            # )

            await ctx.send(embed=embed)

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
