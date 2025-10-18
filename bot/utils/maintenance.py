"""Bot maintenance and background task utilities"""

import asyncio
from ..pkg.logger import logger
from ..services.playback import playback_service


class CacheManager:
    """Manages bot cache maintenance"""

    @staticmethod
    async def perform_cache_maintenance():
        """Perform cache maintenance tasks"""
        try:
            # Get cache performance stats
            cache_stats = await playback_service.get_cache_performance()
            logger.info(f"📊 Cache stats: {cache_stats}")

            # Clean up old cache entries
            logger.info("🧹 Performing cache cleanup...")
            cleanup_count = await playback_service.cleanup_cache()
            logger.info(f"   Cleaned {cleanup_count} expired entries")
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
