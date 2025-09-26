"""Clean Discord bot implementation"""

import asyncio
from pathlib import Path
import random
from typing import Dict, Optional

import discord
from discord.ext import commands

from .config import config
from .logger import logger
from .models import GuildState
from .playlist import playlist_manager
from .spotdl_client import spotdl
from .watcher import watcher


class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix=config.COMMAND_PREFIX, intents=intents, help_command=None
        )

        self.guilds_state: Dict[int, GuildState] = {}

        # Register commands
        self._register_commands()

    def get_guild_state(self, guild_id: int) -> GuildState:
        """Get or create guild state"""
        if guild_id not in self.guilds_state:
            self.guilds_state[guild_id] = GuildState(guild_id)
        return self.guilds_state[guild_id]

    async def on_ready(self):
        """Bot ready event"""
        logger.info(f"🎵 {config.BOT_NAME} ready! Logged in as {self.user}")
        logger.info(f"🔑 Command prefix: {config.COMMAND_PREFIX}")
        logger.info(f"🎯 Bot ID: {self.user.id}")

        # List available commands
        commands_list = [cmd.name for cmd in self.commands]
        logger.info(f"📋 Available commands: {', '.join(commands_list)}")

        # Start file watcher
        watcher.start(self._on_music_change)

    async def on_message(self, message):
        """Handle incoming messages"""
        # Don't respond to bot messages
        if message.author.bot:
            return

        # Log messages that start with our prefix for debugging
        if message.content.startswith(config.COMMAND_PREFIX):
            logger.info(f"📨 [COMMAND]: {message.content} from {message.author}")

        # Process commands
        await self.process_commands(message)

    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        logger.error(f"❌ Command error in {ctx.command}: {error}")

        if isinstance(error, commands.CommandNotFound):
            await ctx.send(
                f"**❌ Không tìm thấy lệnh! Sử dụng `{config.COMMAND_PREFIX}help` để xem danh sách lệnh có sẵn.**"
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"**❌ Thiếu tham số bắt buộc! Sử dụng `{config.COMMAND_PREFIX}help` để biết cách sử dụng.**"
            )
        elif isinstance(error, commands.BadArgument):
            await ctx.send(
                f"**❌ Tham số không hợp lệ! Sử dụng `{config.COMMAND_PREFIX}help` để biết cách sử dụng.**"
            )
        else:
            await ctx.send(f"**❌ Đã xảy ra lỗi: {str(error)}**")

    def _on_music_change(self, changed_path: str):
        """Handle music file changes"""
        logger.debug(f"Music file changed: {changed_path}")

        # Update affected guild queues
        for guild_state in self.guilds_state.values():
            if guild_state.queue:
                # Refresh queue for this guild's active playlist
                new_songs = playlist_manager.get_songs(guild_state.active_playlist)
                guild_state.queue = new_songs

    async def close(self):
        """Clean shutdown"""
        await watcher.stop()
        await super().close()
        logger.info("Bot shutdown complete")

    def _register_commands(self):
        """Register all bot commands"""

        @self.command(name="playlists", help="List available playlists")
        async def list_playlists(ctx):
            await self.list_playlists_impl(ctx)

        @self.command(name="use", help="Select active playlist")
        async def use_playlist(ctx, *, playlist_name: str):
            await self.use_playlist_impl(ctx, playlist_name=playlist_name)

        @self.command(name="current", help="Show current playlist")
        async def current_playlist(ctx):
            await self.current_playlist_impl(ctx)

        @self.command(name="sync", help="Sync playlist")
        async def sync_playlist(ctx, *, playlist_name: str):
            await self.sync_playlist_impl(ctx, playlist_name=playlist_name)

        @self.command(name="add", help="Add song to current playlist")
        async def add_song(ctx, *, spotify_url: str):
            await self.add_song_impl(ctx, spotify_url=spotify_url)

        @self.command(name="addto", help="Add song to specific playlist")
        async def add_to_playlist(ctx, playlist_name: str, *, spotify_url: str):
            await self.add_to_playlist_impl(ctx, playlist_name, spotify_url=spotify_url)

        @self.command(name="create", help="Create new playlist")
        async def create_playlist(ctx, *, playlist_name: str):
            await self.create_playlist_impl(ctx, playlist_name=playlist_name)

        @self.command(name="fix", help="Fix playlist format")
        async def fix_playlist(ctx, *, playlist_name: str):
            await self.fix_playlist_impl(ctx, playlist_name=playlist_name)

        @self.command(name="play", help="Play music")
        async def play_music(ctx, *, song_name: str = None):
            await self.play_music_impl(ctx, song_name=song_name)

        @self.command(name="stop", help="Stop music and disconnect")
        async def stop_music(ctx):
            await self.stop_music_impl(ctx)

        @self.command(name="skip", help="Skip current song")
        async def skip_song(ctx):
            await self.skip_song_impl(ctx)

        @self.command(name="shuffle", help="Shuffle queue")
        async def shuffle_queue(ctx):
            await self.shuffle_queue_impl(ctx)

        @self.command(name="help", help="Show commands")
        async def show_help(ctx):
            await self.show_help_impl(ctx)

    # === Command Implementations ===

    async def list_playlists_impl(self, ctx):
        """List all playlists"""
        playlists = playlist_manager.get_playlists()

        if not playlists:
            await ctx.send("**No playlists found**")
            return

        state = self.get_guild_state(ctx.guild.id)
        lines = []

        for playlist in playlists:
            indicator = "✅" if playlist.name == state.active_playlist else "📁"
            lines.append(
                f"{indicator} **{playlist.name}** ({playlist.song_count} songs)"
            )

        embed = discord.Embed(
            title="🎵 Available Playlists",
            description="\\n".join(lines),
            color=0x00FF00,
        )
        await ctx.send(embed=embed)

    async def use_playlist_impl(self, ctx, *, playlist_name: str):
        """Set active playlist"""
        playlist = playlist_manager.get_playlist(playlist_name)

        if not playlist:
            await ctx.send(f"**❌ Playlist `{playlist_name}` not found**")
            return

        state = self.get_guild_state(ctx.guild.id)
        state.active_playlist = playlist_name

        # Ensure music directory exists
        playlist.music_dir.mkdir(parents=True, exist_ok=True)

        await ctx.send(f"**✅ Active playlist: `{playlist_name}`**")

    async def current_playlist_impl(self, ctx):
        """Show current active playlist"""
        state = self.get_guild_state(ctx.guild.id)

        if not state.active_playlist:
            await ctx.send("**No playlist selected. Use `!use <name>`**")
            return

        playlist = playlist_manager.get_playlist(state.active_playlist)
        if playlist:
            await ctx.send(
                f"**🎯 Current: `{playlist.name}` ({playlist.song_count} songs)**"
            )
        else:
            await ctx.send(f"**Current playlist `{state.active_playlist}` not found**")

    async def sync_playlist_impl(self, ctx, *, playlist_name: str):
        """Sync playlist from Spotify"""
        playlist = playlist_manager.get_playlist(playlist_name)

        if not playlist or not playlist.exists:
            await ctx.send(f"**❌ Playlist `{playlist_name}` not found**")
            return

        await ctx.send(f"**🔄 Syncing `{playlist_name}`...**")

        success = await spotdl.sync_playlist(playlist_name)

        if success:
            await ctx.send(f"**✅ Synced `{playlist_name}` successfully!**")
        else:
            await ctx.send(f"**❌ Failed to sync `{playlist_name}`**")

    async def add_song_impl(self, ctx, *, spotify_url: str):
        """Add song to active playlist"""
        state = self.get_guild_state(ctx.guild.id)

        if not state.active_playlist:
            await ctx.send("**❌ No playlist selected. Use `!use <name>` first**")
            return

        playlist = playlist_manager.get_playlist(state.active_playlist)
        if not playlist:
            await ctx.send(f"**❌ Playlist `{state.active_playlist}` not found**")
            return

        await ctx.send("**📝 Adding song to playlist...**")

        # Add to playlist file
        added = spotdl.add_to_playlist(state.active_playlist, spotify_url)

        if not added:
            await ctx.send("**ℹ️ Song already exists in playlist**")
            return

        await ctx.send(f"**✅ Added to `{state.active_playlist}`**")

        # Try immediate download
        await ctx.send("**⬇️ Downloading...**")
        success = await spotdl.download_song(spotify_url, playlist.music_dir)

        if success:
            await ctx.send("**🎵 Downloaded successfully!**")
        else:
            await ctx.send(
                f"**⚠️ Added to playlist. Use `!sync {state.active_playlist}` to download**"
            )

    async def add_to_playlist_impl(self, ctx, playlist_name: str, *, spotify_url: str):
        """Add song to specific playlist"""
        playlist = playlist_manager.get_playlist(playlist_name)

        if not playlist:
            await ctx.send(f"**❌ Playlist `{playlist_name}` not found**")
            return

        await ctx.send(f"**📝 Adding song to `{playlist_name}`...**")

        # Add to playlist file
        added = spotdl.add_to_playlist(playlist_name, spotify_url)

        if not added:
            await ctx.send("**ℹ️ Song already exists in playlist**")
            return

        await ctx.send(f"**✅ Added to `{playlist_name}`**")

        # Try immediate download
        await ctx.send("**⬇️ Downloading...**")
        success = await spotdl.download_song(spotify_url, playlist.music_dir)

        if success:
            await ctx.send("**🎵 Downloaded successfully!**")
        else:
            await ctx.send(
                f"**⚠️ Added to playlist. Use `!sync {playlist_name}` to download**"
            )

    async def create_playlist_impl(self, ctx, *, playlist_name: str):
        """Create new playlist"""
        if not playlist_name or not playlist_name.strip():
            await ctx.send("**❌ Please provide a valid playlist name**")
            return

        # Clean the name for display
        clean_name = "".join(c for c in playlist_name if c.isalnum() or c in "._- ").strip()
        
        if not clean_name:
            await ctx.send("**❌ Playlist name contains only invalid characters**")
            return

        # Check if playlist already exists
        existing_playlist = playlist_manager.get_playlist(clean_name)
        if existing_playlist and existing_playlist.exists:
            await ctx.send(f"**❌ Playlist `{clean_name}` already exists**")
            return

        await ctx.send(f"**📝 Creating playlist `{clean_name}`...**")

        # Create the playlist
        success = playlist_manager.create_playlist(clean_name)

        if success:
            await ctx.send(f"**✅ Created playlist `{clean_name}` successfully!**")
            await ctx.send(f"**💡 Use `{config.COMMAND_PREFIX}use {clean_name}` to select it**")
        else:
            await ctx.send(f"**❌ Playlist creation failed**")

    async def fix_playlist_impl(self, ctx, *, playlist_name: str):
        """Fix playlist file format"""
        success = playlist_manager.ensure_sync_format(playlist_name)

        if success:
            await ctx.send(f"**✅ Fixed format for `{playlist_name}`**")
        else:
            await ctx.send(f"**❌ Playlist format fix failed**")

    async def play_music_impl(self, ctx, *, song_name: str = None):
        """Play music"""
        if not ctx.author.voice:
            await ctx.send("**❌ Join a voice channel first!**")
            return

        voice_channel = ctx.author.voice.channel
        voice_client = discord.utils.get(self.voice_clients, guild=ctx.guild)

        if not voice_client:
            voice_client = await voice_channel.connect()
        elif voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)

        state = self.get_guild_state(ctx.guild.id)

        if song_name:
            # Play specific song
            song_path = playlist_manager.find_song(song_name, state.active_playlist)
            if not song_path:
                await ctx.send(f"**❌ Song `{song_name}` not found**")
                return

            if voice_client.is_playing():
                voice_client.stop()

            source = discord.FFmpegPCMAudio(song_path)
            voice_client.play(source)
            await ctx.send(f"**🎶 Playing: {song_name}**")
        else:
            # Play playlist
            songs = playlist_manager.get_songs(state.active_playlist)
            if not songs:
                await ctx.send("**❌ No songs available**")
                return

            state.queue = songs
            await ctx.send(f"**▶️ Playing {len(songs)} songs**")
            await self._play_next(ctx)

    async def _play_next(self, ctx):
        """Play next song in queue"""
        state = self.get_guild_state(ctx.guild.id)

        if not state.queue:
            return

        voice_client = discord.utils.get(self.voice_clients, guild=ctx.guild)
        if not voice_client or not voice_client.is_connected():
            return

        song_path = state.queue.pop(0)
        state.queue.append(song_path)  # Loop

        song_name = Path(song_path).stem

        try:
            source = discord.FFmpegPCMAudio(song_path)

            def after_playing(error):
                if error:
                    logger.error(f"Playback error: {error}")
                    return

                # Schedule next song
                coro = self._play_next(ctx)
                future = asyncio.run_coroutine_threadsafe(coro, self.loop)
                try:
                    future.result(timeout=1.0)
                except Exception as e:
                    logger.error(f"Error scheduling next song: {e}")

            voice_client.play(source, after=after_playing)
            await ctx.send(f"**🎵 {song_name}**")

        except Exception as e:
            logger.error(f"Error playing {song_name}: {e}")
            await self._play_next(ctx)  # Try next song

    async def stop_music_impl(self, ctx):
        """Stop music"""
        state = self.get_guild_state(ctx.guild.id)
        state.queue.clear()

        voice_client = discord.utils.get(self.voice_clients, guild=ctx.guild)
        if voice_client:
            voice_client.stop()
            await voice_client.disconnect()
            await ctx.send("**⏹️ Stopped and disconnected**")
        else:
            await ctx.send("**❌ Not connected to voice**")

    async def skip_song_impl(self, ctx):
        """Skip current song"""
        voice_client = discord.utils.get(self.voice_clients, guild=ctx.guild)
        if voice_client and voice_client.is_playing():
            voice_client.stop()
        else:
            await ctx.send("**❌ Nothing playing**")

    async def shuffle_queue_impl(self, ctx):
        """Shuffle current queue"""
        state = self.get_guild_state(ctx.guild.id)
        if state.queue:
            random.shuffle(state.queue)
            await ctx.send("**🔀 Queue shuffled**")
        else:
            await ctx.send("**❌ No queue to shuffle**")

    async def show_help_impl(self, ctx):
        """Show help"""
        embed = discord.Embed(title=f"🎵 {config.BOT_NAME} Commands", color=0x00FF00)

        commands_list = [
            ("playlists", "List available playlists"),
            ("use <name>", "Select active playlist"),
            ("current", "Show current playlist"),
            ("create <name>", "Create new playlist"),
            ("sync <name>", "Sync playlist from Spotify"),
            ("add <url>", "Add song to current playlist"),
            ("addto <name> <url>", "Add song to specific playlist"),
            ("fix <name>", "Fix playlist format"),
            ("play [song]", "Play music (song or playlist)"),
            ("stop", "Stop and disconnect"),
            ("skip", "Skip current song"),
            ("shuffle", "Shuffle queue"),
        ]

        for cmd, desc in commands_list:
            embed.add_field(
                name=f"{config.COMMAND_PREFIX}{cmd}", value=desc, inline=False
            )

        await ctx.send(embed=embed)
