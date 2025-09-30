"""
Dependency Injection Container for Discord Music Bot
Provides proper dependency management and easier testing
"""

from dataclasses import dataclass
from typing import Optional
import discord
from discord.ext import commands

from ..services.audio_service import AudioService
from ..services.playback import PlaybackService
from ..services.playlist_service import PlaylistService
from ..services.auto_recovery import AutoRecoveryService
from ..services.stream_refresh import StreamRefreshService
from ..domain.entities.library import LibraryManager
from ..utils.interaction_manager import InteractionManager
from ..pkg.logger import logger


@dataclass
class ServiceContainer:
    """
    Service container for dependency injection
    
    Benefits:
    - Centralized service management
    - Easier testing with mock services
    - Clear dependency graph
    - Prevents circular dependencies
    """
    
    audio_service: AudioService
    playback_service: PlaybackService
    playlist_service: PlaylistService
    auto_recovery_service: AutoRecoveryService
    stream_refresh_service: StreamRefreshService
    library_manager: LibraryManager
    interaction_manager: InteractionManager
    
    @classmethod
    def create(cls) -> 'ServiceContainer':
        """
        Factory method to create service container with all dependencies
        
        Returns:
            ServiceContainer: Configured service container
        """
        logger.info("🏗️ Creating service container...")
        
        # Create domain layer
        library_manager = LibraryManager()
        logger.debug("✅ Library manager created")
        
        # Create service layer (with dependencies)
        audio_service = AudioService()
        playback_service = PlaybackService()
        playlist_service = PlaylistService(library_manager)
        auto_recovery_service = AutoRecoveryService()
        stream_refresh_service = StreamRefreshService()
        logger.debug("✅ Services created")
        
        # Create utilities
        interaction_manager = InteractionManager()
        logger.debug("✅ Utilities created")
        
        container = cls(
            audio_service=audio_service,
            playback_service=playback_service,
            playlist_service=playlist_service,
            auto_recovery_service=auto_recovery_service,
            stream_refresh_service=stream_refresh_service,
            library_manager=library_manager,
            interaction_manager=interaction_manager
        )
        
        logger.info("✅ Service container created successfully")
        return container
    
    async def initialize(self, bot: commands.Bot) -> bool:
        """
        Initialize all services
        
        Args:
            bot: Discord bot instance
            
        Returns:
            bool: True if initialization successful
        """
        try:
            logger.info("🚀 Initializing services...")
            
            # Initialize resource management
            await self.audio_service.start_resource_management()
            logger.info("✅ Resource management started")
            
            # Initialize async processing
            success = await self.playback_service.initialize_async_processing(bot)
            if success:
                logger.info("✅ Async processing system started")
            else:
                logger.warning("⚠️ Failed to start async processing system")
            
            # Enable auto-recovery
            self.auto_recovery_service.enable_auto_recovery()
            logger.info("✅ Auto-recovery enabled")
            
            logger.info("✅ All services initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize services: {e}")
            return False
    
    async def shutdown(self):
        """Gracefully shutdown all services"""
        logger.info("🛑 Shutting down services...")
        
        try:
            # Shutdown playback service
            await self.playback_service.shutdown_cache_system()
            logger.info("✅ Playback service shutdown")
            
            # Cleanup audio service
            await self.audio_service.cleanup_all()
            logger.info("✅ Audio service cleanup complete")
            
            logger.info("✅ All services shutdown successfully")
            
        except Exception as e:
            logger.error(f"❌ Error during service shutdown: {e}")
    
    def get_service_stats(self) -> dict:
        """
        Get statistics from all services
        
        Returns:
            dict: Combined statistics from all services
        """
        return {
            "audio_service": self.audio_service.get_resource_stats(),
            "cache_stats": self.playback_service.get_cache_performance(),
        }


# Example usage in MusicBot class:
"""
class MusicBot(commands.Bot):
    def __init__(self):
        super().__init__(...)
        
        # Use dependency injection instead of global singletons
        self.services = ServiceContainer.create()
        
        # Setup commands with injected services
        self._setup_commands()
    
    async def setup_hook(self):
        try:
            # Initialize all services through container
            success = await self.services.initialize(self)
            if not success:
                logger.error("Failed to initialize services")
                return
            
            # ... rest of setup ...
            
        except Exception as e:
            logger.error(f"Setup error: {e}")
            raise
    
    async def close(self):
        # Graceful shutdown through container
        await self.services.shutdown()
        await super().close()
"""
