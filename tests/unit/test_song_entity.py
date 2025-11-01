"""
Unit tests for Song entity
Tests song lifecycle, state transitions, and business logic
"""
import pytest
from datetime import datetime

from bot.domain.entities.song import Song
from bot.domain.valueobjects.source_type import SourceType
from bot.domain.valueobjects.song_status import SongStatus
from bot.domain.valueobjects.song_metadata import SongMetadata


class TestSongCreation:
    """Test song creation and initialization"""

    def test_create_song_minimal(self):
        """Test creating song with minimal required fields"""
        song = Song(
            original_input="https://www.youtube.com/watch?v=test",
            source_type=SourceType.YOUTUBE,
        )

        assert song.original_input == "https://www.youtube.com/watch?v=test"
        assert song.source_type == SourceType.YOUTUBE
        assert song.status == SongStatus.PENDING
        assert song.metadata is None
        assert song.stream_url is None
        assert song.id is not None  # UUID should be generated

    def test_create_song_with_requester(self):
        """Test creating song with requester info"""
        song = Song(
            original_input="test song",
            source_type=SourceType.YOUTUBE,
            requested_by="TestUser",
            guild_id=12345,
        )

        assert song.requested_by == "TestUser"
        assert song.guild_id == 12345

    def test_song_has_unique_id(self):
        """Test that each song gets a unique ID"""
        song1 = Song(original_input="test1", source_type=SourceType.YOUTUBE)
        song2 = Song(original_input="test2", source_type=SourceType.YOUTUBE)

        assert song1.id != song2.id

    def test_song_creation_timestamp(self):
        """Test that song has creation timestamp"""
        before = datetime.now()
        song = Song(original_input="test", source_type=SourceType.YOUTUBE)
        after = datetime.now()

        assert before <= song.created_at <= after


class TestSongStateTransitions:
    """Test song state machine transitions"""

    def test_mark_processing(self, mock_song):
        """Test transitioning song to processing state"""
        before = datetime.now()
        mock_song.mark_processing()
        after = datetime.now()

        assert mock_song.status == SongStatus.PROCESSING
        assert mock_song.processed_at is not None
        assert before <= mock_song.processed_at <= after

    def test_mark_ready(self, mock_song):
        """Test transitioning song to ready state"""
        metadata = SongMetadata(
            title="Test Song",
            artist="Test Artist",
            duration=180,
            thumbnail_url="https://example.com/thumb.jpg",
        )
        stream_url = "https://stream.url/test"

        mock_song.mark_ready(metadata, stream_url)

        assert mock_song.status == SongStatus.READY
        assert mock_song.metadata == metadata
        assert mock_song.stream_url == stream_url
        assert mock_song.error_message is None

    def test_mark_failed(self, mock_song):
        """Test transitioning song to failed state"""
        error_msg = "Failed to extract video info"
        before = datetime.now()

        mock_song.mark_failed(error_msg)
        after = datetime.now()

        assert mock_song.status == SongStatus.FAILED
        assert mock_song.error_message == error_msg
        assert mock_song.processed_at is not None
        assert before <= mock_song.processed_at <= after


class TestSongProperties:
    """Test song computed properties"""

    def test_is_ready_when_not_ready(self, mock_song):
        """Test is_ready returns False for pending song"""
        assert not mock_song.is_ready

    def test_is_ready_when_processing(self, mock_song):
        """Test is_ready returns False for processing song"""
        mock_song.mark_processing()
        assert not mock_song.is_ready

    def test_is_ready_when_failed(self, mock_song):
        """Test is_ready returns False for failed song"""
        mock_song.mark_failed("Error")
        assert not mock_song.is_ready

    def test_is_ready_when_ready(self, mock_ready_song):
        """Test is_ready returns True for ready song"""
        assert mock_ready_song.is_ready

    def test_display_name_without_metadata(self, mock_song):
        """Test display name falls back to original input"""
        assert mock_song.display_name == mock_song.original_input

    def test_display_name_with_metadata(self, mock_ready_song):
        """Test display name uses metadata when available"""
        assert mock_ready_song.display_name == "Test Song - Test Artist"

    def test_duration_formatted_without_metadata(self, mock_song):
        """Test formatted duration without metadata"""
        assert mock_song.duration_formatted == "00:00"

    def test_duration_formatted_with_metadata(self, mock_ready_song):
        """Test formatted duration with metadata"""
        # 180 seconds = 3:00
        assert mock_ready_song.duration_formatted == "3:00"


class TestSongSerialization:
    """Test song serialization to dict"""

    def test_to_dict_basic_song(self, mock_song):
        """Test serializing basic song to dict"""
        song_dict = mock_song.to_dict()

        assert song_dict["id"] == mock_song.id
        assert song_dict["original_input"] == mock_song.original_input
        assert song_dict["source_type"] == SourceType.YOUTUBE.value
        assert song_dict["status"] == SongStatus.PENDING.value
        assert song_dict["metadata"] is None
        assert song_dict["stream_url"] is None
        assert song_dict["requested_by"] == "TestUser"
        assert song_dict["guild_id"] == 12345

    def test_to_dict_ready_song(self, mock_ready_song):
        """Test serializing ready song with metadata to dict"""
        song_dict = mock_ready_song.to_dict()

        assert song_dict["status"] == SongStatus.READY.value
        assert song_dict["metadata"] is not None
        assert song_dict["metadata"]["title"] == "Test Song"
        assert song_dict["metadata"]["artist"] == "Test Artist"
        assert song_dict["metadata"]["duration"] == 180
        assert song_dict["stream_url"] == "https://stream.url/test"

    def test_to_dict_failed_song(self, mock_failed_song):
        """Test serializing failed song to dict"""
        song_dict = mock_failed_song.to_dict()

        assert song_dict["status"] == SongStatus.FAILED.value
        assert song_dict["error_message"] == "Failed to extract video info"


@pytest.mark.unit
class TestSongEdgeCases:
    """Test edge cases and error conditions"""

    def test_mark_ready_clears_error(self, mock_song):
        """Test that marking ready clears previous errors"""
        mock_song.mark_failed("Some error")
        assert mock_song.error_message == "Some error"

        metadata = SongMetadata(
            title="Test", artist="Artist", duration=100
        )
        mock_song.mark_ready(metadata, "https://stream")

        assert mock_song.error_message is None
        assert mock_song.status == SongStatus.READY

    def test_multiple_state_transitions(self, mock_song):
        """Test multiple state transitions"""
        # Pending -> Processing
        mock_song.mark_processing()
        assert mock_song.status == SongStatus.PROCESSING

        # Processing -> Ready
        metadata = SongMetadata(title="Test", artist="Artist", duration=100)
        mock_song.mark_ready(metadata, "https://stream")
        assert mock_song.status == SongStatus.READY

    def test_failed_after_processing(self, mock_song):
        """Test can fail after starting processing"""
        mock_song.mark_processing()
        mock_song.mark_failed("Network error")

        assert mock_song.status == SongStatus.FAILED
        assert mock_song.error_message == "Network error"
