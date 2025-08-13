import discord
import wavelink
import asyncio
from discord.ext import commands, tasks
import config
from utils.logger import logger
from utils.player import MusicPlayer

class MusicCog(commands.Cog):
    """Music commands and functionality cog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.player = MusicPlayer()
        self.keep_alive_task.start()
    
    def cog_unload(self):
        """Called when the cog is unloaded"""
        self.keep_alive_task.cancel()
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Bot ready event"""
        logger.info(f'{self.bot.user} is ready!')
        
        # Wait for Lavalink to be ready
        await asyncio.sleep(5)
        await self.player.setup_lavalink(self.bot)
        
        # Auto-connect to voice channel if configured
        if config.DEFAULT_VOICE_CHANNEL_ID:
            await asyncio.sleep(2)  # Wait a bit more for full initialization
            await self.auto_connect()
    
    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """Handle track end event"""
        try:
            # Only handle "finished" or "stopped" reasons
            if payload.reason in ["finished", "stopped"]:
                logger.info(f"Track ended with reason: {payload.reason}")
                
                # Check if we have tracks in playlist
                if not self.player.playlist_tracks:
                    logger.info("No tracks in playlist, nothing to play next")
                    return
                    
                # Wait a moment before playing next track
                await asyncio.sleep(0.2)
                
                # Play next track
                await self.player.play_next_track(payload.player)
                
        except Exception as e:
            logger.error(f"Error in track end event: {e}")
            if self.player.current_channel:
                await self.player.current_channel.send(f"❌ Lỗi khi chuyển bài: {str(e)[:100]}")
    
    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        """Handle node ready event"""
        logger.info(f"Wavelink Node connected: {payload.node!r}")
    
    async def auto_connect(self):
        """Auto-connect to voice channel"""
        try:
            voice_channel = self.bot.get_channel(config.DEFAULT_VOICE_CHANNEL_ID)
            text_channel = self.bot.get_channel(config.DEFAULT_TEXT_CHANNEL_ID)
            
            if voice_channel:
                player = await voice_channel.connect(cls=wavelink.Player)
                self.player.current_voice_channel = voice_channel
                self.player.current_channel = text_channel
                await player.set_volume(config.VOLUME_DEFAULT)
                logger.info(f"Connected to {voice_channel.name}")
                
                if text_channel:
                    await text_channel.send(f"🎵 Bot đã kết nối đến {voice_channel.name}")
                
                # Load default playlist if configured
                if config.DEFAULT_PLAYLIST_URL:
                    await self.player.load_playlist(config.DEFAULT_PLAYLIST_URL, player)
                    
        except Exception as e:
            logger.error(f"Auto-connect failed: {e}")
    
    @tasks.loop(minutes=5)
    async def keep_alive_task(self):
        """Keep bot alive and reconnect if needed"""
        try:
            if config.AUTO_RECONNECT and self.player.current_voice_channel:
                voice_client = discord.utils.get(self.bot.voice_clients, channel=self.player.current_voice_channel)
                
                if not voice_client or not voice_client.is_connected():
                    logger.info("Attempting to reconnect...")
                    await self.auto_connect()
                    
        except Exception as e:
            logger.error(f"Keep alive task error: {e}")
    
    @commands.command(name='join')
    async def join(self, ctx, *, channel: discord.VoiceChannel = None):
        """Join a voice channel"""
        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                return await ctx.send("❌ Bạn cần ở trong voice channel hoặc chỉ định channel!")
        
        try:
            player = await channel.connect(cls=wavelink.Player)
            self.player.current_voice_channel = channel
            self.player.current_channel = ctx.channel
            await player.set_volume(config.VOLUME_DEFAULT)
            await ctx.send(f"🎵 Đã kết nối đến {channel.name}")
            
        except Exception as e:
            await ctx.send(f"❌ Không thể kết nối: {e}")
    
    @commands.command(name='leave')
    async def leave(self, ctx):
        """Leave voice channel"""
        voice_client = ctx.voice_client
        if voice_client:
            await voice_client.disconnect()
            self.player.current_voice_channel = None
            self.player.is_playing = False
            await ctx.send("👋 Đã rời khỏi voice channel")
        else:
            await ctx.send("❌ Bot không ở trong voice channel nào")
    
    @commands.command(name='play')
    async def play(self, ctx, *, search: str = None):
        """Play music from search or URL"""
        if not search:
            return await ctx.send("❌ Vui lòng cung cấp tên bài hát hoặc URL!\nVí dụ: `!play despacito` hoặc `!play https://youtu.be/...`")
            
        if not ctx.voice_client:
            await self.join(ctx)
        
        player = ctx.voice_client
        
        try:
            # Check if it's a playlist URL
            if any(keyword in search.lower() for keyword in ['playlist', 'list=']):
                return await self.load_playlist_command(ctx, search)
            
            # Try different search prefixes
            search_queries = [
                search,
                f"ytsearch:{search}",
                f"scsearch:{search}"
            ]
            
            tracks = None
            for query in search_queries:
                try:
                    tracks = await wavelink.Playable.search(query)
                    if tracks:
                        break
                except Exception as e:
                    logger.error(f"Search failed for '{query}': {e}")
                    continue
            
            if not tracks:
                return await ctx.send("❌ Không tìm thấy bài hát nào! Thử với từ khóa khác hoặc URL trực tiếp.")
            
            # Handle different return types
            if hasattr(tracks, 'tracks'):  # It's a playlist object
                await self.player.load_playlist(search, player)
                return
            elif isinstance(tracks, list):  # It's a list of tracks
                track = tracks[0]
            else:  # It's a single track
                track = tracks
            
            await self.player.play_track(player, track)
            
        except Exception as e:
            logger.error(f"Play command error: {e}")
            await ctx.send(f"❌ Lỗi khi phát nhạc: {str(e)[:100]}")
    
    @commands.command(name='playlist')
    async def load_playlist_command(self, ctx, url: str = None):
        """Load a playlist from URL"""
        if not url:
            return await ctx.send("❌ Vui lòng cung cấp URL playlist!\nVí dụ: `!playlist https://youtube.com/playlist?list=...`")
            
        if not ctx.voice_client:
            await self.join(ctx)
            
        player = ctx.voice_client
        await self.player.load_playlist(url, player)
    
    @commands.command(name='skip')
    async def skip(self, ctx):
        """Skip current track"""
        player = ctx.voice_client
        if not player or not player.playing:
            return await ctx.send("❌ Không có bài hát nào đang phát")
            
        if not self.player.playlist_tracks:
            return await ctx.send("❌ Không có bài hát nào trong playlist để bỏ qua")
            
        # Save current track info for the message
        current_track = player.current
        
        # Stop will trigger the track_end event which should play the next track
        await player.stop()
        
        # But let's also manually trigger next track in case the event doesn't work
        await asyncio.sleep(0.5)  # Small delay to allow track_end to process
        
        # If still on the same track or not playing, force play next
        if not player.playing:
            await self.player.play_next_track(player)
            
        await ctx.send(f"⏭️ Đã bỏ qua bài hát: **{current_track.title if current_track else ''}**")
    
    @commands.command(name='pause')
    async def pause(self, ctx):
        """Pause current track"""
        player = ctx.voice_client
        if player and player.playing:
            await player.pause(True)
            await ctx.send("⏸️ Đã tạm dừng")
        else:
            await ctx.send("❌ Không có bài hát nào đang phát")
    
    @commands.command(name='resume')
    async def resume(self, ctx):
        """Resume current track"""
        player = ctx.voice_client
        if player and player.paused:
            await player.pause(False)
            await ctx.send("▶️ Đã tiếp tục phát")
        else:
            await ctx.send("❌ Không có bài hát nào bị tạm dừng")
    
    @commands.command(name='volume')
    async def volume(self, ctx, vol: int = None):
        """Set or show volume"""
        player = ctx.voice_client
        if not player:
            return await ctx.send("❌ Bot không ở trong voice channel")
        
        if vol is None:
            return await ctx.send(f"🔊 Âm lượng hiện tại: {player.volume}%")
        
        if 0 <= vol <= 100:
            await player.set_volume(vol)
            await ctx.send(f"🔊 Đã đặt âm lượng: {vol}%")
        else:
            await ctx.send("❌ Âm lượng phải từ 0-100")
    
    @commands.command(name='search')
    async def search_song(self, ctx, *, query: str = None):
        """Search for songs and show results"""
        if not query:
            return await ctx.send("❌ Vui lòng nhập từ khóa tìm kiếm!")
            
        try:
            tracks = await wavelink.Playable.search(f"ytsearch:{query}")
            if not tracks:
                return await ctx.send("❌ Không tìm thấy kết quả nào!")
            
            # Show first 5 results
            embed = discord.Embed(
                title=f"🔍 Kết quả tìm kiếm: {query}",
                color=discord.Color.blue()
            )
            
            for i, track in enumerate(tracks[:5], 1):
                duration = f"{track.length // 60000}:{(track.length // 1000) % 60:02d}"
                embed.add_field(
                    name=f"{i}. {track.title[:50]}{'...' if len(track.title) > 50 else ''}",
                    value=f"**Tác giả:** {track.author}\n**Thời lượng:** {duration}",
                    inline=False
                )
            
            embed.set_footer(text="Sử dụng !play <tên bài hát> để phát nhạc")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            await ctx.send("❌ Lỗi khi tìm kiếm!")
            
    @commands.command(name='commands', aliases=['cmd', 'cmds'])
    async def help_command(self, ctx):
        """Show bot commands"""
        embed = discord.Embed(
            title="🎵 Lệnh Music Bot",
            description="Danh sách các lệnh có sẵn:",
            color=discord.Color.green()
        )
        
        commands_list = [
            ("!join [channel]", "Kết nối đến voice channel"),
            ("!leave", "Rời khỏi voice channel"),
            ("!play <tìm kiếm/URL>", "Phát nhạc từ tìm kiếm hoặc URL"),
            ("!playlist <URL>", "Tải playlist từ URL"),
            ("!search <từ khóa>", "Tìm kiếm bài hát"),
            ("!skip", "Bỏ qua bài hát hiện tại"),
            ("!pause", "Tạm dừng"),
            ("!resume", "Tiếp tục phát"),
            ("!volume [0-100]", "Điều chỉnh âm lượng"),
            ("!queue", "Hiển thị danh sách phát"),
            ("!repeat [off/one/all]", "Đặt chế độ lặp lại"),
            ("!remove <số>", "Xóa bài hát khỏi danh sách phát"),
            ("!clear", "Xóa toàn bộ danh sách phát"),
            ("!shuffle", "Xáo trộn danh sách phát"),
        ]
        
        for cmd, desc in commands_list:
            embed.add_field(name=cmd, value=desc, inline=False)
        
        embed.set_footer(text="Ví dụ: !play despacito hoặc !play https://youtu.be/...")
        await ctx.send(embed=embed)
        
    @commands.command(name='queue', aliases=['q', 'list'])
    async def show_queue(self, ctx):
        """Show current playlist queue"""
        if not self.player.playlist_tracks:
            return await ctx.send("❌ Playlist trống")
        
        # Create embed for queue
        embed = discord.Embed(
            title="🎵 Danh sách phát",
            color=discord.Color.blue()
        )
        
        # Add repeat mode info
        repeat_modes = {
            "off": "Tắt lặp lại",
            "one": "Lặp lại bài hiện tại",
            "all": "Lặp lại toàn bộ playlist"
        }
        embed.add_field(
            name="Chế độ lặp lại",
            value=repeat_modes.get(self.player.repeat_mode, "Không xác định"),
            inline=False
        )
        
        # Add tracks (current + next 9)
        total_tracks = len(self.player.playlist_tracks)
        embed.set_footer(text=f"Hiển thị {min(10, total_tracks)}/{total_tracks} bài hát")
        
        for i in range(min(10, total_tracks)):
            idx = (self.player.current_track_index + i) % total_tracks
            track = self.player.playlist_tracks[idx]
            
            # Format duration
            minutes = track.length // 60000
            seconds = (track.length // 1000) % 60
            duration = f"{minutes}:{seconds:02d}"
            
            # Mark current track
            prefix = "▶️ " if i == 0 else f"{i}. "
            
            embed.add_field(
                name=f"{prefix}{track.title[:50]}{'...' if len(track.title) > 50 else ''}",
                value=f"**Tác giả:** {track.author}\n**Thời lượng:** {duration}",
                inline=False
            )
        
        await ctx.send(embed=embed)
        
    @commands.command(name='repeat', aliases=['loop'])
    async def set_repeat(self, ctx, mode: str = None):
        """Set repeat mode: off, one, all"""
        if mode is None:
            # Display current mode
            modes = {
                "off": "Tắt lặp lại",
                "one": "Lặp lại bài hiện tại",
                "all": "Lặp lại toàn bộ playlist"
            }
            current_mode = modes.get(self.player.repeat_mode, "Không xác định")
            return await ctx.send(f"🔄 Chế độ lặp lại hiện tại: **{current_mode}**")
        
        mode = mode.lower()
        if mode in ["off", "one", "all"]:
            self.player.repeat_mode = mode
            modes = {
                "off": "Đã tắt lặp lại",
                "one": "Lặp lại bài hiện tại",
                "all": "Lặp lại toàn bộ playlist"
            }
            await ctx.send(f"🔄 {modes[mode]}")
        else:
            await ctx.send("❌ Chế độ không hợp lệ. Sử dụng: off, one, hoặc all")
            
    @commands.command(name='remove', aliases=['rm'])
    async def remove_track(self, ctx, position: int = None):
        """Remove track from playlist by position"""
        if not self.player.playlist_tracks:
            return await ctx.send("❌ Playlist trống")
        
        if position is None:
            return await ctx.send("❌ Vui lòng chỉ định vị trí bài hát cần xóa")
        
        # Convert position to index
        try:
            position = int(position)
            if position < 1 or position > len(self.player.playlist_tracks):
                return await ctx.send(f"❌ Vị trí không hợp lệ. Phải từ 1 đến {len(self.player.playlist_tracks)}")
            
            index = position - 1
            track = self.player.playlist_tracks[index]
            
            # Handle removing current track
            if index == self.player.current_track_index:
                player = ctx.voice_client
                if player and player.playing:
                    # Stop current track and play next
                    await player.stop()
                    self.player.playlist_tracks.pop(index)
                    # Adjust current index if needed
                    if self.player.current_track_index >= len(self.player.playlist_tracks):
                        self.player.current_track_index = 0
                    return await ctx.send(f"✅ Đã xóa và bỏ qua bài hát: **{track.title}**")
            
            # Remove track and adjust current index if needed
            self.player.playlist_tracks.pop(index)
            if index < self.player.current_track_index:
                self.player.current_track_index -= 1
            
            await ctx.send(f"✅ Đã xóa bài hát: **{track.title}**")
            
        except ValueError:
            await ctx.send("❌ Vị trí phải là số nguyên")
        except Exception as e:
            logger.error(f"Error removing track: {e}")
            await ctx.send(f"❌ Lỗi khi xóa bài hát: {str(e)[:100]}")
    
    @commands.command(name='clear')
    async def clear_playlist(self, ctx):
        """Clear the playlist"""
        if not self.player.playlist_tracks:
            return await ctx.send("❌ Playlist đã trống")
        
        # Save current track if playing
        player = ctx.voice_client
        current_track = None
        
        if player and player.playing:
            current_track = player.current
            await player.stop()
            
        # Clear playlist
        self.player.clear_queue()
        
        # Add current track back if needed
        if current_track:
            self.player.playlist_tracks = [current_track]
            # Restart the current track
            await self.player.play_track(player, current_track)
            await ctx.send("🧹 Đã xóa tất cả bài hát khỏi playlist (ngoại trừ bài đang phát)")
        else:
            await ctx.send("🧹 Đã xóa tất cả bài hát khỏi playlist")
    
    @commands.command(name='shuffle')
    async def shuffle_playlist(self, ctx):
        """Shuffle the playlist"""
        if not self.player.playlist_tracks or len(self.player.playlist_tracks) < 2:
            return await ctx.send("❌ Cần ít nhất 2 bài hát để xáo trộn playlist")
            
        if self.player.shuffle_queue():
            await ctx.send("🔀 Đã xáo trộn playlist")
            # Show the new queue
            await self.show_queue(ctx)
        else:
            await ctx.send("❌ Không thể xáo trộn playlist") 