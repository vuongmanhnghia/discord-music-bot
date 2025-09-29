"""
Utility functions for creating Discord embeds
Standardizes embed creation across the bot
"""

import discord
from typing import Optional
from ..config.constants import COLORS, EMOJIS


class EmbedFactory:
    """Factory class for creating standardized Discord embeds"""
    
    @staticmethod
    def create_success_embed(title: str, description: str = "", **kwargs) -> discord.Embed:
        """Create a success embed with green color"""
        embed = discord.Embed(
            title=f"{EMOJIS['success']} {title}",
            description=description,
            color=COLORS['success']
        )
        return EmbedFactory._add_common_fields(embed, **kwargs)
    
    @staticmethod
    def create_error_embed(title: str, description: str = "", **kwargs) -> discord.Embed:
        """Create an error embed with red color"""
        embed = discord.Embed(
            title=f"{EMOJIS['error']} {title}",
            description=description,
            color=COLORS['error']
        )
        return EmbedFactory._add_common_fields(embed, **kwargs)
    
    @staticmethod
    def create_warning_embed(title: str, description: str = "", **kwargs) -> discord.Embed:
        """Create a warning embed with orange color"""
        embed = discord.Embed(
            title=f"{EMOJIS['warning']} {title}",
            description=description,
            color=COLORS['warning']
        )
        return EmbedFactory._add_common_fields(embed, **kwargs)
    
    @staticmethod
    def create_info_embed(title: str, description: str = "", **kwargs) -> discord.Embed:
        """Create an info embed with blue color"""
        embed = discord.Embed(
            title=f"{EMOJIS['info']} {title}" if not title.startswith(tuple(EMOJIS.values())) else title,
            description=description,
            color=COLORS['info']
        )
        return EmbedFactory._add_common_fields(embed, **kwargs)
    
    @staticmethod
    def create_music_embed(title: str, description: str = "", song=None, **kwargs) -> discord.Embed:
        """Create a music-related embed with song information"""
        embed = discord.Embed(
            title=f"{EMOJIS['nowplaying']} {title}",
            description=description,
            color=COLORS['primary']
        )
        
        if song:
            EmbedFactory._add_song_fields(embed, song)
            
        return EmbedFactory._add_common_fields(embed, **kwargs)
    
    @staticmethod
    def create_queue_embed(current_song=None, queue_list=None, page: int = 1, **kwargs) -> discord.Embed:
        """Create a queue display embed"""
        embed = discord.Embed(
            title=f"{EMOJIS['queue']} Hàng đợi nhạc",
            color=COLORS['info']
        )
        
        # Current playing song
        if current_song:
            embed.add_field(
                name=f"{EMOJIS['nowplaying']} Đang phát",
                value=f"**{current_song.display_name}**",
                inline=False
            )
        
        # Queue pagination
        if queue_list:
            items_per_page = 10
            total_pages = (len(queue_list) + items_per_page - 1) // items_per_page
            
            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            page_items = queue_list[start_idx:end_idx]
            
            queue_text = ""
            for i, song in enumerate(page_items, start=start_idx + 1):
                queue_text += f"`{i}.` **{song.display_name}**\n"
            
            embed.add_field(
                name=f"📄 Danh sách ({len(queue_list)} bài)",
                value=queue_text if queue_text else "Hàng đợi trống",
                inline=False
            )
            
            if total_pages > 1:
                embed.set_footer(text=f"Trang {page}/{total_pages}")
        else:
            embed.add_field(
                name="📄 Danh sách",
                value="Hàng đợi trống",
                inline=False
            )
        
        return EmbedFactory._add_common_fields(embed, **kwargs)
    
    @staticmethod
    def create_playlist_embed(playlist_name: str, songs: list, **kwargs) -> discord.Embed:
        """Create a playlist display embed"""
        embed = discord.Embed(
            title=f"{EMOJIS['playlist']} Playlist: {playlist_name}",
            color=COLORS['info']
        )
        
        if not songs:
            embed.add_field(
                name="📄 Nội dung",
                value="Playlist trống",
                inline=False
            )
        else:
            # Show first 20 songs
            display_songs = songs[:20]
            songs_text = ""
            
            for i, song in enumerate(display_songs, 1):
                title = song.get('title', song.get('input', 'Unknown'))
                source = song.get('source_type', 'Unknown')
                songs_text += f"`{i}.` **{title}** `({source})`\n"
            
            embed.add_field(
                name=f"📄 Nội dung ({len(songs)} bài)",
                value=songs_text,
                inline=False
            )
            
            if len(songs) > 20:
                embed.set_footer(text=f"Hiển thị 20/{len(songs)} bài đầu tiên")
        
        return EmbedFactory._add_common_fields(embed, **kwargs)
    
    @staticmethod
    def create_volume_embed(volume: int, **kwargs) -> discord.Embed:
        """Create volume display embed"""
        # Volume icon based on level
        if volume == 0:
            icon = EMOJIS['volume_mute']
        elif volume <= 33:
            icon = EMOJIS['volume_low']
        elif volume <= 66:
            icon = EMOJIS['volume_medium']
        else:
            icon = EMOJIS['volume_high']
        
        embed = discord.Embed(
            title=f"{icon} Âm lượng đã đặt",
            description=f"**{volume}%**",
            color=COLORS['success']
        )
        
        return EmbedFactory._add_common_fields(embed, **kwargs)
    
    @staticmethod
    def _add_song_fields(embed: discord.Embed, song):
        """Add song information fields to embed"""
        if hasattr(song, 'source_type'):
            embed.add_field(
                name="Nguồn",
                value=song.source_type.value.title(),
                inline=True
            )
        
        if hasattr(song, 'status'):
            embed.add_field(
                name="Trạng thái",
                value=song.status.value.title(),
                inline=True
            )
        
        if hasattr(song, 'metadata') and song.metadata:
            if hasattr(song, 'duration_formatted'):
                embed.add_field(
                    name="Thời lượng",
                    value=song.duration_formatted,
                    inline=True
                )
    
    @staticmethod
    def _add_common_fields(embed: discord.Embed, footer: Optional[str] = None, **kwargs) -> discord.Embed:
        """Add common fields to embed"""
        if footer:
            embed.set_footer(text=footer)
        
        return embed


class EmbedUtils:
    """Utility functions for embed operations"""
    
    @staticmethod
    def get_volume_emoji(volume: int) -> str:
        """Get appropriate volume emoji based on level"""
        if volume == 0:
            return EMOJIS['volume_mute']
        elif volume <= 33:
            return EMOJIS['volume_low']
        elif volume <= 66:
            return EMOJIS['volume_medium']
        else:
            return EMOJIS['volume_high']
    
    @staticmethod
    def get_repeat_mode_emoji(mode: str) -> str:
        """Get appropriate repeat mode emoji"""
        mode_emojis = {
            'off': EMOJIS['repeat_off'],
            'track': EMOJIS['repeat_track'],
            'queue': EMOJIS['repeat_queue']
        }
        return mode_emojis.get(mode.lower(), EMOJIS['repeat_off'])
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 50) -> str:
        """Truncate text with ellipsis if too long"""
        if len(text) > max_length:
            return f"{text[:max_length]}..."
        return text
    
    @staticmethod
    def format_progress_bar(current: int, total: int, length: int = 20) -> str:
        """Create a text progress bar"""
        if total == 0:
            return "▬" * length
        
        filled = int((current / total) * length)
        bar = "▰" * filled + "▱" * (length - filled)
        return f"{bar} {current}/{total}"
