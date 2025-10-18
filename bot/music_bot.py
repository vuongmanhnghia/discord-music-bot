"""
Modern Discord Music Bot with clean architecture
Implements complete playback flow with proper separation of concerns
"""

import asyncio
import sys
import traceback

import discord
from discord.ext import commands

from .config.config import config
from .config.time_constants import TimeIntervals
from .pkg.logger import logger
from .services.audio_service import audio_service
from .services.playback import playback_service
from .services.playlist_service import PlaylistService
from .domain.entities.library import LibraryManager
from .utils.discord_ui import InteractionManager
from .utils.events import message_update_manager
from .utils.core import VoiceStateHelper, ErrorEmbedFactory

# Import command handlers
from .commands import CommandRegistry
from .commands.basic_commands import BasicCommandHandler
from .commands.playback_commands import PlaybackCommandHandler
from .commands.queue_commands import QueueCommandHandler
from .commands.playlist_commands import PlaylistCommandHandler
from .commands.advanced_commands import AdvancedCommandHandler


class MusicBot(commands.Bot):
    """Modern Music Bot with intelligent processing"""

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

        # Initialize services
        self.library_manager = LibraryManager()
        self.playlist_service = PlaylistService(self.library_manager)
        self.active_playlists: dict[int, str] = {}
        self.interaction_manager = InteractionManager()

        # Setup commands
        self._setup_commands()

    async def setup_hook(self):
        """Initialize bot components"""
        try:
            logger.info("🚀 Initializing bot components...")

            # Start resource management
            await audio_service.resource_manager.start_cleanup_task()
            logger.info("✅ Resource management started")

            # Initialize async processing
            success = await playback_service.initialize_async_processing(self)
            if success:
                logger.info("✅ Async processing system started")
            else:
                logger.warning("⚠️ Failed to start async processing system")

            # Initialize message update manager
            await message_update_manager.initialize()
            logger.info("✅ Message update manager initialized")

            # Start unified health monitoring & auto-recovery
            asyncio.create_task(self._health_and_recovery_loop())
            logger.info("💓 Health monitoring & auto-recovery started")

            # Start scheduled maintenance
            asyncio.create_task(self._maintenance_loop())
            logger.info("🔧 Scheduled maintenance started")

            # Sync slash commands
            await self._sync_commands()

        except Exception as e:
            logger.error(f"❌ Failed to initialize bot: {e}")
            raise

    async def _health_and_recovery_loop(self):
        """Unified health monitoring and auto-recovery system"""
        await self.wait_until_ready()

        while not self.is_closed():
            try:
                await asyncio.sleep(TimeIntervals.HEALTH_CHECK_INTERVAL)

                # Check all voice clients
                for voice_client in self.voice_clients:
                    guild_id = voice_client.guild.id

                    # 1. Connection health check
                    if not voice_client.is_connected():
                        logger.warning(
                            f"💔 Disconnected voice client detected: guild {guild_id}"
                        )

                        # 2. Auto-recovery attempt
                        try:
                            logger.info(
                                f"🔄 Attempting auto-recovery for guild {guild_id}"
                            )
                            await audio_service.ensure_voice_connection(guild_id)

                            # 3. Resume playback if there was a current song
                            queue_manager = audio_service.get_queue_manager(guild_id)
                            if queue_manager and queue_manager.current_song:
                                logger.info(f"▶️ Resuming playback for guild {guild_id}")
                                await audio_service.play_next_song(guild_id)

                            logger.info(
                                f"✅ Auto-recovery successful for guild {guild_id}"
                            )

                        except Exception as recovery_error:
                            logger.error(
                                f"❌ Auto-recovery failed for guild {guild_id}: {recovery_error}"
                            )

                    # 4. Playback health check (for connected clients)
                    elif voice_client.is_connected():
                        audio_player = audio_service._audio_players.get(guild_id)
                        queue_manager = audio_service.get_queue_manager(guild_id)

                        # Check for stuck playback
                        if (
                            queue_manager
                            and queue_manager.current_song
                            and audio_player
                            and not audio_player.is_playing
                        ):

                            logger.warning(
                                f"⚠️ Playback stuck detected for guild {guild_id}"
                            )

                            try:
                                await audio_service.play_next_song(guild_id)
                                logger.info(
                                    f"✅ Playback recovered for guild {guild_id}"
                                )
                            except Exception as e:
                                logger.error(f"Failed to recover playback: {e}")

            except Exception as e:
                logger.error(f"Error in health & recovery loop: {e}")
                await asyncio.sleep(TimeIntervals.HEALTH_CHECK_INTERVAL)

    async def _maintenance_loop(self):
        """Scheduled maintenance tasks"""
        await self.wait_until_ready()

        # Initial delay before first maintenance
        await asyncio.sleep(TimeIntervals.MAINTENANCE_INITIAL_DELAY)

        while not self.is_closed():
            try:
                logger.info("🔧 Running scheduled maintenance...")

                # 1. Cleanup expired cache
                try:
                    from .utils.maintenance import CacheManager

                    await CacheManager.perform_cache_maintenance()
                except Exception as e:
                    logger.error(f"  ✗ Cache maintenance failed: {e}")

                # 2. Cleanup idle connections
                try:
                    cleaned = await audio_service.force_cleanup_idle_connections()
                    logger.info(f"  ✓ Cleaned {cleaned} idle connections")
                except Exception as e:
                    logger.error(f"  ✗ Connection cleanup failed: {e}")

                # 3. Refresh stream URLs in queues
                try:
                    from .utils.maintenance import StreamURLRefreshManager

                    await StreamURLRefreshManager.refresh_queue_urls(self.guilds)
                except Exception as e:
                    logger.error(f"  ✗ Stream URL refresh failed: {e}")

                # 4. Log statistics
                try:
                    stats = audio_service.get_resource_stats()
                    logger.info(f"  📊 Resource stats: {stats}")
                except Exception as e:
                    logger.error(f"  ✗ Stats logging failed: {e}")

                logger.info("✅ Scheduled maintenance complete")

                # Wait before next maintenance
                await asyncio.sleep(TimeIntervals.MAINTENANCE_INTERVAL)

            except asyncio.CancelledError:
                logger.info("🔧 Maintenance loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in maintenance loop: {e}")
                await asyncio.sleep(TimeIntervals.MAINTENANCE_INTERVAL)

    async def _sync_commands(self):
        """Sync slash commands with rate limit handling"""
        try:
            synced = await self.tree.sync()
            logger.info(f"✅ Synced {len(synced)} slash commands globally")
        except discord.RateLimited as e:
            logger.warning(f"⚠️ Rate limited. Retry after: {e.retry_after}s")
            await asyncio.sleep(e.retry_after)
            try:
                synced = await self.tree.sync()
                logger.info(f"✅ Retried and synced {len(synced)} commands")
            except Exception as retry_e:
                logger.error(f"❌ Failed after retry: {retry_e}")
        except discord.HTTPException as e:
            logger.error(f"❌ HTTP error syncing commands: {e}")
        except Exception as e:
            logger.error(f"❌ Failed to sync commands: {e}")

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

    async def on_guild_remove(self, guild: discord.Guild):
        """Handle leaving guild"""
        logger.info(f"👋 Left guild: {guild.name} (ID: {guild.id})")
        await audio_service.disconnect_from_guild(guild.id)

    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Global command error handler"""
        logger.error(f"Command error in {ctx.command}: {error}")

        # Create appropriate embed based on error type
        if isinstance(error, commands.CommandNotFound):
            embed = ErrorEmbedFactory.create_error_embed(
                "Unknown Command",
                f"Command `{ctx.invoked_with}` not found.\nUse `{config.COMMAND_PREFIX}help` for available commands.",
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = ErrorEmbedFactory.create_error_embed(
                "Missing Argument",
                f"Missing required argument: `{error.param.name}`\nUse `{config.COMMAND_PREFIX}help {ctx.command}` for usage info.",
            )
        elif isinstance(error, commands.BadArgument):
            embed = ErrorEmbedFactory.create_error_embed(
                "Invalid Argument",
                f"Invalid argument provided.\nUse `{config.COMMAND_PREFIX}help {ctx.command}` for usage info.",
            )
        elif isinstance(error, commands.MissingPermissions):
            embed = ErrorEmbedFactory.create_error_embed(
                "Missing Permissions",
                "You don't have the required permissions to use this command.",
            )
        elif isinstance(error, commands.CommandOnCooldown):
            embed = ErrorEmbedFactory.create_cooldown_embed(error.retry_after)
        elif isinstance(error, discord.HTTPException) and error.status == 429:
            retry_after = getattr(
                error, "retry_after", None
            ) or error.response.headers.get("Retry-After", "60")
            embed = ErrorEmbedFactory.create_rate_limit_embed(float(retry_after))
        else:
            embed = ErrorEmbedFactory.create_error_embed(
                "Unexpected Error",
                f"An unexpected error occurred: {str(error)}",
            )
            logger.exception(f"Unexpected command error: {error}")

        # Send error message
        try:
            await ctx.send(embed=embed, delete_after=30)
        except discord.HTTPException as send_error:
            if send_error.status != 429:
                try:
                    await ctx.send(f"❌ Error: {str(error)}", delete_after=30)
                except discord.HTTPException:
                    pass

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Handle voice state changes - auto disconnect if alone"""
        # Only handle when someone leaves
        if not (before.channel and not after.channel and member.guild):
            return

        voice_client = discord.utils.get(self.voice_clients, guild=member.guild)
        if not voice_client:
            return

        # Check if bot is alone in channel
        if not VoiceStateHelper.is_alone_in_channel(voice_client):
            return

        # Handle based on 24/7 mode
        if config.STAY_CONNECTED_24_7:
            logger.info(
                f"Bot alone in {member.guild.name}, staying connected (24/7 mode)"
            )
            return

        # Auto-disconnect after delay
        logger.info(f"Bot alone in {member.guild.name}, will disconnect")
        await VoiceStateHelper.handle_auto_disconnect(
            voice_client, member.guild.id, delay=60
        )

    async def on_error(self, event_method: str, *args, **kwargs):
        """Handle errors in event listeners"""
        # Get exception info
        exc_type, exc_value, exc_traceback = sys.exc_info()

        # Log the error
        logger.error(f"Error in {event_method}: {exc_value}")
        logger.error(
            f"Traceback: {''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))}"
        )

    def _setup_commands(self):
        """Setup all bot slash commands using command registry"""
        registry = CommandRegistry(self)

        # Register all command handlers
        for handler in [
            BasicCommandHandler,
            PlaybackCommandHandler,
            QueueCommandHandler,
            PlaylistCommandHandler,
            AdvancedCommandHandler,
        ]:
            registry.register_handler(handler)

        # Setup all commands
        registry.setup_all_commands()

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
