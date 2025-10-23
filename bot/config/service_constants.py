"""
Service-level constants for configuration
Centralized magic numbers and thresholds
"""


class ServiceConstants:
    """Constants for service layer configuration"""

    # Audio Player
    SONG_PROCESSING_WAIT_TIMEOUT = 30  # seconds to wait for song processing
    PLAYBACK_RETRY_MAX_ATTEMPTS = 3  # max retry attempts for playback
    PLAYBACK_RETRY_DELAY = 2  # seconds between retries
    STOP_PLAYBACK_DELAY = 0.5  # delay after stopping playback
    SKIP_PLAYBACK_DELAY = 0.3  # delay after skipping

    # Caching
    CACHE_WARM_ACCESS_THRESHOLD = 2  # minimum access count for cache warming
    CACHE_WARM_POPULAR_LIMIT = 20  # number of popular URLs to warm

    # Playlist Processing
    IMMEDIATE_PROCESS_COUNT = 3  # songs to process immediately when loading playlist
    BATCH_PROCESS_DELAY = 0.1  # delay between batch processing items

    # Stream Refresh
    STREAM_URL_REFRESH_DELAY = 2  # delay between stream URL refreshes
    STREAM_REFRESH_RETRY_DELAY = 5  # delay before retry after refresh failure

    # Recovery
    RECOVERY_COOLDOWN_SECONDS = 300  # 5 minutes between auto-recovery attempts
    RECOVERY_POST_WAIT = 2  # seconds to wait after recovery

    # Playlist Switch
    SWITCH_CANCEL_TIMEOUT = 3.0  # timeout for cancelling tasks during switch
    SWITCH_CLEANUP_DELAY = 0.5  # delay for cleanup after stopping playback

    # YouTube Processing
    YOUTUBE_EXTRACT_TIMEOUT_BASE = (
        45  # base timeout for YouTube extraction (increased from 30)
    )
    YOUTUBE_EXTRACT_TIMEOUT_INCREMENT = 15  # additional timeout per retry
    YOUTUBE_RETRY_MAX_ATTEMPTS = 3  # max retry attempts for YouTube
    YOUTUBE_STREAM_TIMEOUT = 60  # timeout for stream URL extraction (increased from 45)
    YOUTUBE_RETRY_DELAYS = [2, 5, 10]  # exponential backoff delays (increased)

    # Metadata Extraction
    METADATA_EXTRACTION_TIMEOUT = (
        45  # timeout for metadata extraction (increased from 30)
    )
    BASIC_INFO_TIMEOUT = 30  # timeout for basic info fallback (increased from 20)

    # Connection
    VOICE_CONNECT_TIMEOUT = 30.0  # timeout for voice channel connection
    VOICE_DISCONNECT_TIMEOUT = 5.0  # timeout for voice channel disconnection

    # Task Management
    TASK_CANCELLATION_TIMEOUT = 3.0  # timeout for task cancellation
    ASYNC_TASK_SUBMIT_DELAY = 0.1  # delay between async task submissions

    # Stream Refresh
    STREAM_REFRESH_DELAY = 2  # delay between stream URL refresh attempts


