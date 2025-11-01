"""
Unit tests for Tracklist entity
Tests queue management and playback control
"""
import pytest

from bot.domain.entities.tracklist import Tracklist
from bot.domain.entities.song import Song
from bot.domain.valueobjects.source_type import SourceType


class TestTracklistCreation:
    """Test tracklist initialization"""

    def test_create_empty_tracklist(self):
        """Test creating empty tracklist"""
        tracklist = Tracklist(guild_id=12345)

        assert tracklist.guild_id == 12345
        assert tracklist.queue_size == 0
        assert tracklist.current_song is None
        assert tracklist.position == 0

    def test_tracklist_has_default_repeat_mode(self, mock_tracklist):
        """Test tracklist initializes with default repeat mode"""
        assert mock_tracklist.repeat_mode == "off"


@pytest.mark.asyncio
class TestAddingSongs:
    """Test adding songs to tracklist"""

    async def test_add_single_song(self, mock_tracklist, mock_ready_song):
        """Test adding a single song"""
        position = await mock_tracklist.add_song(mock_ready_song)

        assert position == 1
        assert mock_tracklist.queue_size == 1
        assert mock_tracklist.current_song == mock_ready_song

    async def test_add_multiple_songs(self, mock_tracklist):
        """Test adding multiple songs"""
        songs = [
            Song(original_input=f"song{i}", source_type=SourceType.YOUTUBE)
            for i in range(3)
        ]

        positions = []
        for song in songs:
            pos = await mock_tracklist.add_song(song)
            positions.append(pos)

        assert positions == [1, 2, 3]
        assert mock_tracklist.queue_size == 3

    async def test_first_song_becomes_current(self, mock_tracklist, mock_ready_song):
        """Test first song becomes current song"""
        await mock_tracklist.add_song(mock_ready_song)

        assert mock_tracklist.current_song == mock_ready_song
        assert mock_tracklist.position == 0


@pytest.mark.asyncio
class TestTracklistNavigation:
    """Test navigation through tracklist"""

    async def test_get_upcoming_songs(self, mock_tracklist):
        """Test getting upcoming songs"""
        songs = [
            Song(original_input=f"song{i}", source_type=SourceType.YOUTUBE)
            for i in range(5)
        ]

        for song in songs:
            await mock_tracklist.add_song(song)

        upcoming = mock_tracklist.get_upcoming(3)

        assert len(upcoming) == 3
        assert upcoming[0] == songs[1]
        assert upcoming[1] == songs[2]
        assert upcoming[2] == songs[3]

    async def test_get_all_songs(self, mock_tracklist):
        """Test getting all songs"""
        songs = [
            Song(original_input=f"song{i}", source_type=SourceType.YOUTUBE)
            for i in range(3)
        ]

        for song in songs:
            await mock_tracklist.add_song(song)

        all_songs = mock_tracklist.get_all_songs()

        assert len(all_songs) == 3
        assert all_songs == songs


@pytest.mark.asyncio
class TestTracklistClear:
    """Test clearing tracklist"""

    async def test_clear_empty_tracklist(self, mock_tracklist):
        """Test clearing empty tracklist"""
        await mock_tracklist.clear()

        assert mock_tracklist.queue_size == 0
        assert mock_tracklist.current_song is None

    async def test_clear_populated_tracklist(self, mock_tracklist):
        """Test clearing tracklist with songs"""
        songs = [
            Song(original_input=f"song{i}", source_type=SourceType.YOUTUBE)
            for i in range(3)
        ]

        for song in songs:
            await mock_tracklist.add_song(song)

        await mock_tracklist.clear()

        assert mock_tracklist.queue_size == 0
        assert mock_tracklist.current_song is None
        assert mock_tracklist.position == 0


@pytest.mark.asyncio
class TestRepeatMode:
    """Test repeat mode functionality"""

    async def test_set_repeat_mode_off(self, mock_tracklist):
        """Test setting repeat mode to off"""
        result = mock_tracklist.set_repeat_mode("off")

        assert result is True
        assert mock_tracklist.repeat_mode == "off"

    async def test_set_repeat_mode_track(self, mock_tracklist):
        """Test setting repeat mode to track"""
        result = mock_tracklist.set_repeat_mode("track")

        assert result is True
        assert mock_tracklist.repeat_mode == "track"

    async def test_set_repeat_mode_queue(self, mock_tracklist):
        """Test setting repeat mode to queue"""
        result = mock_tracklist.set_repeat_mode("queue")

        assert result is True
        assert mock_tracklist.repeat_mode == "queue"

    async def test_set_invalid_repeat_mode(self, mock_tracklist):
        """Test setting invalid repeat mode"""
        result = mock_tracklist.set_repeat_mode("invalid")

        assert result is False
        assert mock_tracklist.repeat_mode == "off"  # Should remain unchanged


@pytest.mark.unit
class TestTracklistEdgeCases:
    """Test edge cases"""

    @pytest.mark.asyncio
    async def test_add_none_song(self, mock_tracklist):
        """Test adding None as song"""
        with pytest.raises((AttributeError, TypeError)):
            await mock_tracklist.add_song(None)

    def test_get_upcoming_with_empty_queue(self, mock_tracklist):
        """Test getting upcoming from empty queue"""
        upcoming = mock_tracklist.get_upcoming(5)

        assert upcoming == []

    def test_get_upcoming_more_than_available(self, mock_tracklist):
        """Test requesting more upcoming songs than available"""
        # This test would need async, implement if tracklist supports it
        pass
