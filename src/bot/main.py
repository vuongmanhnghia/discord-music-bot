import asyncio
import random
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

from src.queue.queue_view import QueueView
from src.playlist_manage import check_playlist_exists, get_all_songs
from src.initialize.init_logger import init_logger
from src.tracking.tracking import (
    spotdl_add_to_sync_file,
    spotdl_download_from_tracking_async,
    spotdl_sync_from_tracking_async,
    spotdl_download_single_song_async,
    spotdl_save_async,
    fix_playlist_format,
)
from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    FileModifiedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
)

load_dotenv()

BOT_NAME = os.getenv("BOT_NAME")
BOT_TOKEN = os.getenv("BOT_TOKEN")
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")
logger = init_logger("lofi-music")
PLAYLIST_FOLDER = os.getenv("PLAYLIST_FOLDER")
MUSIC_FOLDER = os.getenv("MUSIC_FOLDER")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set")

intents = discord.Intents.default()  # Enable message content intent
intents.message_content = True


class MusicFolderHandler(FileSystemEventHandler):
    """Improved file system event handler for music folders"""

    def __init__(self, bot: "MusicBot"):
        super().__init__()
        self.bot = bot
        self.audio_extensions = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}

    def _is_audio_file(self, path: str) -> bool:
        """Check if the file is an audio file we care about"""
        return os.path.splitext(path.lower())[1] in self.audio_extensions

    def _should_process_event(self, event) -> bool:
        """Filter events to only process relevant audio file changes"""
        if event.is_directory:
            return False

        # Only process audio files
        if hasattr(event, "src_path") and not self._is_audio_file(event.src_path):
            return False

        # For move events, check dest_path too
        if hasattr(event, "dest_path") and not self._is_audio_file(event.dest_path):
            return False

        return True

    def on_created(self, event):
        """Handle file creation events"""
        if self._should_process_event(event):
            logger.debug(f"Audio file created: {event.src_path}")
            self._schedule_rescan(event.src_path)

    def on_deleted(self, event):
        """Handle file deletion events"""
        if self._should_process_event(event):
            logger.debug(f"Audio file deleted: {event.src_path}")
            self._schedule_rescan(event.src_path)

    def on_moved(self, event):
        """Handle file move/rename events"""
        if self._should_process_event(event):
            logger.debug(f"Audio file moved: {event.src_path} -> {event.dest_path}")
            self._schedule_rescan(event.dest_path)

    def on_modified(self, event):
        """Handle file modification events (less common for audio files)"""
        # Skip modified events for audio files as they're usually not relevant
        # and can cause excessive rescanning during downloads
        pass

    def _schedule_rescan(self, changed_path: str):
        """Schedule rescan via bot's thread-safe method"""
        try:
            self.bot.loop.call_soon_threadsafe(
                lambda: self.bot._schedule_rescan(changed_path)
            )
        except Exception as e:
            logger.warning(f"Failed to schedule rescan for {changed_path}: {e}")


