"""
Modern Discfrom .services.audio_service import audio_service
from .services.playback import playback_service
from .services.playlist_service import PlaylistService
from .services.auto_recovery import auto_recovery_service Music Bot with clean architecture
Implements the complete playback flow with proper separation of concerns
"""

import asyncio
import time
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from .config.config import config
from .pkg.logger import logger
from .services.audio_service import audio_service
from .services.playback import playback_service
from .services.playlist_service import PlaylistService
from .services.auto_recovery import auto_recovery_service
from .services.stream_refresh import stream_refresh_service
from .domain.entities.library import LibraryManager
from .domain.valueobjects.source_type import SourceType
from .utils.youtube_playlist_handler import YouTubePlaylistHandler
from .utils.interaction_manager import InteractionManager
from .utils.message_updater import message_update_manager

# Import command handlers
from .commands import CommandRegistry
from .commands.basic_commands import BasicCommandHandler
from .commands.playback_commands import PlaybackCommandHandler
from .commands.queue_commands import QueueCommandHandler
from .commands.playlist_commands import PlaylistCommandHandler
from .commands.advanced_commands import AdvancedCommandHandler


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

        # Setup commands using registry
        self._setup_commands()

    async def setup_hook(self):
        """Initialize bot components"""
        try:
            logger.info("🚀 Initializing bot components...")

            # Start ResourceManager for memory leak prevention
            await audio_service.start_resource_management()
            logger.info("✅ Resource management started")

            # Initialize async processing system
            success = await playback_service.initialize_async_processing(self)
            if success:
                logger.info("✅ Async processing system started")
            else:
                logger.warning("⚠️ Failed to start async processing system")

            # Initialize SmartCache system
            try:
                # Warm cache with popular songs (async, non-blocking)
                asyncio.create_task(self._warm_cache_on_startup())
                logger.info("🚄 SmartCache initialization started")
            except Exception as e:
                logger.warning(f"Cache warming failed: {e}")

            # Start auto-recovery service with scheduled maintenance
            try:
                # Enable auto-recovery
                auto_recovery_service.enable_auto_recovery()

                # Schedule maintenance every 6 hours
                asyncio.create_task(self._run_scheduled_maintenance())
                logger.info(
                    "🔧 Auto-recovery service started with scheduled maintenance"
                )
            except Exception as e:
                logger.warning(f"Auto-recovery service failed to start: {e}")

            # Initialize MessageUpdateManager for real-time updates
            try:
                await message_update_manager.initialize()
                logger.info("✅ Message update manager initialized")
            except Exception as e:
                logger.warning(f"Message update manager failed to initialize: {e}")

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
        """Setup all bot slash commands using command registry"""
        # Initialize command registry
        registry = CommandRegistry(self)

        # Register all command handlers
        registry.register_handler(BasicCommandHandler)
        registry.register_handler(PlaybackCommandHandler)
        registry.register_handler(QueueCommandHandler)
        registry.register_handler(PlaylistCommandHandler)
        registry.register_handler(AdvancedCommandHandler)

        # Setup all commands
        registry.setup_all_commands()

    async def _process_playlist_videos(
        self, video_urls: list, playlist_message: str, guild_id: int, requested_by: str
    ):
        """Helper method to process YouTube playlist videos with progress tracking"""
        added_count = 0
        failed_count = 0

        # Process videos in batches to avoid timeout
        for i, video_url in enumerate(video_urls[:50]):  # Limit to 50 videos
            try:
                success_video, _, song = await playback_service.play_request_cached(
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
                # Step 1: Process song like /play (but without auto_play) using smart caching
                success, response_message, song = (
                    await playback_service.play_request_cached(
                        user_input=video_url,
                        guild_id=guild_id,
                        requested_by=requested_by,
                        auto_play=False,  # Don't auto-start playback
                    )
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
                    description=message,
                    color=discord.Color.green(),
                )
        else:
            embed = discord.Embed(
                title="❌ Lỗi", description=message, color=discord.Color.red()
            )

        return embed

    def _create_lazy_use_playlist_result(
        self,
        success: bool,
        message: str,
        playlist_name: str,
        guild_id: int,
        job_id: Optional[str],
    ):
        """Helper method to create result embed for lazy /use command"""
        if success:
            # Always track the active playlist for this guild
            self.active_playlists[guild_id] = playlist_name

            embed = discord.Embed(
                title=f"Kích hoạt playlist",
                description=f"**{playlist_name} đã được load**\n\n" f"{message}\n\n",
                color=discord.Color.blue(),
            )

            if job_id:
                embed.add_field(
                    name="📊 Lazy Loading Info",
                    value=f"**Job ID**: `{job_id}`\n"
                    f"**Strategy**: Load 3 songs immediately, rest in background\n"
                    f"**Progress**: Use `/playlist_status` to check progress",
                    inline=False,
                )

            embed.set_footer(
                text="💡 First few songs load instantly, others process in background"
            )

        else:
            embed = discord.Embed(
                title="❌ Lỗi", description=message, color=discord.Color.red()
            )

        return embed

    async def _warm_cache_on_startup(self):
        """Warm cache with popular content on startup"""
        try:
            # Wait a bit for bot to fully initialize
            await asyncio.sleep(10)

            # Warm cache with popular songs
            warmed_count = await playback_service.warm_cache_with_popular()

            if warmed_count > 0:
                logger.info(
                    f"🔥 Startup cache warming completed: {warmed_count} songs cached"
                )
            else:
                logger.info("ℹ️ No popular songs to warm cache with on startup")

        except Exception as e:
            logger.error(f"Error during startup cache warming: {e}")

    async def _run_scheduled_maintenance(self):
        """Run scheduled maintenance tasks"""
        logger.info("🔧 Starting scheduled maintenance loop...")

        while True:
            try:
                # Wait 6 hours between maintenance runs
                await asyncio.sleep(6 * 3600)  # 6 hours = 21600 seconds

                logger.info("🔧 Running scheduled maintenance...")
                await auto_recovery_service.scheduled_maintenance()

                # Proactive stream URL refresh for 24/7 operation
                await self._refresh_queue_urls()

                # Also run bot-specific maintenance
                try:
                    # Get cache performance stats
                    cache_stats = await playback_service.get_cache_performance()
                    logger.info(f"📊 Cache stats: {cache_stats}")

                    # Clean up old cache if hit rate is low
                    if cache_stats.get("hit_rate", 1.0) < 0.3:
                        logger.info("🧹 Low cache hit rate, performing cleanup...")
                        cleanup_stats = await playback_service.cleanup_cache()
                        logger.info(f"   Cleaned: {cleanup_stats}")

                except Exception as cache_e:
                    logger.warning(f"Cache maintenance error: {cache_e}")

                logger.info("✅ Scheduled maintenance completed")

            except asyncio.CancelledError:
                logger.info("🔧 Scheduled maintenance cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Scheduled maintenance error: {e}")
                # Continue the loop even if maintenance fails

    async def _refresh_queue_urls(self):
        """Proactively refresh stream URLs in all guild queues"""
        try:
            from .services.stream_refresh import stream_refresh_service

            logger.info("🔄 Checking queues for URLs that need refresh...")

            total_refreshed = 0

            # Check all active guilds
            for guild in self.guilds:
                try:
                    queue_manager = audio_service.get_queue_manager(guild.id)
                    if not queue_manager:
                        continue

                    # Get all songs in queue
                    queue_songs = queue_manager.get_all_songs()
                    if not queue_songs:
                        continue

                    logger.debug(
                        f"Checking {len(queue_songs)} songs in guild {guild.name}"
                    )

                    # Refresh URLs that will expire soon
                    refreshed = await stream_refresh_service.preemptive_refresh_queue(
                        queue_songs
                    )
                    total_refreshed += refreshed

                    if refreshed > 0:
                        logger.info(f"   🔄 Refreshed {refreshed} URLs in {guild.name}")

                except Exception as guild_error:
                    logger.warning(
                        f"Error refreshing URLs for guild {guild.id}: {guild_error}"
                    )
                    continue

            if total_refreshed > 0:
                logger.info(f"✅ Total URLs refreshed: {total_refreshed}")
            else:
                logger.debug("No URLs needed refresh")

        except Exception as e:
            logger.error(f"❌ Error in queue URL refresh: {e}")

    async def close(self):
        """Clean shutdown"""
        logger.info("🛑 Shutting down bot...")

        try:
            # Shutdown SmartCache system
            await playback_service.shutdown_cache_system()
            logger.info("✅ SmartCache shutdown complete")

            # Cleanup audio connections
            await audio_service.cleanup_all()
            logger.info("✅ Bot shutdown complete")

        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")

        await super().close()
