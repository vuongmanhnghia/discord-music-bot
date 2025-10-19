"""
Basic commands for the music bot
Handles ping, join, leave commands
"""

import discord

from . import BaseCommandHandler
from ..pkg.logger import logger
from ..utils.discord_ui import EmbedFactory
from ..config.constants import ERROR_MESSAGES

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..music_bot import MusicBot


class BasicCommandHandler(BaseCommandHandler):
    """Handler for basic bot commands"""

    def __init__(self, bot: "MusicBot"):
        super().__init__(bot)
        self.audio_service = bot.audio_service

    def setup_commands(self):
        """Setup basic commands"""

        @self.bot.tree.command(name="ping", description="Kiểm tra độ trễ bot")
        async def ping(interaction: discord.Interaction):
            """🏓 Ping command"""
            try:
                latency = round(self.bot.latency * 1000)
                embed = EmbedFactory.success(
                    "Pong!",
                    f"> Latency: **{latency}ms**",
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                await self.handle_command_error(interaction, e, "ping")

        @self.bot.tree.command(name="join", description="Tham gia voice channel")
        async def join(interaction: discord.Interaction):
            """🔊 Join voice channel"""
            try:
                # Check guild context
                if not interaction.guild:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["guild_only"], ephemeral=True
                    )
                    return

                # Check if user is in voice channel
                if not await self.ensure_user_in_voice(interaction):
                    return

                user_channel = interaction.user.voice.channel

                # Check if bot is already in the same channel
                voice_client = interaction.guild.voice_client
                if voice_client and voice_client.is_connected():
                    if voice_client.channel == user_channel:
                        # Already in same channel
                        embed = EmbedFactory.info(
                            "🔊 Already Connected",
                            f"Bot is already in **{user_channel.name}**",
                            details={"Status": "Connected"},
                            footer="Use /play to start playing music",
                        )
                        await interaction.response.send_message(embed=embed)
                        return
                    else:
                        # Move to user's channel
                        logger.info(
                            f"Moving bot from {voice_client.channel.name} to {user_channel.name}"
                        )

                # Connect to voice channel
                success = await self.audio_service.connect_to_channel(user_channel)

                if success:
                    embed = EmbedFactory.success(
                        "🔊 Joined Voice Channel",
                        f"Connected to **{user_channel.name}**",
                        details={"Channel": user_channel.name, "Status": "Connected"},
                        footer="Ready to play music! Use /play to start",
                    )
                    await interaction.response.send_message(embed=embed)
                else:
                    embed = EmbedFactory.error(
                        "❌ Connection Failed",
                        f"Could not connect to **{user_channel.name}**",
                        suggestions=["Check bot permissions", "Try again in a moment"],
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)

            except Exception as e:
                await self.handle_command_error(interaction, e, "join")

        @self.bot.tree.command(name="leave", description="Bot rời khỏi voice channel")
        async def leave(interaction: discord.Interaction):
            """👋 Leave voice channel"""
            try:
                # Check guild context
                if not interaction.guild:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["guild_only"], ephemeral=True
                    )
                    return

                # Check if bot is connected
                voice_client = interaction.guild.voice_client
                if not voice_client or not voice_client.is_connected():
                    embed = EmbedFactory.info(
                        "ℹ️ Not Connected",
                        "Bot is not in any voice channel",
                        footer="Use /join to connect",
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                channel_name = voice_client.channel.name

                # Disconnect from voice channel
                success = await self.audio_service.disconnect_from_guild(
                    interaction.guild.id
                )

                if success:
                    embed = EmbedFactory.success(
                        "👋 Disconnected",
                        f"Left **{channel_name}**",
                        details={"Status": "Disconnected", "Queue": "Cleared"},
                        footer="Use /join to reconnect",
                    )
                    await interaction.response.send_message(embed=embed)
                else:
                    embed = EmbedFactory.warning(
                        "⚠️ Disconnect Warning",
                        "Bot disconnected but some cleanup may have failed",
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)

            except Exception as e:
                await self.handle_command_error(
                    interaction, e, "leave"
                ) @ self.bot.tree.command(name="stats", description="Xem thống kê bot")

        async def stats(interaction: discord.Interaction):
            """📊 Bot statistics"""
            try:
                stats = self.audio_service.get_resource_stats()

                embed = discord.Embed(
                    title="📊 Bot Statistics",
                    description="Current bot status and resource usage",
                    color=discord.Color.blue(),
                )

                # Audio statistics
                embed.add_field(
                    name="🎵 Active Queues",
                    value=f"`{stats.get('active_queues', 0)}`",
                    inline=True,
                )
                embed.add_field(
                    name="🔊 Voice Connections",
                    value=f"`{stats.get('voice_connections', 0)}`",
                    inline=True,
                )
                embed.add_field(
                    name="🎮 Active Players",
                    value=f"`{stats.get('active_players', 0)}`",
                    inline=True,
                )

                # Bot statistics
                embed.add_field(
                    name="🌐 Guilds",
                    value=f"`{len(self.bot.guilds)}`",
                    inline=True,
                )
                embed.add_field(
                    name="📶 Latency",
                    value=f"`{round(self.bot.latency * 1000)}ms`",
                    inline=True,
                )
                embed.add_field(
                    name="👥 Users",
                    value=f"`{sum(guild.member_count for guild in self.bot.guilds)}`",
                    inline=True,
                )

                embed.set_footer(text=f"Requested by {interaction.user.display_name}")
                embed.timestamp = discord.utils.utcnow()

                await interaction.response.send_message(embed=embed)

            except Exception as e:
                await self.handle_command_error(interaction, e, "stats")
