"""Decorators for common command patterns"""

import functools
import asyncio
from typing import Callable, Any
import discord
from discord.ext import commands

from ..pkg.logger import logger
from .core import ErrorEmbedFactory


def handle_command_errors(func: Callable) -> Callable:
    """
    Decorator to handle common command errors gracefully

    Handles:
    - Discord HTTP errors (including rate limits)
    - Timeout errors
    - Value errors (invalid input)
    - General exceptions
    """

    @functools.wraps(func)
    async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
        try:
            return await func(self, interaction, *args, **kwargs)

        except discord.HTTPException as e:
            logger.error(f"HTTP error in {func.__name__}: {e}")

            if e.status == 429:
                # Rate limited
                retry_after = getattr(e, "retry_after", 60)
                embed = ErrorEmbedFactory.create_rate_limit_embed(retry_after)
            else:
                embed = ErrorEmbedFactory.create_error_embed(
                    "Connection Error",
                    f"A connection error occurred. Please try again.\n\n**Error:** {str(e)[:100]}",
                )

            try:
                if interaction.response.is_done():
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
            except:
                pass  # Interaction may have expired

        except asyncio.TimeoutError:
            logger.error(f"Timeout in {func.__name__}")
            embed = ErrorEmbedFactory.create_error_embed("Timeout", "The operation took too long. Please try again.")

            try:
                if interaction.response.is_done():
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
            except:
                pass

        except ValueError as e:
            logger.warning(f"Invalid input in {func.__name__}: {e}")
            embed = ErrorEmbedFactory.create_error_embed("Invalid Input", str(e))

            try:
                if interaction.response.is_done():
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
            except:
                pass

        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}: {e}")
            embed = ErrorEmbedFactory.create_error_embed(
                "Unexpected Error",
                "An unexpected error occurred. The issue has been logged.",
            )

            try:
                if interaction.response.is_done():
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
            except:
                pass

    return wrapper


def require_voice_connection(bot_must_be_connected: bool = False):
    """
    Decorator to check voice connection requirements

    Args:
        bot_must_be_connected: If True, requires bot to already be in voice channel

    Checks:
    - Command is used in a server (not DM)
    - User is in a voice channel
    - Bot is in voice channel (if required)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            # Check if in guild
            if not interaction.guild:
                embed = ErrorEmbedFactory.create_error_embed("Server Only", "This command can only be used in a server.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Check if user is in voice channel
            if not interaction.user.voice:
                embed = ErrorEmbedFactory.create_error_embed(
                    "Not in Voice Channel",
                    "You must be in a voice channel to use this command.",
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Check if bot should be connected
            if bot_must_be_connected:
                voice_client = interaction.guild.voice_client
                if not voice_client or not voice_client.is_connected():
                    embed = ErrorEmbedFactory.create_error_embed(
                        "Bot Not Connected",
                        "The bot is not currently in a voice channel.\nUse `/play` to start playing music.",
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

            return await func(self, interaction, *args, **kwargs)

        return wrapper

    return decorator


def require_same_voice_channel(func: Callable) -> Callable:
    """
    Decorator to ensure user and bot are in the same voice channel

    Used for commands like skip, pause, etc. where user must be
    in the same channel as the bot
    """

    @functools.wraps(func)
    async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
        if not interaction.guild:
            embed = ErrorEmbedFactory.create_error_embed("Server Only", "This command can only be used in a server.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Get user's voice channel
        if not interaction.user.voice:
            embed = ErrorEmbedFactory.create_error_embed(
                "Not in Voice Channel",
                "You must be in a voice channel to use this command.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        user_channel = interaction.user.voice.channel

        # Get bot's voice channel
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            embed = ErrorEmbedFactory.create_error_embed("Bot Not Connected", "The bot is not currently in a voice channel.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        bot_channel = voice_client.channel

        # Check if in same channel
        if user_channel.id != bot_channel.id:
            embed = ErrorEmbedFactory.create_error_embed(
                "Different Voice Channel",
                f"You must be in **{bot_channel.name}** to use this command.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        return await func(self, interaction, *args, **kwargs)

    return wrapper


def log_command_usage(func: Callable) -> Callable:
    """
    Decorator to log command usage for analytics
    """

    @functools.wraps(func)
    async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
        # Log command usage
        user = interaction.user
        guild = interaction.guild
        command_name = func.__name__

        logger.info(
            f"Command: /{command_name} | " f"User: {user.name} ({user.id}) | " f"Guild: {guild.name if guild else 'DM'} ({guild.id if guild else 'N/A'})"
        )

        # Execute command
        result = await func(self, interaction, *args, **kwargs)

        return result

    return wrapper


def defer_response(ephemeral: bool = False, thinking: bool = True):
    """
    Decorator to automatically defer interaction response

    Useful for commands that take time to process

    Args:
        ephemeral: Whether the response should be ephemeral
        thinking: Whether to show "thinking" state
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            # Defer the response
            await interaction.response.defer(ephemeral=ephemeral, thinking=thinking)

            # Execute the command
            return await func(self, interaction, *args, **kwargs)

        return wrapper

    return decorator
