import discord
from discord.ext import commands, tasks
import wavelink
import asyncio
import logging
import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix=config.COMMAND_PREFIX, intents=intents)

class MusicBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_channel = None
        self.current_voice_channel = None
        self.is_playing = False
        self.playlist_tracks = []
        self.current_track_index = 0
        
    async def setup_lavalink(self):
        """Setup Lavalink connection"""
        try:
            node = wavelink.Node(
                uri=f"http://{config.LAVALINK_HOST}:{config.LAVALINK_PORT}",
                password=config.LAVALINK_PASSWORD,
            )
            await wavelink.Pool.connect(client=self.bot, nodes=[node])
            logger.info("Lavalink connected successfully!")
        except Exception as e:
            logger.error(f"Failed to connect to Lavalink: {e}")
            # Retry after 10 seconds
            await asyncio.sleep(10)
            await self.setup_lavalink()
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Bot ready event"""
        logger.info(f'{self.bot.user} is ready!')
        
        # Wait for Lavalink to be ready
        await asyncio.sleep(5)
        await self.setup_lavalink()
        
        # Auto-connect to voice channel if configured
        if config.DEFAULT_VOICE_CHANNEL_ID:
            await asyncio.sleep(2)  # Wait a bit more for full initialization
            await self.auto_connect()
            
        # Start keep alive task
        if not self.keep_alive_task.is_running():
            self.keep_alive_task.start()
    
    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """Handle track end event"""
        if payload.reason == "finished":
            await self.play_next_track(payload.player)
    
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
                self.current_voice_channel = voice_channel
                self.current_channel = text_channel
                await player.set_volume(config.VOLUME_DEFAULT)
                logger.info(f"Connected to {voice_channel.name}")
                
                if text_channel:
                    await text_channel.send(f"🎵 Bot đã kết nối đến {voice_channel.name}")
                
                # Load default playlist if configured
                if config.DEFAULT_PLAYLIST_URL:
                    await self.load_playlist(config.DEFAULT_PLAYLIST_URL, player)
                    
        except Exception as e:
            logger.error(f"Auto-connect failed: {e}")
    
    async def load_playlist(self, url: str, player: wavelink.Player):
        """Load playlist from URL"""
        try:
            # Add ytsearch prefix if it's just text
            if not url.startswith(('http://', 'https://')):
                url = f"ytsearch:{url}"
                
            tracks = await wavelink.Playable.search(url)
            if tracks:
                self.playlist_tracks = tracks if isinstance(tracks, list) else [tracks]
                self.current_track_index = 0
                await self.play_track(player, self.playlist_tracks[0])
                
                if self.current_channel:
                    await self.current_channel.send(f"🎵 Đã tải playlist với {len(self.playlist_tracks)} bài hát")
            else:
                if self.current_channel:
                    await self.current_channel.send("❌ Không thể tải playlist. Kiểm tra lại URL!")
                    
        except Exception as e:
            logger.error(f"Failed to load playlist: {e}")
            if self.current_channel:
                await self.current_channel.send(f"❌ Không thể tải playlist: {str(e)[:100]}")
    
    async def play_track(self, player: wavelink.Player, track):
        """Play a specific track"""
        try:
            await player.play(track, replace=True)
            self.is_playing = True
            
            if self.current_channel:
                embed = discord.Embed(
                    title="🎵 Đang phát",
                    description=f"**{track.title}**\n{track.author}",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Thời lượng", value=f"{track.length // 60000}:{(track.length // 1000) % 60:02d}", inline=True)
                await self.current_channel.send(embed=embed)
                
        except Exception as e:
            logger.error(f"Failed to play track: {e}")
            self.is_playing = False
    
    async def play_next_track(self, player: wavelink.Player):
        """Play next track in playlist"""
        if self.playlist_tracks:
            self.current_track_index = (self.current_track_index + 1) % len(self.playlist_tracks)
            next_track = self.playlist_tracks[self.current_track_index]
            await self.play_track(player, next_track)
    
    @tasks.loop(minutes=5)
    async def keep_alive_task(self):
        """Keep bot alive and reconnect if needed"""
        try:
            if config.AUTO_RECONNECT and self.current_voice_channel:
                voice_client = discord.utils.get(self.bot.voice_clients, channel=self.current_voice_channel)
                
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
            self.current_voice_channel = channel
            self.current_channel = ctx.channel
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
            self.current_voice_channel = None
            self.is_playing = False
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
            
            track = tracks[0] if isinstance(tracks, list) else tracks
            await self.play_track(player, track)
            
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
        await self.load_playlist(url, player)
    
    @commands.command(name='skip')
    async def skip(self, ctx):
        """Skip current track"""
        player = ctx.voice_client
        if player and player.playing:
            await player.stop()
            await ctx.send("⏭️ Đã bỏ qua bài hát")
        else:
            await ctx.send("❌ Không có bài hát nào đang phát")
    
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
            ("!now", "Hiển thị bài hát đang phát"),
        ]
        
        for cmd, desc in commands_list:
            embed.add_field(name=cmd, value=desc, inline=False)
        
        embed.set_footer(text="Ví dụ: !play despacito hoặc !play https://youtu.be/...")
        await ctx.send(embed=embed)

# Add cog and run bot
async def main():
    async with bot:
        await bot.add_cog(MusicBot(bot))
        await bot.start(config.DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())