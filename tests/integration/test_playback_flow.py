"""
Integration tests for complete playback flow
Tests the interaction between PlaybackService, AudioService, and ProcessingService
"""
import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch

from bot.services.playback_service import PlaybackService
from bot.services.audio.audio_service import AudioService
from bot.services.processing_service import ProcessingService
from bot.services.playlist_service import PlaylistService
from bot.services.youtube_service import YouTubeService
from bot.services.stream_refresh import StreamRefreshService
from bot.domain.entities.library import Library
from bot.utils.async_processor import AsyncSongProcessor
from bot.domain.entities.song import Song
from bot.domain.valueobjects.source_type import SourceType
from bot.domain.valueobjects.song_metadata import SongMetadata


@pytest.fixture
def mock_stream_refresh_service():
    """Mock StreamRefreshService"""
    service = Mock(spec=StreamRefreshService)
    service.should_refresh_url = AsyncMock(return_value=False)
    service.refresh_stream_url = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_audio_service(mock_stream_refresh_service):
    """Mock AudioService"""
    service = Mock(spec=AudioService)
    service.get_tracklist = Mock()
    service.get_voice_client = Mock(return_value=None)
    service.is_playing = Mock(return_value=False)
    service.play_next_song = AsyncMock(return_value=True)
    service.get_audio_player = Mock(return_value=None)

    # Mock tracklist
    mock_tracklist = Mock()
    mock_tracklist.add_song = AsyncMock(return_value=1)
    mock_tracklist.current_song = None
    mock_tracklist.queue_size = 0
    mock_tracklist.get_all_songs = Mock(return_value=[])
    mock_tracklist.clear = AsyncMock()
    service.get_tracklist.return_value = mock_tracklist

    return service


@pytest.fixture
def mock_processing_service():
    """Mock ProcessingService"""
    service = Mock(spec=ProcessingService)
    service.process_song = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_playlist_service():
    """Mock PlaylistService"""
    service = Mock(spec=PlaylistService)
    service.get_playlist_content = Mock(return_value=(True, []))
    return service


@pytest.fixture
def mock_youtube_service():
    """Mock YouTubeService"""
    service = Mock(spec=YouTubeService)

    # Create a ready song with metadata
    async def mock_create_song(user_input, requested_by, guild_id):
        metadata = SongMetadata(
            title="Test Song",
            artist="Test Artist",
            duration=180,
            thumbnail_url="https://example.com/thumb.jpg"
        )
        song = Song(
            original_input=user_input,
            source_type=SourceType.YOUTUBE,
            requested_by=requested_by,
            guild_id=guild_id
        )
        song.mark_ready(metadata, "https://stream.url/test")
        return song, False  # (song, was_cached)

    service.create_song = AsyncMock(side_effect=mock_create_song)
    service.get_stats = Mock(return_value={})
    service.cleanup = AsyncMock(return_value=0)
    service.shutdown = AsyncMock()

    return service


@pytest.fixture
def mock_async_processor():
    """Mock AsyncSongProcessor"""
    processor = Mock(spec=AsyncSongProcessor)
    processor.get_available_capacity = Mock(return_value=100)
    return processor


@pytest.fixture
def library():
    """Real Library instance for testing"""
    return Library()


@pytest.fixture
def playback_service(
    mock_audio_service,
    library,
    mock_playlist_service,
    mock_processing_service,
    mock_async_processor,
    mock_youtube_service
):
    """Create PlaybackService with mocked dependencies"""
    return PlaybackService(
        audio_service=mock_audio_service,
        library=library,
        playlist_service=mock_playlist_service,
        processing_service=mock_processing_service,
        async_processor=mock_async_processor,
        youtube_service=mock_youtube_service
    )


