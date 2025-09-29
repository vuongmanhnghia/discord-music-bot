"""
InteractionManager - Prevent Discord interaction timeouts
Simple utility to handle long-running operations safely
"""

import asyncio
import discord
from typing import Callable, Any
from ..pkg.logger import logger


class InteractionManager:
    """Manage long-running Discord interactions to prevent timeouts"""

    @staticmethod
    async def handle_long_operation(
        interaction: discord.Interaction,
        operation_func: Callable,
        initial_message: str = None,
        *args,
        **kwargs,
    ) -> Any:
        """
        Handle operations that might take >3 seconds
        Automatically defers interaction and uses followup

        Args:
            interaction: Discord interaction
            operation_func: Async function to execute
            initial_message: Optional progress message to show (not used currently, for future enhancement)
            *args, **kwargs: Arguments to pass to operation_func
        """
        try:
            # Always defer first to get 15 minutes instead of 3 seconds
            if not interaction.response.is_done():
                await interaction.response.defer()
                logger.debug(
                    f"Deferred interaction for {interaction.command.name if interaction.command else 'unknown'}"
                )

            # Run the operation
            result = await operation_func(*args, **kwargs)

            # Send result via followup
            if isinstance(result, discord.Embed):
                await interaction.followup.send(embed=result)
            elif isinstance(result, str):
                await interaction.followup.send(result)
            else:
                await interaction.followup.send(str(result))

            return result

        except Exception as e:
            logger.error(f"Error in long operation: {e}")
            error_msg = f"❌ Operation failed: {str(e)[:100]}..."

            try:
                if interaction.response.is_done():
                    await interaction.followup.send(error_msg, ephemeral=True)
                else:
                    await interaction.response.send_message(error_msg, ephemeral=True)
            except discord.HTTPException:
                logger.error(
                    "Failed to send error message - interaction may be expired"
                )

            raise  # Re-raise for proper error handling

    @staticmethod
    async def safe_response(
        interaction: discord.Interaction,
        content: str = None,
        embed: discord.Embed = None,
        ephemeral: bool = False,
    ):
        """
        Safely send response, handling both response and followup cases
        """
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    content=content, embed=embed, ephemeral=ephemeral
                )
            else:
                await interaction.response.send_message(
                    content=content, embed=embed, ephemeral=ephemeral
                )
        except discord.HTTPException as e:
            logger.error(f"Failed to send response: {e}")