class MusicBot(commands.Bot):
    def __init__(self, spotdl_instance=None):
        """Initialize the bot"""
        super().__init__(
            command_prefix=COMMAND_PREFIX,
            intents=intents,
            help_command=None,  # Disable default help command
        )
        self.queues = {}
        self._observer: Observer | None = None
        self._rescan_scheduled: bool = False
        self._rescan_task: asyncio.Task | None = None
        self._watched_paths: set[str] = set()
        self.spotdl = spotdl_instance
        self.active_playlists: dict[int, str] = {}  # guild_id -> playlist name
        self.spotdl_dir = os.getenv("SPOTDL_DIR", ".")  # where .spotdl files live

    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f"Đã đăng nhập với tên {self.user}")
        logger.info("Bot đã sẵn sàng hoạt động trên server!")
        logger.info("------------------------------------")

        # Start filesystem watcher
        await self._setup_file_watchers()

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

        # Determine subfolder based on active playlist
        active_playlist = self.active_playlists.get(ctx.guild.id)
        subfolder = active_playlist if active_playlist else None

        if self.active_playlists.get(ctx.guild.id) is None:
            await ctx.send(
                f"Hãy chọn playlist để phát! Dùng `{COMMAND_PREFIX}use <playlist_name>`"
            )
            return

        if song_name:  # Play specific song
            found, song_path = await check_playlist_exists(
                song_name, subfolder=subfolder
            )
            if not found:
                await ctx.send(
                    f"Không tìm thấy bài hát **{song_name}** trong playlist!"
                )
                return

            try:
                source = discord.FFmpegPCMAudio(song_path)
                voice_client.play(source)
                await ctx.send(f"🎶 Đang phát: **{song_name}**")
                logger.info(f"Play command: {song_name} -> {song_path}")
            except Exception as e:
                await ctx.send(f"❌ Lỗi khi phát nhạc: {str(e)}")
                logger.exception("Error while playing specific song")
                return

        else:  # Play all songs in playlist (active) or entire folder
            playlist = await get_all_songs(subfolder=subfolder)

            if not playlist:
                await ctx.send(f"Không có bài hát nào trong playlist!")
                return

            self.queues[ctx.guild.id] = playlist
            await ctx.send(
                f"▶ Bắt đầu phát **{len(playlist)}** bài hát trong "
                f"{'playlist ' + active_playlist if active_playlist else 'thư mục'}."
            )
            logger.info(f"Queue initialized with {len(playlist)} songs")

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
                            logger.error(f"Error playing audio: {error}")
                            return
                        # Schedule the next song to play safely
                        coro = self.play_next(ctx)
                        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
                        try:
                            future.result(timeout=1.0)  # Short timeout to avoid hanging
                        except Exception as e:
                            logger.error(f"Error scheduling next song: {e}")

                    voice_client.play(source, after=after_playing)
                    await ctx.send(f"🎶 **{song_name}**")
                    logger.info(f"Now playing: {song_name}")
                except Exception as e:
                    logger.exception(f"Error playing song {song_name}")
                    # Try to play next song in queue
                    if ctx.guild.id in self.queues and self.queues[ctx.guild.id]:
                        await self.play_next(ctx)

    # --- Folder watching & rescan logic ---
    async def _setup_file_watchers(self) -> None:
        """Setup file watchers for music folders with best practices"""
        try:
            if not MUSIC_FOLDER:
                logger.warning("MUSIC_FOLDER is not set; folder watcher disabled")
                return

            if not os.path.isdir(MUSIC_FOLDER):
                logger.warning(f"MUSIC_FOLDER path does not exist: {MUSIC_FOLDER}")
                return

            if self._observer is not None:
                await self._cleanup_watchers()

            self._observer = Observer()
            handler = MusicFolderHandler(self)

            # Watch root music folder recursively to catch all playlist subfolders
            self._observer.schedule(handler, path=MUSIC_FOLDER, recursive=True)
            self._watched_paths.add(MUSIC_FOLDER)

            self._observer.start()
            logger.info(f"Started recursive file watcher for: {MUSIC_FOLDER}")

        except Exception as e:
            logger.exception(f"Failed to setup file watchers: {e}")

    async def _cleanup_watchers(self) -> None:
        """Cleanup existing watchers safely"""
        if self._observer is not None:
            try:
                self._observer.stop()
                # Use asyncio to avoid blocking
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self._observer.join(timeout=3.0)
                )
            except Exception as e:
                logger.warning(f"Error stopping observer: {e}")
            finally:
                self._observer = None
                self._watched_paths.clear()

    def _schedule_rescan(self, changed_path: str = None) -> None:
        """Schedule a rescan with improved debouncing"""
        if self._rescan_scheduled:
            return

        self._rescan_scheduled = True

        # Cancel existing rescan task if any
        if self._rescan_task and not self._rescan_task.done():
            self._rescan_task.cancel()

        # Schedule new rescan task
        self._rescan_task = asyncio.create_task(
            self._rescan_playlist_after_delay(changed_path)
        )

    async def _rescan_playlist_after_delay(self, changed_path: str = None) -> None:
        """Rescan with improved delay and error handling"""
        try:
            # Longer debounce for batch operations
            await asyncio.sleep(1.0)
            await self._rescan_playlist(changed_path)
        except asyncio.CancelledError:
            logger.debug("Rescan cancelled (newer rescan scheduled)")
        except Exception as e:
            logger.exception(f"Error during delayed rescan: {e}")
        finally:
            self._rescan_scheduled = False

    async def _rescan_playlist(self, changed_path: str = None) -> None:
        """Rescan playlists with optimized updates"""
        try:
            if not MUSIC_FOLDER:
                return

            # Determine which playlists need updating based on changed path
            affected_playlists = set()

            if changed_path:
                # Extract playlist name from path if it's in a subfolder
                rel_path = os.path.relpath(changed_path, MUSIC_FOLDER)
                path_parts = rel_path.split(os.sep)
                if len(path_parts) > 1:
                    playlist_name = path_parts[0]
                    affected_playlists.add(playlist_name)
                else:
                    # Change in root folder affects all guilds without specific playlist
                    affected_playlists.add(None)

            # Update queues for affected guilds only
            updated_guilds = 0
            for guild_id in list(self.queues.keys()):
                subfolder = self.active_playlists.get(guild_id)

                # Skip if this guild's playlist wasn't affected
                if (
                    changed_path
                    and affected_playlists
                    and subfolder not in affected_playlists
                ):
                    continue

                try:
                    playlist = await get_all_songs(subfolder=subfolder)
                    self.queues[guild_id] = playlist.copy()
                    updated_guilds += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to rescan playlist for guild {guild_id}: {e}"
                    )

            logger.info(
                f"Rescanned music folder(s). Updated {updated_guilds} guild queues."
                + (f" (affected: {changed_path})" if changed_path else "")
            )

        except Exception as e:
            logger.exception(f"Error while rescanning music folder: {e}")

    async def close(self):
        """Cleanup resources when bot shuts down"""
        try:
            # Cancel any pending rescan task
            if self._rescan_task and not self._rescan_task.done():
                self._rescan_task.cancel()
                try:
                    await self._rescan_task
                except asyncio.CancelledError:
                    pass

            # Cleanup file watchers
            await self._cleanup_watchers()

        except Exception as e:
            logger.exception(f"Error during bot cleanup: {e}")
        finally:
            await super().close()

    async def skip(self, ctx: commands.Context):
        """Skip the current song"""
        # await ctx.send("Skip...!")
        voice_client = discord.utils.get(self.voice_clients, guild=ctx.guild)
        if voice_client and voice_client.is_connected():
            voice_client.stop()
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
                title="Current Queue", description=queue_text, color=0x00FF00
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

    async def save_playlist(self, ctx: commands.Context, *, args: str):
        """Save Spotify URLs into a .spotdl file"""
        parts = args.split()
        if not parts:
            await ctx.send("Dùng: !save <save_file> <spotify_url...>")
            return

        save_file, *urls = parts
        if not urls:
            await ctx.send(
                "Bạn cần cung cấp ít nhất 1 Spotify URL. Ví dụ: !save test_playlist https://open.spotify.com/playlist/..."
            )
            return

        try:
            await ctx.send(f"Đang lưu {len(urls)} URL vào {save_file}.spotdl ...")
            await spotdl_save_async(save_file, *urls)
            await ctx.send(f"Đã lưu {len(urls)} URL vào {save_file}.spotdl")
        except Exception as e:
            await ctx.send(f"❌ Lỗi khi save: {str(e)}")

    async def download_playlist(self, ctx: commands.Context, *, playlist_name: str):
        """Download the playlist"""
        await self.download_playlist(ctx, playlist_name=playlist_name)

    async def sync_playlist(self, ctx: commands.Context, *, playlist_name: str):
        """Sync the playlist"""
        try:
            if not playlist_name.endswith(".spotdl"):
                playlist_file = f"{playlist_name}.spotdl"
            else:
                playlist_file = playlist_name

            save_file_path = os.path.join(self.spotdl_dir, playlist_file)
            if not os.path.exists(save_file_path):
                await ctx.send(f"❌ Không tìm thấy file {save_file_path}")
                return

            pl_name_no_ext = os.path.splitext(playlist_file)[0]
            output_dir_root = MUSIC_FOLDER
            output_dir = os.path.join(output_dir_root, pl_name_no_ext)
            os.makedirs(output_dir, exist_ok=True)

            await ctx.send(
                f"**Đang đồng bộ playlist từ playlist `{playlist_name}`...**"
            )
            await spotdl_sync_from_tracking_async(save_file_path, output_dir)
            await ctx.send(f"**Đã đồng bộ thành công playlist `{playlist_name}`!**")
            logger.info(f"Synced playlist: {playlist_name} -> {output_dir}")

        except Exception as e:
            await ctx.send(f"❌ Lỗi khi đồng bộ playlist: `{str(e)}`")
            logger.exception(f"Error syncing playlist {playlist_name}")

    async def add_song(self, ctx: commands.Context, *, spotify_url: str):
        """Add a song from Spotify URL to the playlist"""
        try:
            # Use active playlist or default to main_playlist
            playlist_name = self.active_playlists.get(ctx.guild.id, "main_playlist")
            playlist_file = f"{playlist_name}.spotdl"
            output_dir_root = MUSIC_FOLDER
            output_dir = os.path.join(output_dir_root, playlist_name)
            os.makedirs(output_dir, exist_ok=True)

            await ctx.send(f"**Đang tải bài hát từ Spotify...**")

            # Add to sync file
            save_file_path = os.path.join(self.spotdl_dir, playlist_file)
            added = spotdl_add_to_sync_file(save_file_path, spotify_url, output_dir)

            if added:
                await ctx.send(f"**Đã thêm bài hát vào playlist `{playlist_name}`**")

                # Try to download the song immediately (single song - faster)
                try:
                    await ctx.send(f"**⬇ Đang tải bài hát...**")
                    await spotdl_download_single_song_async(spotify_url, output_dir)
                    await ctx.send(f"**Đã tải và thêm bài hát thành công!**")
                    logger.info(f"Downloaded song from URL: {spotify_url}")
                except Exception as download_error:
                    await ctx.send(
                        f"Đã thêm vào playlist {playlist_name}, nhưng tải thất bại. Hãy dùng `!sync {playlist_name}` để tải lại."
                    )
                    logger.warning(f"Failed to download immediately: {download_error}")
            else:
                await ctx.send(f"Bài hát đã tồn tại trong playlist {playlist_name}!")

        except Exception as e:
            await ctx.send(f"❌ Lỗi khi thêm bài hát: {str(e)}")
            logger.exception(f"Error adding song from URL: {spotify_url}")

    async def fix_playlist_format_cmd(
        self, ctx: commands.Context, *, playlist_name: str
    ):
        """Fix playlist format from array to sync format"""
        try:
            if not playlist_name.endswith(".spotdl"):
                playlist_name = f"{playlist_name}.spotdl"

            save_file_path = os.path.join(self.spotdl_dir, playlist_name)
            if not os.path.exists(save_file_path):
                await ctx.send(f"❌ Không tìm thấy file {save_file_path}")
                return

            await ctx.send(f"🔧 Đang sửa format file {playlist_name}...")

            success = fix_playlist_format(save_file_path)
            if success:
                await ctx.send(f"✅ Đã sửa format thành công cho {playlist_name}!")
                logger.info(f"Fixed format for playlist: {playlist_name}")
            else:
                await ctx.send(f"❌ Không thể sửa format cho {playlist_name}")

        except Exception as e:
            await ctx.send(f"❌ Lỗi khi sửa format: {str(e)}")
            logger.exception(f"Error fixing format for {playlist_name}")

    def setup_commands(self):
        """Setup bot commands"""

        @self.command(
            name="play",
            help="Phát nhạc. Nếu có tên bài hát thì phát bài đó, nếu không thì phát lặp lại cả thư mục.",
        )
        async def play_command(ctx: commands.Context, *, song_name: str = None):
            await self.play(ctx, song_name=song_name)

        @self.command(name="playlists", help="Liệt kê danh sách file .spotdl có sẵn.")
        async def playlists_command(ctx: commands.Context):
            files = [f for f in os.listdir(self.spotdl_dir) if f.endswith(".spotdl")]
            if not files:
                await ctx.send("Không tìm thấy playlist (.spotdl) nào.")
                return
            names = [os.path.splitext(f)[0] for f in files]
            current = self.active_playlists.get(ctx.guild.id)
            listing = "\n".join(
                f"- {n}{' <current>' if n == current else ''}" for n in sorted(names)
            )
            await ctx.send(f"Danh sách playlists:\n{listing}")

        @self.command(
            name="use", help="Chọn playlist để phát/đồng bộ. Ví dụ: !use main_playlist"
        )
        async def use_command(ctx: commands.Context, *, playlist_name: str):
            # Set active playlist for this guild
            self.active_playlists[ctx.guild.id] = playlist_name
            # Ensure subfolder exists
            output_dir_root = MUSIC_FOLDER
            os.makedirs(os.path.join(output_dir_root, playlist_name), exist_ok=True)
            await ctx.send(f"Đã chọn playlist: {playlist_name}")

        @self.command(name="current", help="Hiển thị playlist đang được chọn.")
        async def current_command(ctx: commands.Context):
            current = self.active_playlists.get(ctx.guild.id)
            if not current:
                await ctx.send(
                    "**Chưa chọn playlist nào. Dùng `!use <playlist_name>`**."
                )
                return
            await ctx.send(f"**Playlist hiện tại: `{current}`**")

        @self.command(
            name="addto",
            help="Thêm bài hát vào playlist cụ thể. Ví dụ: !addto main_playlist <spotify_url>",
        )
        async def addto_command(ctx: commands.Context, *, args: str):
            try:
                parts = args.split()
                if len(parts) < 2:
                    await ctx.send("**Dùng: !addto <playlist_name> <spotify_url>**")
                    return
                playlist_name, spotify_url = parts[0], parts[1]
                output_dir_root = MUSIC_FOLDER
                output_dir = os.path.join(output_dir_root, playlist_name)
                os.makedirs(output_dir, exist_ok=True)

                save_file = f"{playlist_name}.spotdl"
                save_file_path = os.path.join(self.spotdl_dir, save_file)

                # Add to sync file (creates if not exists)
                added = spotdl_add_to_sync_file(save_file_path, spotify_url, output_dir)
                if added:
                    await ctx.send(f"**Đã thêm vào `{playlist_name}`**")
                    # Try immediate download of single song into this playlist folder
                    try:
                        await ctx.send("**⬇ Đang tải bài hát...**")
                        await spotdl_download_single_song_async(spotify_url, output_dir)
                        await ctx.send("**Đã tải và thêm bài hát thành công!**")
                        logger.info(
                            f"Downloaded song to {output_dir} from URL: {spotify_url}"
                        )
                    except Exception as download_error:
                        await ctx.send(
                            f"Đã thêm vào playlist_name, nhưng tải thất bại. Hãy dùng `!sync {playlist_name}` để tải lại."
                        )
                        logger.warning(
                            f"Failed to download immediately: {download_error}"
                        )
                else:
                    await ctx.send(
                        f"Bài hát đã tồn tại trong playlist {playlist_name}."
                    )

            except Exception as e:
                await ctx.send(f"❌ Lỗi khi thêm bài hát: {str(e)}")
                logger.exception("Error in addto command")

        @self.command(name="stop", help="Dừng nhạc, xóa hàng đợi và ngắt kết nối.")
        async def stop_command(ctx: commands.Context):
            await self.stop(ctx)

        @self.command(
            name="save",
            help="Lưu URL vào file .spotdl. Dùng: !save <file> <url1> [url2 ...]",
        )
        async def save_command(ctx: commands.Context, *, args: str):
            await self.save_playlist(ctx, args=args)

        @self.command(name="download", help="Tải playlist.")
        async def download_command(ctx: commands.Context, *, playlist_name: str):
            await self.download_playlist(ctx, playlist_name=playlist_name)

        @self.command(name="sync", help="Đồng bộ playlist.")
        async def sync_command(ctx: commands.Context, *, playlist_name: str):
            await self.sync_playlist(ctx, playlist_name=playlist_name)

        @self.command(name="add", help="Thêm bài hát từ Spotify link.")
        async def add_command(ctx: commands.Context, *, spotify_url: str):
            await self.add_song(ctx, spotify_url=spotify_url)

        @self.command(name="skip", help="Bỏ qua bài hát hiện tại.")
        async def skip_command(ctx: commands.Context):
            await self.skip(ctx)

        @self.command(name="shuffle", help="Xáo trộn hàng đợi.")
        async def shuffle_command(ctx: commands.Context):
            await self.shuffle(ctx)

        @self.command(name="queue", help="Hiển thị hàng đợi.")
        async def queue_command(ctx: commands.Context):
            await self.queue(ctx)

        @self.command(name="fix", help="Sửa format file .spotdl từ array sang sync.")
        async def fix_command(ctx: commands.Context, *, playlist_name: str):
            await self.fix_playlist_format_cmd(ctx, playlist_name=playlist_name)

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
            name=f"{COMMAND_PREFIX}save [tên playlist]",
            value="Lưu playlist.",
            inline=False,
        )
        embed.add_field(
            name=f"{COMMAND_PREFIX}download [tên playlist]",
            value="Tải playlist.",
            inline=False,
        )
        embed.add_field(
            name=f"{COMMAND_PREFIX}sync [tên playlist]",
            value="Đồng bộ playlist.",
            inline=False,
        )
        embed.add_field(
            name=f"{COMMAND_PREFIX}playlists",
            value="Liệt kê các file .spotdl có sẵn.",
            inline=False,
        )
        embed.add_field(
            name=f"{COMMAND_PREFIX}use [tên playlist]",
            value="Chọn playlist đang hoạt động (phát/đồng bộ/thêm).",
            inline=False,
        )
        embed.add_field(
            name=f"{COMMAND_PREFIX}current",
            value="Hiển thị playlist đang hoạt động.",
            inline=False,
        )
        embed.add_field(
            name=f"{COMMAND_PREFIX}addto [tên playlist] [Spotify link]",
            value="Thêm bài hát vào playlist chỉ định và tải về thư mục tương ứng.",
            inline=False,
        )
        embed.add_field(
            name=f"{COMMAND_PREFIX}add [Spotify link]",
            value="Thêm bài hát từ Spotify link vào playlist.",
            inline=False,
        )
        embed.add_field(
            name=f"{COMMAND_PREFIX}fix [tên playlist]",
            value="Sửa format file .spotdl từ array sang sync format.",
            inline=False,
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
