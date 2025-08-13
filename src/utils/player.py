import wavelink
import discord
import asyncio
import config
from utils.logger import logger

class MusicPlayer:
    """Class to manage music player functionality"""
    
    def __init__(self):
        self.playlist_tracks = []
        self.current_track_index = 0
        self.is_playing = False
        self.current_channel = None
        self.current_voice_channel = None
        self.repeat_mode = "all"  # Options: "off", "one", "all"
        
    async def setup_lavalink(self, bot):
        """Setup and connect to Lavalink"""
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                logger.info(f"Connecting to Lavalink at {config.LAVALINK_HOST}:{config.LAVALINK_PORT}")
                node = wavelink.Node(
                    uri=f"http://{config.LAVALINK_HOST}:{config.LAVALINK_PORT}",
                    password=config.LAVALINK_PASSWORD,
                )
                await wavelink.Pool.connect(client=bot, nodes=[node])
                logger.info("Lavalink connected successfully!")
                return True
            except Exception as e:
                retry_count += 1
                logger.error(f"Failed to connect to Lavalink (attempt {retry_count}/{max_retries}): {e}")
                # Increase wait time between retries
                wait_time = 10 * retry_count
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
                # No recursive call here, using while loop instead
        
        logger.error("Maximum retries reached. Could not connect to Lavalink.")
        return False
    
    async def play_track(self, player: wavelink.Player, track):
        """Play a specific track"""
        try:
            # Ensure we have a valid playable track
            if not track or not hasattr(track, 'title'):
                logger.error("Invalid track object")
                if self.current_channel:
                    await self.current_channel.send("❌ Không thể phát: Bài hát không hợp lệ")
                return False
            
            await player.play(track, replace=True)
            self.is_playing = True
            
            if self.current_channel:
                embed = discord.Embed(
                    title="🎵 Đang phát",
                    description=f"**{track.title}**\n{track.author}",
                    color=discord.Color.blue()
                )
                
                # Format duration properly
                minutes = track.length // 60000
                seconds = (track.length // 1000) % 60
                embed.add_field(name="Thời lượng", value=f"{minutes}:{seconds:02d}", inline=True)
                
                # Add thumbnail if available
                if hasattr(track, 'artwork_url') and track.artwork_url:
                    embed.set_thumbnail(url=track.artwork_url)
                    
                await self.current_channel.send(embed=embed)
                return True
                
        except Exception as e:
            logger.error(f"Failed to play track: {e}")
            self.is_playing = False
            if self.current_channel:
                await self.current_channel.send(f"❌ Lỗi khi phát nhạc: {str(e)[:100]}")
            return False
    
    async def play_next_track(self, player: wavelink.Player):
        """Play next track in playlist"""
        try:
            if not self.playlist_tracks or len(self.playlist_tracks) == 0:
                logger.info("No tracks in playlist to play next")
                if self.current_channel:
                    await self.current_channel.send("❌ Không còn bài hát nào trong playlist")
                return False
            
            # Handle different repeat modes
            if self.repeat_mode == "one":
                # Stay on current track
                next_track = self.playlist_tracks[self.current_track_index]
            else:
                # Move to next track (default behavior)
                self.current_track_index = (self.current_track_index + 1) % len(self.playlist_tracks)
                next_track = self.playlist_tracks[self.current_track_index]
                
                # Notify when playlist loops back to beginning
                if self.repeat_mode == "all" and self.current_track_index == 0 and len(self.playlist_tracks) > 1:
                    if self.current_channel:
                        await self.current_channel.send("🔄 Playlist bắt đầu lại từ đầu")
            
            # Validate track before playing
            if not next_track or not hasattr(next_track, 'title'):
                logger.error("Invalid next track in playlist")
                if self.current_channel:
                    await self.current_channel.send("❌ Bài hát tiếp theo không hợp lệ, đang bỏ qua...")
                # Try to get the next track instead of recursion
                self.current_track_index = (self.current_track_index + 1) % len(self.playlist_tracks)
                return await self.play_next_track(player)
                
            return await self.play_track(player, next_track)
                
        except Exception as e:
            logger.error(f"Error playing next track: {e}")
            if self.current_channel:
                await self.current_channel.send(f"❌ Lỗi khi phát bài tiếp theo: {str(e)[:100]}")
            return False
    
    async def load_playlist(self, url: str, player: wavelink.Player):
        """Load playlist from URL"""
        try:
            # Add ytsearch prefix if it's just text
            if not url.startswith(('http://', 'https://')):
                url = f"ytsearch:{url}"
                
            tracks = await wavelink.Playable.search(url)
            if not tracks:
                if self.current_channel:
                    await self.current_channel.send("❌ Không thể tải playlist. Kiểm tra lại URL!")
                return
                
            # Handle different return types from wavelink.Playable.search
            if hasattr(tracks, 'tracks'):  # If it's a playlist object
                self.playlist_tracks = tracks.tracks
            elif isinstance(tracks, list):  # If it's a list of tracks
                self.playlist_tracks = tracks
            else:  # If it's a single track
                self.playlist_tracks = [tracks]
                
            if not self.playlist_tracks:
                if self.current_channel:
                    await self.current_channel.send("❌ Playlist trống!")
                return
                
            self.current_track_index = 0
            await self.play_track(player, self.playlist_tracks[0])
            
            if self.current_channel:
                await self.current_channel.send(f"🎵 Đã tải playlist với {len(self.playlist_tracks)} bài hát")
                    
        except Exception as e:
            logger.error(f"Failed to load playlist: {e}")
            if self.current_channel:
                await self.current_channel.send(f"❌ Không thể tải playlist: {str(e)[:100]}")
                
    def clear_queue(self):
        """Clear the playlist queue"""
        self.playlist_tracks = []
        self.current_track_index = 0
        
    def shuffle_queue(self):
        """Shuffle the playlist queue"""
        if len(self.playlist_tracks) < 2:
            return False
        
        # Save current track
        current_track = None
        if self.playlist_tracks and len(self.playlist_tracks) > self.current_track_index:
            current_track = self.playlist_tracks[self.current_track_index]
        
        # Remove current track from list temporarily
        if current_track:
            self.playlist_tracks.pop(self.current_track_index)
        
        # Shuffle remaining tracks
        import random
        random.shuffle(self.playlist_tracks)
        
        # Add current track back at position 0
        if current_track:
            self.playlist_tracks.insert(0, current_track)
            self.current_track_index = 0
            
        return True 