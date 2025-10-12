"""Bot maintenance and background task utilities"""

import asyncio
from ..pkg.logger import logger
from ..services.playback import playback_service
from ..services.auto_recovery import auto_recovery_service


class CacheManager:
    """Manages bot cache warming and cleanup"""

    @staticmethod
    async def warm_cache_on_startup() -> int:
        """Warm cache with popular content on startup"""
        try:
            await asyncio.sleep(10)  # Wait for bot initialization
            
            warmed_count = await playback_service.warm_cache_with_popular()
            
            if warmed_count > 0:
                logger.info(f"🔥 Startup cache warming completed: {warmed_count} songs cached")
            else:
                logger.info("ℹ️ No popular songs to warm cache with on startup")
                
            return warmed_count
        except Exception as e:
            logger.error(f"Error during startup cache warming: {e}")
            return 0

    @staticmethod
    async def perform_cache_maintenance():
        """Perform cache maintenance tasks"""
        try:
            # Get cache performance stats
            cache_stats = await playback_service.get_cache_performance()
            logger.info(f"📊 Cache stats: {cache_stats}")

            # Clean up old cache if hit rate is low
            if cache_stats.get("hit_rate", 1.0) < 0.3:
                logger.info("🧹 Low cache hit rate, performing cleanup...")
                cleanup_stats = await playback_service.cleanup_cache()
                logger.info(f"   Cleaned: {cleanup_stats}")
        except Exception as e:
            logger.warning(f"Cache maintenance error: {e}")


class StreamURLRefreshManager:
    """Manages proactive stream URL refresh for 24/7 operation"""

    @staticmethod
    async def refresh_queue_urls(bot_guilds):
        """Proactively refresh stream URLs in all guild queues"""
        try:
            from ..services.stream_refresh import stream_refresh_service
            from ..services.audio_service import audio_service

            logger.info("🔄 Checking queues for URLs that need refresh...")

            total_refreshed = 0

            for guild in bot_guilds:
                try:
                    queue_manager = audio_service.get_queue_manager(guild.id)
                    if not queue_manager:
                        continue

                    queue_songs = queue_manager.get_all_songs()
                    if not queue_songs:
                        continue

                    logger.debug(f"Checking {len(queue_songs)} songs in guild {guild.name}")

                    # Refresh URLs that will expire soon
                    refreshed = await stream_refresh_service.preemptive_refresh_queue(queue_songs)
                    total_refreshed += refreshed

                    if refreshed > 0:
                        logger.info(f"   🔄 Refreshed {refreshed} URLs in {guild.name}")

                except Exception as guild_error:
                    logger.warning(f"Error refreshing URLs for guild {guild.id}: {guild_error}")
                    continue

            if total_refreshed > 0:
                logger.info(f"✅ Total URLs refreshed: {total_refreshed}")
            else:
                logger.debug("No URLs needed refresh")

        except Exception as e:
            logger.error(f"❌ Error in queue URL refresh: {e}")


class MaintenanceScheduler:
    """Schedules and runs periodic maintenance tasks"""

    @staticmethod
    async def run_scheduled_maintenance(bot_guilds, interval_hours: int = 6):
        """Run scheduled maintenance tasks"""
        logger.info("🔧 Starting scheduled maintenance loop...")

        while True:
            try:
                await asyncio.sleep(interval_hours * 3600)

                logger.info("🔧 Running scheduled maintenance...")
                
                # Run auto-recovery maintenance
                await auto_recovery_service.scheduled_maintenance()

                # Proactive stream URL refresh
                await StreamURLRefreshManager.refresh_queue_urls(bot_guilds)

                # Cache maintenance
                await CacheManager.perform_cache_maintenance()

                logger.info("✅ Scheduled maintenance completed")

            except asyncio.CancelledError:
                logger.info("🔧 Scheduled maintenance cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Scheduled maintenance error: {e}")
