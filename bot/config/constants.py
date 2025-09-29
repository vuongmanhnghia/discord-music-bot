"""
Constants for the music bot
Centralized configuration and magic strings
"""

# Command descriptions
COMMAND_DESCRIPTIONS = {
    'ping': "Kiểm tra độ trễ bot",
    'join': "Tham gia voice channel", 
    'leave': "Rời voice channel",
    'play': "Phát nhạc từ URL/tìm kiếm hoặc từ playlist hiện tại",
    'skip': "Bỏ qua bài hiện tại",
    'pause': "Tạm dừng phát",
    'resume': "Tiếp tục phát nhạc",
    'stop': "Dừng và xóa hàng đợi",
    'queue': "Hiển thị hàng đợi hiện tại",
    'volume': "Đặt âm lượng (0-100)",
    'nowplaying': "Hiển thị bài đang phát",
    'repeat': "Set repeat mode",
    'use': "Chọn playlist để sử dụng làm queue mặc định",
    'create': "Tạo playlist mới",
    'add': "Thêm bài hát vào playlist hiện tại",
    'addto': "Thêm bài hát vào playlist chỉ định",
    'remove': "Xóa bài hát khỏi playlist",
    'playlists': "Liệt kê tất cả playlist",
    'playlist': "Hiển thị nội dung playlist",
    'delete': "Xóa playlist",
    'help': "Hiển thị thông tin về bot và các tính năng",
    'aplay': "Phát toàn bộ playlist YouTube (Async Processing)"
}

# Error messages
ERROR_MESSAGES = {
    'guild_only': "⛔ Lệnh này chỉ có thể sử dụng trong server!",
    'voice_required': "Hãy tham gia voice channel trước!",
    'not_connected': "⛔ Bot chưa kết nối voice!",
    'same_channel_required': "❌ Bạn phải ở cùng voice channel với bot!",
    'no_queue': "❌ Không có hàng đợi nào!",
    'no_song_playing': "❌ Không có bài nào đang phát!",
    'no_active_playlist': "❌ Chưa có playlist nào được chọn! Sử dụng `/use <playlist>` trước.",
    'playlist_service_unavailable': "❌ Playlist service không khả dụng!",
    'invalid_volume': "❌ Âm lượng phải từ 0 đến 100!",
    'invalid_playlist_url': "❌ Đây không phải URL playlist YouTube hợp lệ!"
}

# Success messages
SUCCESS_MESSAGES = {
    'connected': "🔌 Đã kết nối với **{}**!",
    'disconnected': "👋 Đã rời khỏi **{}**!",
    'moved_channel': "🔄 Đã chuyển đến **{}**!",
    'song_skipped': "⏭️ Đã bỏ qua bài hát",
    'playback_paused': "⏸️ Tạm dừng",
    'playback_resumed': "▶️ Tiếp tục",
    'playback_stopped': "⏹️ Đã dừng phát nhạc",
    'volume_set': "🔊 Âm lượng đã đặt",
    'playlist_created': "✅ Tạo playlist thành công",
    'song_added': "✅ Đã thêm vào playlist và queue",
    'playlist_deleted': "✅ Đã xóa playlist",
    'song_removed': "✅ Đã xóa bài hát"
}

# Processing messages
PROCESSING_MESSAGES = {
    'searching': "🔍 **Processing:** {}",
    'youtube_playlist': "🎵 Processing YouTube Playlist...",
    'async_playlist': "🚀 Processing YouTube Playlist Asynchronously...",
    'adding_playlist': "🎵 Adding YouTube Playlist to queue and active playlist..."
}

# Emojis
EMOJIS = {
    'ping': "🏓",
    'connect': "🔌", 
    'disconnect': "👋",
    'play': "▶️",
    'pause': "⏸️",
    'resume': "▶️",
    'skip': "⏭️",
    'stop': "⏹️",
    'queue': "📋",
    'volume_mute': "🔇",
    'volume_low': "🔉", 
    'volume_medium': "🔊",
    'volume_high': "📢",
    'nowplaying': "🎵",
    'repeat_off': "📴",
    'repeat_track': "🔂",
    'repeat_queue': "🔁",
    'playlist': "📋",
    'create': "📝",
    'add': "➕",
    'remove': "🗑️",
    'delete': "🗑️",
    'help': "❓",
    'async': "🚀",
    'error': "❌",
    'success': "✅",
    'warning': "⚠️",
    'info': "ℹ️"
}

# Limits and constraints
LIMITS = {
    'query_max_length': 500,
    'playlist_max_videos': 50,
    'queue_display_limit': 10,
    'playlist_display_limit': 20,
    'volume_min': 0,
    'volume_max': 100
}

# Colors
COLORS = {
    'success': 0x00ff00,  # Green
    'error': 0xff0000,    # Red  
    'warning': 0xffa500,  # Orange
    'info': 0x0099ff,     # Blue
    'primary': 0x7289da   # Discord Blurple
}
