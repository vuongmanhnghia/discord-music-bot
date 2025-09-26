import asyncio
import random
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

from src.queue.queue_view import QueueView
from src.playlist_manage import check_playlist_exists, get_all_songs

load_dotenv()

BOT_NAME = os.getenv("BOT_NAME")
BOT_TOKEN = os.getenv("BOT_TOKEN")
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set")

intents = discord.Intents.default()  # Enable message content intent
intents.message_content = True


class MusicBot(commands.Bot):
    def __init__(self):
        """Initialize the bot"""
        super().__init__(
            command_prefix=COMMAND_PREFIX,
            intents=intents,
            help_command=None,  # Disable default help command
        )
        self.queues = {}

    async def on_ready(self):
        """Called when the bot is ready"""
        print(f"Đã đăng nhập với tên {self.user}")
        print("Bot đã sẵn sàng hoạt động trên server!")
        print("------------------------------------")

    async def play(self, ctx: commands.Context, *, song_name: str = None):
        """Play a song"""
        if not ctx.author.voice:
            await ctx.send(f"Bạn cần phải ở trong một kênh thoại để dùng lệnh này!")
            return

        voice_channel = ctx.author.voice.channel
        voice_client = discord.utils.get(self.voice_clients, guild=ctx.guild)

        if not voice_client:
            voice_client = await voice_channel.connect()
        elif voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)

        if voice_client.is_playing():
            voice_client.stop()

        if ctx.guild.id in self.queues:
            del self.queues[ctx.guild.id]

        if song_name:  # Play specific song
            found, song_path = await check_playlist_exists(song_name)
            if not found:
                await ctx.send(
                    f"Không tìm thấy bài hát **{song_name}** trong playlist!"
                )
                return

            try:
                source = discord.FFmpegPCMAudio(song_path)
                voice_client.play(source)
                await ctx.send(f"🎶 Đang phát: **{song_name}**")
            except Exception as e:
                await ctx.send(f"❌ Lỗi khi phát nhạc: {str(e)}")
                return

        else:  # Play all songs in playlist
            playlist = await get_all_songs()

            if not playlist:
                await ctx.send(f"Không có bài hát nào trong playlist!")
                return

            self.queues[ctx.guild.id] = playlist
            await ctx.send(
                f"▶ Bắt đầu phát **{len(playlist)}** bài hát trong playlist."
            )

            await self.play_next(ctx)

    async def stop(self, ctx: commands.Context):
        """Stop the bot"""
        if ctx.guild.id in self.queues:
            del self.queues[ctx.guild.id]
        voice_client = discord.utils.get(self.voice_clients, guild=ctx.guild)
        if voice_client and voice_client.is_connected():
            voice_client.stop()
            await voice_client.disconnect()
            await ctx.send(
                "Đã dừng nhạc, xóa hàng đợi và ngắt kết nối. Hẹn gặp lại! 👋"
            )
        else:
            await ctx.send("Bot đang không ở trong kênh thoại nào cả.")

    async def play_next(self, ctx: commands.Context):
        """Play the next song in the queue"""
        if ctx.guild.id in self.queues and self.queues[ctx.guild.id]:
            voice_client = discord.utils.get(self.voice_clients, guild=ctx.guild)
            if voice_client and voice_client.is_connected():
                song_path = self.queues[ctx.guild.id].pop(0)
                self.queues[ctx.guild.id].append(song_path)
                song_name = os.path.splitext(os.path.basename(song_path))[0]

                try:
                    source = discord.FFmpegPCMAudio(song_path)

                    def after_playing(error):
                        if error:
                            print(f"Error playing audio: {error}")
                            return
                        # Schedule the next song to play safely
                        coro = self.play_next(ctx)
                        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
                        try:
                            future.result(timeout=1.0)  # Short timeout to avoid hanging
                        except Exception as e:
                            print(f"Error scheduling next song: {e}")

                    voice_client.play(source, after=after_playing)
                    await ctx.send(f"🎶 **{song_name}**")
                except Exception as e:
                    print(f"Error playing song {song_name}: {e}")
                    # Try to play next song in queue
                    if ctx.guild.id in self.queues and self.queues[ctx.guild.id]:
                        await self.play_next(ctx)

    async def skip(self, ctx: commands.Context):
        """Skip the current song"""
        voice_client = discord.utils.get(self.voice_clients, guild=ctx.guild)
        if voice_client and voice_client.is_connected():
            voice_client.stop()
            await ctx.send("Đã bỏ qua bài hát hiện tại.")
        else:
            await ctx.send("Bot đang không ở trong kênh thoại nào cả.")

    async def shuffle(self, ctx: commands.Context):
        """Shuffle the playlist"""
        if ctx.guild.id in self.queues:
            random.shuffle(self.queues[ctx.guild.id])
            await ctx.send("Đã xáo trộn hàng đợi.")
        else:
            await ctx.send("Không có hàng đợi nào để xáo trộn.")

    async def queue(self, ctx: commands.Context):
        """Show the queue with pagination"""
        if ctx.guild.id in self.queues and self.queues[ctx.guild.id]:
            queue = self.queues[ctx.guild.id]

            # Create paginated view
            view = QueueView(queue)
            queue_text = view.get_queue_text()

            embed = discord.Embed(
                title="🎵 Current Queue", description=queue_text, color=0x00FF00
            )

            embed.set_footer(
                text=f"Page 1/{view.max_pages} • Total: {len(queue)} songs"
            )

            # Disable next button if only one page
            if view.max_pages <= 1:
                view.next_button.disabled = True

            await ctx.send(embed=embed, view=view)
        else:
            await ctx.send("Không có hàng đợi nào.")

    async def on_message(self, message: discord.Message):
        """Called when a message is sent"""
        if message.author == self.user:
            return
        await self.process_commands(message)

    def setup_commands(self):
        """Setup bot commands"""

        @self.command(
            name="play",
            help="Phát nhạc. Nếu có tên bài hát thì phát bài đó, nếu không thì phát lặp lại cả thư mục.",
        )
        async def play_command(ctx: commands.Context, *, song_name: str = None):
            await self.play(ctx, song_name=song_name)

        @self.command(name="stop", help="Dừng nhạc, xóa hàng đợi và ngắt kết nối.")
        async def stop_command(ctx: commands.Context):
            await self.stop(ctx)

        @self.command(name="skip", help="Bỏ qua bài hát hiện tại.")
        async def skip_command(ctx: commands.Context):
            await self.skip(ctx)

        @self.command(name="shuffle", help="Xáo trộn hàng đợi.")
        async def shuffle_command(ctx: commands.Context):
            await self.shuffle(ctx)

        @self.command(name="queue", help="Hiển thị hàng đợi.")
        async def queue_command(ctx: commands.Context):
            await self.queue(ctx)

        # Override help command
        @self.command(name="help", help="Hiển thị các lệnh của bot.")
        async def help_command(ctx: commands.Context):
            await self.show_help(ctx)

    async def on_command_error(self, ctx: commands.Context, error):
        """Handle command errors"""
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(
                f"❌ Command not found! Gõ `{COMMAND_PREFIX}help` để xem các commands có sẵn."
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"❌ Command missing required argument! Gõ `{COMMAND_PREFIX}help` để xem cách sử dụng."
            )
        else:
            await ctx.send(f"❌ Command error: {str(error)}")

    async def show_help(self, ctx: commands.Context):
        """Show help for the bot"""
        embed = discord.Embed(
            title=f"{BOT_NAME} Commands",
            description="--------------------------------",
            color=0x00FF00,
        )
        embed.add_field(
            name=f"{COMMAND_PREFIX}play [tên bài hát]",
            value="Phát nhạc. Nếu có tên bài hát thì phát bài đó, nếu không thì phát lặp lại cả thư mục.",
            inline=False,
        )
        embed.add_field(
            name=f"{COMMAND_PREFIX}stop",
            value="Dừng nhạc, xóa hàng đợi và ngắt kết nối.",
            inline=False,
        )
        embed.add_field(
            name=f"{COMMAND_PREFIX}skip", value="Bỏ qua bài hát hiện tại.", inline=False
        )
        embed.add_field(
            name=f"{COMMAND_PREFIX}shuffle", value="Xáo trộn hàng đợi.", inline=False
        )
        embed.add_field(
            name=f"{COMMAND_PREFIX}queue", value="Hiển thị hàng đợi.", inline=False
        )
        embed.add_field(
            name=f"{COMMAND_PREFIX}help",
            value="Hiển thị các lệnh của bot.",
            inline=False,
        )
        await ctx.send(embed=embed)

    def run_bot(self):
        """Start the bot with proper setup"""
        self.setup_commands()
        self.run(BOT_TOKEN)
