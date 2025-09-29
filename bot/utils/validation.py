"""
Validation utilities for the music bot
Common validation functions used across commands
"""

from typing import Tuple, Optional
from ..config.constants import LIMITS, ERROR_MESSAGES


class ValidationUtils:
    """Utility class for input validation"""
    
    @staticmethod
    def validate_query_length(query: str) -> Tuple[bool, Optional[str]]:
        """Validate query length"""
        if len(query) > LIMITS['query_max_length']:
            return False, f"❌ Query quá dài! Giới hạn {LIMITS['query_max_length']} ký tự."
        return True, None
    
    @staticmethod
    def validate_volume(volume: int) -> Tuple[bool, Optional[str]]:
        """Validate volume range"""
        if not LIMITS['volume_min'] <= volume <= LIMITS['volume_max']:
            return False, ERROR_MESSAGES['invalid_volume']
        return True, None
    
    @staticmethod
    def validate_playlist_index(index: int, playlist_size: int) -> Tuple[bool, Optional[str]]:
        """Validate playlist index"""
        if index < 1 or index > playlist_size:
            return False, f"❌ Index không hợp lệ! Phải từ 1 đến {playlist_size}."
        return True, None
    
    @staticmethod
    def validate_page_number(page: int, total_pages: int) -> Tuple[bool, Optional[str]]:
        """Validate page number for pagination"""
        if page < 1:
            return False, "❌ Trang phải lớn hơn 0!"
        if page > total_pages and total_pages > 0:
            return False, f"❌ Trang {page} không tồn tại! Chỉ có {total_pages} trang."
        return True, None
    
    @staticmethod
    def sanitize_query(query: str) -> str:
        """Sanitize and clean query input"""
        if not query:
            return ""
        
        # Strip whitespace and normalize
        query = query.strip()
        
        # Remove potential malicious patterns (basic protection)
        dangerous_patterns = ['<script', 'javascript:', 'data:', 'vbscript:']
        query_lower = query.lower()
        
        for pattern in dangerous_patterns:
            if pattern in query_lower:
                query = query.replace(pattern, '')
        
        return query
    
    @staticmethod
    def validate_playlist_name(name: str) -> Tuple[bool, Optional[str]]:
        """Validate playlist name"""
        if not name or not name.strip():
            return False, "❌ Tên playlist không được để trống!"
        
        name = name.strip()
        
        # Check length
        if len(name) > 50:
            return False, "❌ Tên playlist quá dài! Tối đa 50 ký tự."
        
        # Check for invalid characters
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in name:
                return False, f"❌ Tên playlist không được chứa ký tự '{char}'!"
        
        return True, None
    
    @staticmethod
    def validate_repeat_mode(mode: str) -> Tuple[bool, Optional[str]]:
        """Validate repeat mode"""
        valid_modes = ['off', 'track', 'queue']
        if mode.lower() not in valid_modes:
            return False, f"❌ Chế độ lặp không hợp lệ! Sử dụng: {', '.join(valid_modes)}"
        return True, None


class PermissionUtils:
    """Utility class for permission checking"""
    
    @staticmethod
    def is_admin(interaction) -> bool:
        """Check if user has admin permissions"""
        if not hasattr(interaction.user, 'guild_permissions'):
            return False
        return interaction.user.guild_permissions.administrator
    
    @staticmethod
    def is_moderator(interaction) -> bool:
        """Check if user has moderator permissions"""
        if not hasattr(interaction.user, 'guild_permissions'):
            return False
        
        perms = interaction.user.guild_permissions
        return (
            perms.administrator or
            perms.manage_guild or
            perms.manage_channels or
            perms.manage_messages
        )
    
    @staticmethod
    def can_use_voice_commands(interaction) -> Tuple[bool, Optional[str]]:
        """Check if user can use voice commands"""
        if not hasattr(interaction.user, 'voice') or not interaction.user.voice:
            return False, ERROR_MESSAGES['voice_required']
        
        voice_channel = interaction.user.voice.channel
        if not voice_channel:
            return False, ERROR_MESSAGES['voice_required']
        
        # Check voice permissions
        permissions = voice_channel.permissions_for(interaction.guild.me)
        if not permissions.connect:
            return False, "❌ Bot không có quyền kết nối voice channel!"
        
        if not permissions.speak:
            return False, "❌ Bot không có quyền nói trong voice channel!"
        
        return True, None


class FormatUtils:
    """Utility class for formatting strings"""
    
    @staticmethod
    def format_duration(seconds: int) -> str:
        """Format duration in seconds to readable format"""
        if seconds < 60:
            return f"{seconds}s"
        
        minutes = seconds // 60
        seconds = seconds % 60
        
        if minutes < 60:
            return f"{minutes}:{seconds:02d}"
        
        hours = minutes // 60
        minutes = minutes % 60
        
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    
    @staticmethod
    def format_file_size(bytes_size: int) -> str:
        """Format file size to readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} TB"
    
    @staticmethod
    def format_uptime(seconds: int) -> str:
        """Format uptime to readable format"""
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")
        
        return " ".join(parts)
    
    @staticmethod
    def truncate_string(text: str, max_length: int = 50, suffix: str = "...") -> str:
        """Truncate string with custom suffix"""
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
