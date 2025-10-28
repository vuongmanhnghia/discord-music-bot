"""Decorators for common command patterns"""

import functools
import asyncio
from typing import Callable, Any
import discord
from discord.ext import commands

from ..pkg.logger import logger
from .core import ErrorEmbedFactory


def handle_command_errors(func: Callable) -> Callable:
    @functools.wraps(func)
    async def wrapper(interaction: discord.Interaction, *args, **kwargs):
        try:
            return await func(interaction, *args, **kwargs)
        except discord.HTTPException as e:
            logger.error(f"HTTP error in {func.__name__}: {e}")
            if e.status == 429:
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
                pass
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
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            if not interaction.guild:
                embed = ErrorEmbedFactory.create_error_embed("Server Only", "This command can only be used in a server.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if not interaction.user.voice:
                embed = ErrorEmbedFactory.create_error_embed(
                    "Not in Voice Channel",
                    "You must be in a voice channel to use this command.",
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            if bot_must_be_connected:
                voice_client = interaction.guild.voice_client
                if not voice_client or not voice_client.is_connected():
                    embed = ErrorEmbedFactory.create_error_embed(
                        "Bot Not Connected",
                        "The bot is not currently in a voice channel.\nUse `/play` to start playing music.",
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
            return await func(interaction, *args, **kwargs)

        return wrapper

    return decorator


def require_same_voice_channel(func: Callable) -> Callable:
    @functools.wraps(func)
    async def wrapper(interaction: discord.Interaction, *args, **kwargs):
        if not interaction.guild:
            embed = ErrorEmbedFactory.create_error_embed("Server Only", "This command can only be used in a server.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if not interaction.user.voice:
            embed = ErrorEmbedFactory.create_error_embed(
                "Not in Voice Channel",
                "You must be in a voice channel to use this command.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        user_channel = interaction.user.voice.channel
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            embed = ErrorEmbedFactory.create_error_embed("Bot Not Connected", "The bot is not currently in a voice channel.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        bot_channel = voice_client.channel
        if user_channel.id != bot_channel.id:
            embed = ErrorEmbedFactory.create_error_embed(
                "Different Voice Channel",
                f"You must be in **{bot_channel.name}** to use this command.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        return await func(interaction, *args, **kwargs)

    return wrapper


def log_command_usage(func: Callable) -> Callable:
    @functools.wraps(func)
    async def wrapper(interaction: discord.Interaction, *args, **kwargs):
        user = interaction.user
        guild = interaction.guild
        command_name = func.__name__
        logger.info(
            f"Command: /{command_name} | " f"User: {user.name} ({user.id}) | " f"Guild: {guild.name if guild else 'DM'} ({guild.id if guild else 'N/A'})"
        )
        return await func(interaction, *args, **kwargs)

    return wrapper


def defer_response(ephemeral: bool = False, thinking: bool = True):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            await interaction.response.defer(ephemeral=ephemeral, thinking=thinking)
            return await func(interaction, *args, **kwargs)

        return wrapper

    return decorator