@pytest.mark.integration
@pytest.mark.asyncio
class TestPlaybackFlow:
    """Test complete playback flow integration"""

    async def test_play_request_success(self, playback_service, mock_processing_service):
        """Test successful play request flow"""
        # Arrange
        user_input = "https://www.youtube.com/watch?v=test"
        guild_id = 12345
        requested_by = "TestUser"

        # Mock successful processing
        mock_processing_service.process_song = AsyncMock(return_value=True)

        # Act
        success, message, song = await playback_service.play_request(
            user_input, guild_id, requested_by, auto_play=False
        )

        # Assert
        assert success is True
        assert song is not None
        assert song.original_input == user_input
        assert mock_processing_service.process_song.called

    async def test_play_request_cached_flow(self, playback_service, mock_youtube_service):
        """Test play request with caching"""
        # Arrange
        user_input = "test song"
        guild_id = 12345
        requested_by = "TestUser"

        # Act
        success, message, song = await playback_service.play_request_cached(
            user_input, guild_id, requested_by, auto_play=False
        )

        # Assert
        assert success is True
        assert song is not None
        assert mock_youtube_service.create_song.called

    async def test_play_request_processing_failure(self, playback_service, mock_processing_service):
        """Test play request when processing fails"""
        # Arrange
        user_input = "invalid_url"
        guild_id = 12345
        requested_by = "TestUser"

        # Mock failed processing
        mock_processing_service.process_song = AsyncMock(return_value=False)

        # Act
        success, message, song = await playback_service.play_request(
            user_input, guild_id, requested_by, auto_play=False
        )

        # Assert
        assert success is False
        assert song is None

    async def test_skip_current_song(self, playback_service, mock_audio_service):
        """Test skipping current song"""
        # Arrange
        guild_id = 12345

        # Mock current song
        current_song = Mock()
        current_song.display_name = "Current Song"
        mock_tracklist = mock_audio_service.get_tracklist.return_value
        mock_tracklist.current_song = current_song

        # Mock successful skip
        mock_audio_service.skip_current_song = AsyncMock(return_value=True)

        # Act
        success, result = await playback_service.skip_current_song(guild_id)

        # Assert
        assert success is True
        assert mock_audio_service.skip_current_song.called

    async def test_pause_resume_flow(self, playback_service, mock_audio_service):
        """Test pause and resume flow"""
        # Arrange
        guild_id = 12345

        # Mock audio player
        mock_player = Mock()
        mock_player.is_paused = False
        mock_player.pause = Mock(return_value=True)
        mock_player.resume = Mock(return_value=True)
        mock_player.current_song = Mock(display_name="Test Song")
        mock_audio_service.get_audio_player.return_value = mock_player

        # Act - Pause
        success_pause, msg_pause = await playback_service.pause_playback(guild_id)

        # Update state
        mock_player.is_paused = True

        # Act - Resume
        success_resume, msg_resume = await playback_service.resume_playback(guild_id)

        # Assert
        assert success_pause is True
        assert success_resume is True
        assert mock_player.pause.called
        assert mock_player.resume.called

    async def test_stop_playback_clears_queue(self, playback_service, mock_audio_service):
        """Test that stop playback clears the queue"""
        # Arrange
        guild_id = 12345

        # Mock audio player
        mock_player = Mock()
        mock_player.stop = Mock()
        mock_audio_service.get_audio_player.return_value = mock_player

        # Act
        success, message = await playback_service.stop_playback(guild_id)

        # Assert
        assert success is True
        mock_tracklist = mock_audio_service.get_tracklist.return_value
        assert mock_tracklist.clear.called

    async def test_set_volume(self, playback_service, mock_audio_service):
        """Test setting volume"""
        # Arrange
        guild_id = 12345
        volume = 0.75

        # Mock audio player
        mock_player = Mock()
        mock_player.set_volume = Mock(return_value=True)
        mock_audio_service.get_audio_player.return_value = mock_player

        # Act
        success, message = await playback_service.set_volume(guild_id, volume)

        # Assert
        assert success is True
        mock_player.set_volume.assert_called_once_with(volume)

    async def test_volume_clamping(self, playback_service, mock_audio_service):
        """Test that volume is clamped between 0 and 1"""
        # Arrange
        guild_id = 12345

        # Mock audio player
        mock_player = Mock()
        mock_player.set_volume = Mock(return_value=True)
        mock_audio_service.get_audio_player.return_value = mock_player

        # Act - Test upper bound
        await playback_service.set_volume(guild_id, 1.5)
        assert mock_player.set_volume.call_args[0][0] == 1.0

        # Act - Test lower bound
        await playback_service.set_volume(guild_id, -0.5)
        assert mock_player.set_volume.call_args[0][0] == 0.0


@pytest.mark.integration
@pytest.mark.asyncio
class TestPlaylistPlaybackFlow:
    """Test playlist playback integration"""

    async def test_empty_playlist_playback(self, playback_service, mock_playlist_service):
        """Test starting playback with empty playlist"""
        # Arrange
        guild_id = 12345
        playlist_name = "Empty Playlist"

        # Mock empty playlist
        mock_playlist_service.get_playlist_content = Mock(return_value=(True, []))

        # Act
        success = await playback_service.start_playlist_playback(guild_id, playlist_name)

        # Assert
        assert success is True

    async def test_playlist_not_found(self, playback_service, mock_playlist_service):
        """Test starting playback with non-existent playlist"""
        # Arrange
        guild_id = 12345
        playlist_name = "Non-existent"

        # Mock failed playlist load
        mock_playlist_service.get_playlist_content = Mock(return_value=(False, None))

        # Act
        success = await playback_service.start_playlist_playback(guild_id, playlist_name)

        # Assert
        assert success is False

    async def test_get_tracklist_status(self, playback_service, mock_audio_service):
        """Test getting tracklist status"""
        # Arrange
        guild_id = 12345

        # Mock tracklist and audio player
        mock_song = Mock()
        mock_song.display_name = "Current Song"

        mock_tracklist = mock_audio_service.get_tracklist.return_value
        mock_tracklist.current_song = mock_song
        mock_tracklist.get_upcoming = Mock(return_value=[])
        mock_tracklist.position = 0

        mock_player = Mock()
        mock_player.is_playing = True
        mock_player.is_paused = False
        mock_player.volume = 0.5
        mock_audio_service.get_audio_player.return_value = mock_player

        # Act
        status = await playback_service.get_tracklist_status(guild_id)

        # Assert
        assert status is not None
        assert status["current_song"] == mock_song
        assert status["is_playing"] is True
        assert status["is_paused"] is False
        assert status["volume"] == 0.5
