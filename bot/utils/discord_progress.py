"""
Discord Progress Updates for Async Processing
===========================================

Real-time progress updates via Discord embeds for async song processing.
Provides users with live feedback during background processing.

Features:
- Real-time progress bars in Discord embeds
- Status updates with emojis and colors
- Processing stage information
- Error handling and retry notifications
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import discord

from ..pkg.logger import setup_logger
from ..utils.async_processor import ProcessingTask, ProcessingStatus
from ..utils.message_updater import message_update_manager

logger = setup_logger(__name__)


class DiscordProgressUpdater:
    """
    Manages Discord progress updates for async processing tasks

    Features:
    - Real-time embed updates
    - Progress bars with emojis
    - Status colors and icons
    - Processing stage descriptions
    """

    def __init__(self):
        self.active_messages: Dict[str, discord.Message] = {}
        self.update_lock = asyncio.Lock()

    async def create_initial_progress(
        self, interaction: discord.Interaction, task: ProcessingTask, guild_id: int = None
    ) -> Optional[discord.Message]:
        """Create initial progress message for a task"""
        try:
            embed = self._create_progress_embed(task)

            # Send as followup if interaction was already responded to
            if interaction.response.is_done():
                message = await interaction.followup.send(embed=embed)
            else:
                await interaction.response.send_message(embed=embed)
                message = await interaction.original_response()

            self.active_messages[task.id] = message
            
            # Track message for real-time updates when processing completes
            if message and task.song and task.song.id and guild_id:
                await message_update_manager.track_message(
                    message, task.song.id, guild_id, "processing"
                )
            
            return message

        except Exception as e:
            logger.error(f"Error creating initial progress for task {task.id}: {e}")
            return None

    async def update_progress(self, task: ProcessingTask):
        """Update progress for a task"""
        async with self.update_lock:
            try:
                message = self.active_messages.get(task.id)
                if not message:
                    return

                embed = self._create_progress_embed(task)
                await message.edit(embed=embed)

                # Remove from active messages if task is complete
                if task.status in [
                    ProcessingStatus.COMPLETED,
                    ProcessingStatus.FAILED,
                    ProcessingStatus.CANCELLED,
                ]:
                    # Keep message for a bit, then clean up
                    await asyncio.sleep(5)
                    if task.id in self.active_messages:
                        del self.active_messages[task.id]

            except discord.NotFound:
                # Message was deleted, clean up
                if task.id in self.active_messages:
                    del self.active_messages[task.id]
            except Exception as e:
                logger.error(f"Error updating progress for task {task.id}: {e}")

    def _create_progress_embed(self, task: ProcessingTask) -> discord.Embed:
        """Create progress embed for a task"""

        # Status-based color and emoji
        status_config = {
            ProcessingStatus.QUEUED: {
                "color": discord.Color.orange(),
                "emoji": "⏳",
                "title": "Queued for Processing",
            },
            ProcessingStatus.PROCESSING: {
                "color": discord.Color.blue(),
                "emoji": "🔄",
                "title": "Processing Song",
            },
            ProcessingStatus.COMPLETED: {
                "color": discord.Color.green(),
                "emoji": "✅",
                "title": "Processing Complete",
            },
            ProcessingStatus.FAILED: {
                "color": discord.Color.red(),
                "emoji": "❌",
                "title": "Processing Failed",
            },
            ProcessingStatus.CANCELLED: {
                "color": discord.Color.dark_grey(),
                "emoji": "⏹️",
                "title": "Processing Cancelled",
            },
        }

        config = status_config.get(task.status, status_config[ProcessingStatus.QUEUED])

        # Create embed
        embed = discord.Embed(
            title=f"{config['emoji']} {config['title']}",
            description=f"**{task.song.original_input}**",
            color=config["color"],
            timestamp=datetime.now(),
        )

        # Add progress bar
        if task.status == ProcessingStatus.PROCESSING:
            progress_bar = self._create_progress_bar(task.progress)
            embed.add_field(
                name="📊 Progress",
                value=f"{progress_bar} {task.progress}%",
                inline=False,
            )

            # Add processing stage
            stage = self._get_processing_stage(task.progress)
            if stage:
                embed.add_field(name="🎯 Current Stage", value=stage, inline=True)

        # Add task info
        embed.add_field(
            name="🏷️ Task Info",
            value=f"**ID**: `{task.id}`\n"
            f"**Priority**: {task.priority.name}\n"
            f"**Requested**: <t:{int(task.created_at.timestamp())}:R>",
            inline=True,
        )

        # Add retry info if failed
        if task.status == ProcessingStatus.FAILED and task.retry_count > 0:
            embed.add_field(
                name="🔄 Retry Info",
                value=f"**Attempts**: {task.retry_count}/{task.max_retries}\n"
                f"**Error**: {task.error_message or 'Unknown error'}",
                inline=False,
            )

        # Add final error if permanently failed
        if (
            task.status == ProcessingStatus.FAILED
            and task.retry_count >= task.max_retries
        ):
            embed.add_field(
                name="💀 Final Error",
                value=task.error_message or "Unknown error",
                inline=False,
            )

        # Footer with task ID
        embed.set_footer(text=f"Task: {task.id}")

        return embed

    def _create_progress_bar(self, progress: int, length: int = 20) -> str:
        """Create a visual progress bar"""
        filled = int(length * progress / 100)
        empty = length - filled

        # Different emojis based on progress
        if progress == 100:
            fill_char = "🟩"
        elif progress >= 75:
            fill_char = "🟦"
        elif progress >= 50:
            fill_char = "🟨"
        elif progress >= 25:
            fill_char = "🟧"
        else:
            fill_char = "🟥"

        empty_char = "⬜"

        return f"{''.join([fill_char] * filled)}{''.join([empty_char] * empty)}"

    def _get_processing_stage(self, progress: int) -> Optional[str]:
        """Get current processing stage description"""
        if progress < 20:
            return "🔍 Validating URL..."
        elif progress < 40:
            return "📝 Extracting metadata..."
        elif progress < 60:
            return "📥 Downloading audio info..."
        elif progress < 80:
            return "🎵 Processing audio stream..."
        elif progress < 90:
            return "✨ Finalizing..."
        elif progress < 100:
            return "🎯 Almost done..."
        else:
            return "✅ Complete!"

    async def cleanup_old_messages(self):
        """Clean up old progress messages"""
        try:
            # This would be called periodically to clean up old messages
            # Implementation depends on specific cleanup requirements
            pass
        except Exception as e:
            logger.error(f"Error cleaning up progress messages: {e}")


# Global progress updater instance
discord_progress_updater = DiscordProgressUpdater()


async def send_discord_progress_update(bot_instance, task: ProcessingTask):
    """Send progress update to Discord - called by async processor"""
    try:
        await discord_progress_updater.update_progress(task)
    except Exception as e:
        logger.error(f"Error sending Discord progress update: {e}")


async def create_initial_progress_message(
    interaction: discord.Interaction, task: ProcessingTask
) -> Optional[discord.Message]:
    """Create initial progress message for a task"""
    return await discord_progress_updater.create_initial_progress(interaction, task)


# Enhanced progress callback for better integration
class EnhancedProgressCallback:
    """Enhanced progress callback with Discord integration"""

    def __init__(self, interaction: discord.Interaction):
        self.interaction = interaction
        self.progress_message: Optional[discord.Message] = None

    async def __call__(self, task: ProcessingTask):
        """Progress callback function"""
        try:
            # Create initial message if first update
            if not self.progress_message and task.progress <= 10:
                self.progress_message = await create_initial_progress_message(
                    self.interaction, task
                )

            # Update existing message
            if self.progress_message:
                await discord_progress_updater.update_progress(task)

            # Send completion/error notifications
            if task.status == ProcessingStatus.COMPLETED:
                await self._send_completion_notification(task)
            elif (
                task.status == ProcessingStatus.FAILED
                and task.retry_count >= task.max_retries
            ):
                await self._send_failure_notification(task)

        except Exception as e:
            logger.error(f"Error in enhanced progress callback: {e}")

    async def _send_completion_notification(self, task: ProcessingTask):
        """Send completion notification"""
        try:
            embed = discord.Embed(
                title="🎵 Song Ready!",
                description=f"**{task.song.original_input}** is now ready to play!",
                color=discord.Color.green(),
            )

            # Send as followup to avoid conflicts
            await self.interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error sending completion notification: {e}")

    async def _send_failure_notification(self, task: ProcessingTask):
        """Send failure notification"""
        try:
            embed = discord.Embed(
                title="❌ Processing Failed",
                description=f"Could not process **{task.song.original_input}**",
                color=discord.Color.red(),
            )

            if task.error_message:
                embed.add_field(
                    name="Error Details", value=task.error_message, inline=False
                )

            await self.interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error sending failure notification: {e}")
