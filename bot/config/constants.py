"""
Constants for the music bot
Centralized configuration and magic strings
"""

# Command descriptions
COMMAND_DESCRIPTIONS = {
    "ping": "Kiểm tra độ trễ bot",
    "join": "Tham gia voice channel",
    "leave": "Rời voice channel",
    "play": "Phát nhạc từ URL/tìm kiếm hoặc từ playlist hiện tại",
    "skip": "Bỏ qua bài hiện tại",
    "pause": "Tạm dừng phát",
    "resume": "Tiếp tục phát nhạc",
    "stop": "Dừng và xóa hàng đợi",
    "queue": "Hiển thị hàng đợi hiện tại",
    "volume": "Đặt âm lượng (0-100)",
    "now": "Hiển thị bài đang phát",
    "repeat": "Set repeat mode",
    "use": "Chọn playlist để sử dụng làm queue mặc định",
    "create": "Tạo playlist mới",
    "add": "Thêm bài hát vào playlist hiện tại",
    "addto": "Thêm bài hát vào playlist chỉ định",
    "remove": "Xóa bài hát khỏi playlist",
    "playlists": "Liệt kê tất cả playlist",
    "playlist": "Hiển thị nội dung playlist",
    "delete": "Xóa playlist",
    "help": "Hiển thị thông tin về bot và các tính năng",
    "aplay": "Phát toàn bộ playlist YouTube (Async Processing)",
}

# Error messages
ERROR_MESSAGES = {
    "guild_only": "⛔ Lệnh này chỉ có thể sử dụng trong server!",
    "voice_required": "Hãy tham gia voice channel trước!",
    "not_connected": "⛔ Bot chưa kết nối voice!",
    "cannot_connect_voice": "Không thể kết nối voice channel",
    "same_channel_required": "❌ Bạn phải ở cùng voice channel với bot!",
    # queue
    "no_queue": "❌ Không có hàng đợi nào!",
    "cannot_init_queue": "❌ Không thể khởi tạo hàng đợi!",
    "no_song_playing": "❌ Không có bài nào đang phát!",
    # playlist
    "playlist_playback_error": "❌ Lỗi khi phát playlist!",
    "no_active_playlist": "❌ Chưa có playlist nào được chọn! Sử dụng `/use <playlist>` trước.",
    "playlist_service_unavailable": "❌ Playlist service không khả dụng!",
    "invalid_volume": "❌ Âm lượng phải từ 0 đến 100!",
    "cannot_set_volume": "❌ Không thể đặt âm lượng!",
    "invalid_playlist_url": "❌ Đây không phải URL playlist YouTube hợp lệ!",
    "playlist_extraction_error": "❌ Lỗi trích xuất playlist",
    "cannot_set_repeat": "❌ Không thể đặt chế độ lặp!",
    "invalid_repeat_mode": "❌ Chế độ lặp không hợp lệ! Sử dụng: off, track, queue",
    "command_error": "❌ Lỗi trong lệnh",
    "unexpected_error": "❌ Lỗi không mong đợi",
}

# Success messages
SUCCESS_MESSAGES = {
    "connected": "Đã kết nối với voice channel **{}**!",
    "disconnected": "Đã rời khỏi voice channel **{}**!",
    "moved_channel": "Đã chuyển đến voice channel **{}**!",
    "song_skipped": "Đã bỏ qua bài hát",
    "playback_paused": "Tạm dừng",
    "playback_resumed": "Tiếp tục",
    "playback_stopped": "Đã dừng phát nhạc",
    "volume_set": "Âm lượng đã đặt",
    "playlist_created": "Tạo playlist thành công",
    "playlist_selected": "Đã chọn playlist",
    "song_added": "Đã thêm vào playlist và queue",
    "playlist_deleted": "Đã xóa playlist",
    "song_removed": "Đã xóa bài hát",
}

# Processing messages
PROCESSING_MESSAGES = {
    "searching": "🔍 **Processing:** {}",
    "youtube_playlist": "🎵 Processing YouTube Playlist...",
    "async_playlist": "🚀 Processing YouTube Playlist Asynchronously...",
    "adding_playlist": "🎵 Adding YouTube Playlist to queue and active playlist...",
}

# Emojis
EMOJIS = {
    "ping": "⚲",
    "connect": "⏻",
    "disconnect": "⏻",
    "play": "▶",
    "pause": "||",
    "resume": "▶",
    "skip": "⏭",
    "stop": "◼",
    "queue": "☰",
    "volume_mute": "🔇",
    "volume_low": "🔉",
    "volume_medium": "🔊",
    "volume_high": "📢",
    "now": "♫",
    "repeat_off": "⟲",
    "repeat_track": "⟲",
    "repeat_queue": "⟲",
    "playlist": "☰",
    "create": "☰",
    "add": "✚",
    "remove": "🗑",
    "delete": "🗑",
    "help": "❔",
    "async": "ᯓ ✈︎",
    "error": "✗",
    "success": "✔",
    "warning": "⚠",
    "info": "ⓘ",
}

# Limits and constraints
LIMITS = {
    "query_max_length": 500,
    "playlist_max_videos": 50,
    "queue_display_limit": 10,
    "playlist_display_limit": 20,
    "volume_min": 0,
    "volume_max": 100,
}

# Colors
COLORS = {
    "success": 0x00FF00,  # Green
    "error": 0xFF0000,  # Red
    "warning": 0xFFA500,  # Orange
    "info": 0x0099FF,  # Blue
    "primary": 0x7289DA,  # Discord Blurple
}

# Stream URL refresh settings (for 24/7 operation)
STREAM_URL_MAX_AGE = 18000  # 5 hours in seconds (YouTube URLs expire ~6h)
STREAM_URL_REFRESH_INTERVAL = 3600  # Check every hour
STREAM_URL_REFRESH_THRESHOLD = 900  # Refresh if expires in 15 minutes

# Auto-recovery settings
AUTO_RECOVERY_COOLDOWN = 300  # 5 minutes between recoveries
SCHEDULED_MAINTENANCE_INTERVAL = 21600  # 6 hours
MAX_CACHE_AGE_DAYS = 7  # Delete cache older than 7 days
