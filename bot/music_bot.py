"""
Modern Discord Music Bot with clean architecture
Implements complete playback flow with proper separation of concerns
"""

import asyncio

import discord
from discord.ext import commands

from .config.config import config
from .pkg.logger import logger
from .services.audio_service import audio_service
from .services.playback import playback_service
from .services.playlist_service import PlaylistService
from .services.auto_recovery import auto_recovery_service
from .domain.entities.library import LibraryManager
from .utils.discord_ui import InteractionManager
from .utils.events import message_update_manager
from .utils.core import VoiceStateHelper, ErrorEmbedFactory
from .utils.playlist_processors import PlaylistProcessor, PlaylistResultFactory
from .utils.maintenance import CacheManager, MaintenanceScheduler

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
            await audio_service.start_resource_management()
            logger.info("✅ Resource management started")

            # Initialize async processing
            success = await playback_service.initialize_async_processing(self)
            if success:
                logger.info("✅ Async processing system started")
            else:
                logger.warning("⚠️ Failed to start async processing system")

            # Initialize cache system (non-blocking)
            asyncio.create_task(CacheManager.warm_cache_on_startup())
            logger.info("🚄 SmartCache initialization started")

            # Start auto-recovery service
            auto_recovery_service.enable_auto_recovery()
            asyncio.create_task(
                MaintenanceScheduler.run_scheduled_maintenance(self.guilds)
            )
            logger.info("🔧 Auto-recovery service started")

            # Initialize message update manager
            await message_update_manager.initialize()
            logger.info("✅ Message update manager initialized")
            
            # Start voice connection health check
            asyncio.create_task(self._voice_health_check_loop())
            logger.info("💓 Voice health check started")

            # Sync slash commands
            await self._sync_commands()

        except Exception as e:
            logger.error(f"❌ Failed to initialize bot: {e}")
            raise

    async def _voice_health_check_loop(self):
        """Periodically check voice connections and recover if needed"""
        await self.wait_until_ready()
        
        while not self.is_closed():
            try:
                # Check every 60 seconds
                await asyncio.sleep(60)
                
                # Check all voice clients
                for voice_client in self.voice_clients:
                    if not voice_client.is_connected():
                        guild_id = voice_client.guild.id
                        logger.warning(f"💔 Detected disconnected voice client in guild {guild_id}")
                        
                        # Try to recover
                        try:
                            await audio_service.ensure_voice_connection(guild_id)
                        except Exception as e:
                            logger.error(f"Failed to recover voice connection for guild {guild_id}: {e}")
                
            except Exception as e:
                logger.error(f"Error in voice health check: {e}")
                await asyncio.sleep(60)  # Continue checking even on error

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
        import traceback
        import sys
        
        # Get exception info
        exc_type, exc_value, exc_traceback = sys.exc_info()
        
        # Log the error
        logger.error(f"Error in {event_method}: {exc_value}")
        logger.error(f"Traceback: {''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))}")
        
        # Handle voice connection errors specifically
        if event_method == "on_voice_state_update" or "voice" in event_method.lower():
            # Check if it's a timeout or connection error
            error_msg = str(exc_value).lower()
            if any(keyword in error_msg for keyword in ["timeout", "cancelled", "websocket", "connection"]):
                logger.warning(f"Voice connection issue detected: {exc_value}")
                await self._attempt_voice_recovery()

    async def _attempt_voice_recovery(self):
        """Attempt to recover from voice connection issues"""
        try:
            logger.info("🔄 Attempting voice connection recovery...")
            
            # Wait a bit before recovery
            await asyncio.sleep(2)
            
            # Check all voice clients
            for voice_client in self.voice_clients:
                if not voice_client.is_connected():
                    guild_id = voice_client.guild.id
                    logger.warning(f"Voice client disconnected for guild {guild_id}")
                    
                    # Try to get the channel we were in
                    queue_manager = audio_service.get_queue_manager(guild_id)
                    if queue_manager and queue_manager.current_song:
                        # Get the voice channel
                        guild = voice_client.guild
                        # Try to reconnect
                        try:
                            logger.info(f"Attempting to reconnect voice in guild {guild_id}")
                            # The audio service will handle reconnection
                            await audio_service.ensure_voice_connection(guild_id)
                        except Exception as e:
                            logger.error(f"Failed to reconnect voice: {e}")
            
            logger.info("✅ Voice recovery attempt completed")
            
        except Exception as e:
            logger.error(f"Error during voice recovery: {e}")
            import traceback
            logger.error(f"Recovery traceback: {traceback.format_exc()}")

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

    # Playlist processing helpers - delegate to utility classes
    async def _process_playlist_videos(self, *args, **kwargs):
        """Process YouTube playlist videos"""
        return await PlaylistProcessor.process_playlist_videos(*args, **kwargs)

    async def _process_add_playlist_videos(self, *args, **kwargs):
        """Process YouTube playlist videos for /add command"""
        return await PlaylistProcessor.process_add_playlist_videos(
            *args, playlist_service=self.playlist_service, **kwargs
        )

    def _create_use_playlist_result(self, *args, **kwargs):
        """Create result embed for /use command"""
        return PlaylistResultFactory.create_use_result(
            *args, active_playlists=self.active_playlists, **kwargs
        )

    def _create_lazy_use_playlist_result(self, *args, **kwargs):
        """Create result embed for lazy /use command"""
        return PlaylistResultFactory.create_lazy_use_result(
            *args, active_playlists=self.active_playlists, **kwargs
        )

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
