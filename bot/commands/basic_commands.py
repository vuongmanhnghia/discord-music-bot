"""
Basic commands for the music bot
Handles ping, join, leave commands
"""

import time
import discord

from . import BaseCommandHandler
from ..pkg.logger import logger
from ..services.audio_service import audio_service
from ..utils.discord_ui import EmbedFactory
from ..config.constants import ERROR_MESSAGES


class BasicCommandHandler(BaseCommandHandler):
    """Handler for basic bot commands"""

    def setup_commands(self):
        """Setup basic commands"""

        @self.bot.tree.command(name="ping", description="Kiểm tra độ trễ bot")
        async def ping_command(interaction: discord.Interaction):
            """🏓 Check bot latency"""
            try:
                start_time = time.time()
                await interaction.response.send_message("🏓 Pong!")
                end_time = time.time()

                latency = round(self.bot.latency * 1000)
                response_time = round((end_time - start_time) * 1000)

                embed = EmbedFactory.success(
                    "🏓 Pong!",
                    "Bot đang hoạt động tốt!",
                    details={
                        "Độ trễ API": f"{latency}ms",
                        "Thời gian phản hồi": f"{response_time}ms",
                    },
                    footer="Thời gian tính bằng milliseconds",
                )
                await interaction.edit_original_response(content=None, embed=embed)

            except Exception as e:
                await self.handle_command_error(interaction, e, "ping")

        @self.bot.tree.command(name="join", description="Tham gia voice channel")
        async def join_command(interaction: discord.Interaction):
            """🔌 Join voice channel"""
            try:
                if not interaction.guild:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["guild_only"], ephemeral=True
                    )
                    return

                if not await self.ensure_user_in_voice(interaction):
                    return

                user_voice_channel = interaction.user.voice.channel

                # Check if already connected to the same channel
                if interaction.guild.voice_client:
                    if interaction.guild.voice_client.channel == user_voice_channel:
                        embed = EmbedFactory.info(
                            "Đã trong voice channel",
                            f"Bot đã ở trong **{user_voice_channel.name}** rồi!",
                            info_fields={"Kênh hiện tại": user_voice_channel.name},
                            footer="Bot đã kết nối",
                        )
                        await interaction.response.send_message(
                            embed=embed, ephemeral=True
                        )
                        return
                    else:
                        # Move to new channel
                        await interaction.guild.voice_client.move_to(user_voice_channel)
                        embed = EmbedFactory.success(
                            "Đã chuyển kênh",
                            f"Bot đã di chuyển đến **{user_voice_channel.name}**!",
                            details={"Kênh mới": user_voice_channel.name},
                            footer="Bot đã sẵn sàng!",
                        )
                        await interaction.response.send_message(embed=embed)
                        return

                # Connect to voice channel
                try:
                    voice_client = await user_voice_channel.connect()

                    # Initialize audio service for this guild
                    await audio_service.initialize_guild(
                        interaction.guild.id, voice_client
                    )

                    embed = EmbedFactory.success(
                        "Đã kết nối",
                        f"Bot đã tham gia **{user_voice_channel.name}**!",
                        details={"Channel": user_voice_channel.name},
                        footer="Sẵn sàng phát nhạc!",
                    )
                    await interaction.response.send_message(embed=embed)

                    logger.info(
                        f"Connected to voice channel: {user_voice_channel.name} in {interaction.guild.name}"
                    )

                except discord.ClientException as e:
                    error_msg = f"{ERROR_MESSAGES['cannot_connect_voice']}: {str(e)}"
                    await interaction.response.send_message(error_msg, ephemeral=True)
                    logger.error(f"Failed to connect to voice: {e}")

            except Exception as e:
                await self.handle_command_error(interaction, e, "join")

        @self.bot.tree.command(name="leave", description="Rời voice channel")
        async def leave_command(interaction: discord.Interaction):
            """👋 Leave voice channel"""
            try:
                if not interaction.guild:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["guild_only"], ephemeral=True
                    )
                    return

                voice_client = interaction.guild.voice_client
                if not voice_client:
                    await interaction.response.send_message(
                        ERROR_MESSAGES["not_connected"], ephemeral=True
                    )
                    return

                if not await self.ensure_same_voice_channel(interaction):
                    return

                channel_name = (
                    voice_client.channel.name if voice_client.channel else "Unknown"
                )

                # Cleanup audio service and disconnect from voice
                await audio_service.disconnect_from_guild(interaction.guild.id)

                embed = EmbedFactory.success(
                    "👋 Đã rời khỏi kênh",
                    "Bot đã ngắt kết nối voice!",
                    details={"Trạng thái": "Đã ngắt kết nối"},
                    footer="Dùng /join để kết nối lại",
                )
                await interaction.response.send_message(embed=embed)

                logger.info(
                    f"Left voice channel: {channel_name} in {interaction.guild.name}"
                )

            except Exception as e:
                await self.handle_command_error(interaction, e, "leave")