class ErrorMessages:
    """Centralized error messages (bilingual)"""

    @staticmethod
    def song_added(song_name: str, position: int, cached: bool = False) -> str:
        """Message when song is added to queue"""
        indicator = "⚡" if cached else "🔄"
        return f"{indicator} **{song_name}** ・ *(Vị trí: {position})*"

    @staticmethod
    def playlist_created(name: str) -> str:
        """Message when playlist is created"""
        return f"Đã tạo playlist **{name}** thành công, hãy sử dụng `/use {name}` để kích hoạt."

    @staticmethod
    def playlist_not_found(name: str) -> str:
        """Message when playlist is not found"""
        return f"Playlist '{name}' không tồn tại"

    @staticmethod
    def invalid_position(total_songs: int) -> str:
        """Message for invalid position/index"""
        return f"Số thứ tự không hợp lệ. Playlist có {total_songs} bài hát"

    @staticmethod
    def song_removed(index: int, remaining: int) -> str:
        """Message when song is removed"""
        return f"Đã xóa bài hát #{index}. Còn lại: {remaining} bài hát"

    @staticmethod
    def song_exists_in_playlist(title: str, playlist: str) -> str:
        """Message when song already exists in playlist"""
        return f"**{title}** đã tồn tại trong playlist '{playlist}'"

    @staticmethod
    def song_added_to_playlist(title: str, playlist: str) -> str:
        """Message when song is added to playlist"""
        return f"Đã thêm **{title}** vào playlist '{playlist}'"

    @staticmethod
    def failed_to_process_song(error: str = "") -> str:
        """Message when song processing fails"""
        if error:
            return f"Không thể xử lý bài hát: {error}"
        return "Không thể xử lý bài hát"

    @staticmethod
    def system_error(component: str = "") -> str:
        """Generic system error message"""
        if component:
            return f"Lỗi hệ thống: {component}"
        return "Lỗi hệ thống"

    @staticmethod
    def playlist_switch_in_progress(target: str) -> str:
        """Message when playlist switch is in progress"""
        return f"⚠️ Đang chuyển sang playlist **{target}**, vui lòng chờ..."

    @staticmethod
    def processing_song() -> str:
        """Message when song is being processed"""
        return "🔄 Đang xử lý bài hát..."

    @staticmethod
    def no_audio_player() -> str:
        """Message when audio player is not found"""
        return ErrorMessages.system_error("Không tìm thấy audio player")

    @staticmethod
    def playlist_loaded(name: str, count: int) -> str:
        """Message when playlist is loaded"""
        return f"Playlist **{name}** đã tải {count} bài hát"

    @staticmethod
    def playlist_empty(name: str) -> str:
        """Message when playlist is empty"""
        return f"Playlist **{name}** đang trống. Sử dụng `/add` để thêm bài hát"

    @staticmethod
    def playlist_activated(name: str, message: str = "") -> str:
        """Message when playlist is activated"""
        base = f"**Đã kích hoạt playlist `{name}`**"
        if message:
            return f"{base}\n{message}"
        return base

    @staticmethod
    def cannot_remove_song(playlist: str) -> str:
        """Message when song cannot be removed"""
        return f"Không thể xóa bài hát khỏi playlist '{playlist}'"

    @staticmethod
    def no_current_song() -> str:
        """Message when no song is currently playing"""
        return "Không có bài hát nào đang phát"

    @staticmethod
    def skipped_to_song(song_name: str) -> str:
        """Message when skipped to a song"""
        return f"Đã chuyển sang: **{song_name}**"

    @staticmethod
    def skipped_no_more_songs() -> str:
        """Message when skipped but queue is empty"""
        return "Đã bỏ qua. Không còn bài hát trong hàng đợi."

    @staticmethod
    def cannot_skip() -> str:
        """Message when cannot skip song"""
        return "Không thể bỏ qua bài hát"

    @staticmethod
    def already_paused() -> str:
        """Message when already paused"""
        return "Đang tạm dừng rồi"

    @staticmethod
    def paused_song(song_name: str) -> str:
        """Message when song is paused"""
        return f"Đã tạm dừng: **{song_name}**"

    @staticmethod
    def cannot_pause() -> str:
        """Message when cannot pause"""
        return "Không thể tạm dừng"

    @staticmethod
    def nothing_to_resume() -> str:
        """Message when nothing to resume"""
        return "Không có gì để tiếp tục"

    @staticmethod
    def resumed_song(song_name: str) -> str:
        """Message when song is resumed"""
        return f"Đã tiếp tục: **{song_name}**"

    @staticmethod
    def cannot_resume() -> str:
        """Message when cannot resume"""
        return "Không thể tiếp tục phát"

    @staticmethod
    def stopped_and_cleared() -> str:
        """Message when stopped and cleared queue"""
        return "Đã dừng phát và xóa hàng đợi"

    @staticmethod
    def volume_set(percent: int) -> str:
        """Message when volume is set"""
        return f"Âm lượng đã đặt thành {percent}%"

    @staticmethod
    def cannot_set_volume() -> str:
        """Message when cannot set volume"""
        return "Không thể đặt âm lượng"
