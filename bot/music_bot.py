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
from .pkg.logger import logger

from .domain.entities.queue import QueueManager

from .services.stream_refresh import StreamRefreshService
from .services.playlist_service import PlaylistService
from .services.audio_service import AudioService
from .services.playback_service import PlaybackService

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

# Import utils
from .utils.playlist_processors import PlaylistProcessor
from .utils.youtube import YouTubeHandler


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

        self.stream_refresh_service = StreamRefreshService()
        self.audio_service = AudioService(self.stream_refresh_service)

        self.playback_service = PlaybackService(self.audio_service)
        self.interaction_manager = InteractionManager()

        # Initialize utils
        self.playlist_processor = PlaylistProcessor()
        self.youtube_handler = YouTubeHandler()

        # State
        self.active_playlists: dict[int, str] = {}
        self._switching_playlists: set[int] = set()

        # Setup commands
        self._setup_commands()

    async def setup_hook(self):
        """Initialize bot components"""
        try:
            logger.info("🚀 Initializing bot components...")

            # Initialize async processing
            await self.playback_service.initialize_async_processing(self)

            # Initialize message update manager
            await message_update_manager.initialize()
            logger.info("✅ Message update manager initialized")

            # Start unified health monitoring & auto-recovery
            # asyncio.create_task(self._health_and_recovery_loop())
            # logger.info("💓 Health monitoring & auto-recovery started")

            # Start scheduled maintenance
            # asyncio.create_task(self._maintenance_loop())
            # logger.info("🔧 Scheduled maintenance started")

            # Sync slash commands
            await self._sync_commands()

        except Exception as e:
            logger.error(f"❌ Failed to initialize bot: {e}")
            raise

    # async def _health_and_recovery_loop(self):
    #     """Unified health monitoring and auto-recovery system"""
    #     await self.wait_until_ready()

    #     while not self.is_closed():
    #         try:
    #             await asyncio.sleep(TimeIntervals.HEALTH_CHECK_INTERVAL)

    #             # Check all voice clients
    #             for voice_client in self.voice_clients:
    #                 guild_id = voice_client.guild.id

    #                 # 1. Connection health check
    #                 if not voice_client.is_connected():
    #                     logger.warning(
    #                         f"💔 Disconnected voice client detected: guild {guild_id}"
    #                     )

    #                     # 2. Auto-recovery attempt
    #                     try:
    #                         logger.info(
    #                             f"🔄 Attempting auto-recovery for guild {guild_id}"
    #                         )
    #                         await self.audio_service.ensure_voice_connection(guild_id)

    #                         # 3. Resume playback if there was a current song
    #                         if self.audio_service._queue_managers[
    #                             guild_id
    #                         ].current_song:
    #                             logger.info(f"▶️ Resuming playback for guild {guild_id}")
    #                             await self.audio_service.play_next_song(guild_id)

    #                         logger.info(
    #                             f"✅ Auto-recovery successful for guild {guild_id}"
    #                         )

    #                     except Exception as recovery_error:
    #                         logger.error(
    #                             f"❌ Auto-recovery failed for guild {guild_id}: {recovery_error}"
    #                         )

    #                 # 4. Playback health check (for connected clients)
    #                 elif voice_client.is_connected():
    #                     audio_player = self.audio_service._audio_players.get(guild_id)

    #                     # Check for stuck playback
    #                     if (
    #                         self.audio_service._queue_managers[guild_id]
    #                         and self.audio_service._queue_managers[
    #                             guild_id
    #                         ].current_song
    #                         and audio_player
    #                         and not audio_player.is_playing
    #                     ):

    #                         logger.warning(
    #                             f"⚠️ Playback stuck detected for guild {guild_id}"
    #                         )

    #                         try:
    #                             await self.audio_service.play_next_song(guild_id)
    #                             logger.info(
    #                                 f"✅ Playback recovered for guild {guild_id}"
    #                             )
    #                         except Exception as e:
    #                             logger.error(f"Failed to recover playback: {e}")

    #         except Exception as e:
    #             logger.error(f"Error in health & recovery loop: {e}")
    #             await asyncio.sleep(TimeIntervals.HEALTH_CHECK_INTERVAL)

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
        await self.audio_service.disconnect_from_guild(guild.id)

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
            await self.playback_service.shutdown_cache_system()

            # Cleanup audio connections
            await self.audio_service.cleanup_all()

        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")

        await super().close()
