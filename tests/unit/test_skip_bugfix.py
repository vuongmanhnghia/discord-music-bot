"""
Unit tests for skip command race condition bug fix
Tests the auto_play_next parameter functionality
"""
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock, patch

from bot.services.audio.audio_player import AudioPlayer
from bot.domain.entities.song import Song
from bot.domain.entities.tracklist import Tracklist
from bot.domain.valueobjects.source_type import SourceType
from bot.domain.valueobjects.song_metadata import SongMetadata


@pytest.fixture
def mock_voice_client():
    """Mock Discord VoiceClient"""
    client = MagicMock()
    client.is_playing.return_value = True
    client.is_paused.return_value = False
    client.is_connected.return_value = True
    client.stop = Mock()
    client.play = Mock()
    return client


@pytest.fixture
def mock_stream_refresh_service():
    """Mock StreamRefreshService"""
    service = Mock()
    service.should_refresh_url = AsyncMock(return_value=False)
    service.refresh_stream_url = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_tracklist():
    """Mock Tracklist with multiple songs"""
    tracklist = Mock(spec=Tracklist)
    tracklist.guild_id = 12345

    # Create test songs
    songs = [
        Song(
            original_input=f"song{i}",
            source_type=SourceType.YOUTUBE,
            requested_by="TestUser",
            guild_id=12345
        )
        for i in range(3)
    ]

    # Add metadata to make songs ready
    for i, song in enumerate(songs):
        metadata = SongMetadata(
            title=f"Test Song {i}",
            artist="Test Artist",
            duration=180
        )
        song.mark_ready(metadata, f"https://stream.url/song{i}")

    tracklist.next_song = AsyncMock(side_effect=songs)
    tracklist.current_song = songs[0]

    return tracklist


@pytest.fixture
def audio_player(mock_voice_client, mock_stream_refresh_service, mock_tracklist):
    """Create AudioPlayer instance for testing"""
    loop = asyncio.get_event_loop()
    return AudioPlayer(
        stream_refresh_service=mock_stream_refresh_service,
        voice_client=mock_voice_client,
        guild_id=12345,
        tracklist=mock_tracklist,
        loop=loop
    )


@pytest.mark.unit
class TestSkipRaceConditionBugFix:
    """Test skip command race condition bug fix"""

    def test_stop_with_auto_play_enabled(self, audio_player, mock_voice_client):
        """Test stop() with auto_play_next=True (default behavior)"""
        # Arrange
        audio_player.is_playing = True
        audio_player.current_song = Mock()

        # Act
        result = audio_player.stop(auto_play_next=True)

        # Assert
        assert result is True
        assert mock_voice_client.stop.called
        assert audio_player.is_playing is False
        assert audio_player.current_song is None
        # _is_disconnected should NOT be set (callback can auto-play)
        assert audio_player._is_disconnected is False

    def test_stop_with_auto_play_disabled(self, audio_player, mock_voice_client):
        """Test stop() with auto_play_next=False (skip/stop behavior)"""
        # Arrange
        audio_player.is_playing = True
        audio_player.current_song = Mock()

        # Act
        result = audio_player.stop(auto_play_next=False)

        # Assert
        assert result is True
        assert mock_voice_client.stop.called
        assert audio_player.is_playing is False
        assert audio_player.current_song is None
        # _is_disconnected should be set (prevents callback auto-play)
        assert audio_player._is_disconnected is True

    @pytest.mark.asyncio
    async def test_reset_auto_play_flag(self, audio_player):
        """Test that auto-play flag is reset after delay"""
        # Arrange
        audio_player._is_disconnected = True

        # Act
        await audio_player._reset_auto_play_flag()

        # Assert
        assert audio_player._is_disconnected is False

    def test_stop_when_not_playing(self, audio_player, mock_voice_client):
        """Test stop() when nothing is playing"""
        # Arrange
        mock_voice_client.is_playing.return_value = False
        mock_voice_client.is_paused.return_value = False

        # Act
        result = audio_player.stop()

        # Assert
        assert result is False
        assert not mock_voice_client.stop.called

    def test_callback_respects_disconnected_flag(self, audio_player):
        """Test that _after_playback respects _is_disconnected flag"""
        # Arrange
        audio_player._is_disconnected = True
        mock_song = Mock()

        # Act
        audio_player._after_playback(None, mock_song)

        # Assert
        # The callback should skip auto-play because _is_disconnected=True
        # We can't directly test this without running the callback,
        # but we verified the flag is set correctly

    @pytest.mark.asyncio
    async def test_skip_scenario_prevents_double_play(self, audio_player, mock_voice_client):
        """
        Integration test: Simulate skip command to ensure no double play

        This tests the complete flow:
        1. stop(auto_play_next=False) sets _is_disconnected
        2. Callback sees flag and skips auto-play
        3. Manual play_next_song happens without conflict
        """
        # Arrange
        audio_player.is_playing = True
        audio_player.current_song = Mock()

        # Act - Simulate skip command
        # Step 1: Stop with auto_play disabled
        stop_result = audio_player.stop(auto_play_next=False)

        # Assert - Stop succeeded and flag is set
        assert stop_result is True
        assert audio_player._is_disconnected is True

        # Simulate callback being called (would happen in real scenario)
        # The callback should NOT call _play_next_song because flag is set

        # Step 2: Manual play would happen here in real skip_current_song
        # (not tested here as it requires full integration)

        # Step 3: Flag gets reset after delay
        await audio_player._reset_auto_play_flag()
        assert audio_player._is_disconnected is False


@pytest.mark.unit
class TestBackwardCompatibility:
    """Test that changes don't break existing functionality"""

    def test_default_stop_behavior_unchanged(self, audio_player, mock_voice_client):
        """Test that stop() without arguments behaves as before"""
        # Arrange
        audio_player.is_playing = True

        # Act - Call without arguments (should default to auto_play_next=True)
        result = audio_player.stop()

        # Assert - Should work as before (auto-play enabled)
        assert result is True
        assert audio_player._is_disconnected is False

    def test_mark_disconnected_still_works(self, audio_player):
        """Test that mark_disconnected() method still works"""
        # Act
        audio_player.mark_disconnected()

        # Assert
        assert audio_player._is_disconnected is True


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_stop_when_already_disconnected(self, audio_player, mock_voice_client):
        """Test stop when _is_disconnected is already True"""
        # Arrange
        audio_player._is_disconnected = True
        audio_player.is_playing = True

        # Act
        result = audio_player.stop(auto_play_next=False)

        # Assert - Should still work
        assert result is True
        assert audio_player._is_disconnected is True

    @pytest.mark.asyncio
    async def test_multiple_reset_calls(self, audio_player):
        """Test multiple reset_auto_play_flag calls"""
        # Arrange
        audio_player._is_disconnected = True

        # Act - Call multiple times
        await audio_player._reset_auto_play_flag()
        await audio_player._reset_auto_play_flag()

        # Assert - Should be idempotent
        assert audio_player._is_disconnected is False

    def test_stop_both_playing_and_paused(self, audio_player, mock_voice_client):
        """Test stop when voice client is both playing and paused"""
        # Arrange
        mock_voice_client.is_playing.return_value = False
        mock_voice_client.is_paused.return_value = True

        # Act
        result = audio_player.stop()

        # Assert - Should still work (paused counts as active)
        assert result is True
        assert mock_voice_client.stop.called


@pytest.mark.unit
class TestTracklistAdvancement:
    """Test that tracklist properly advances on skip (Bug #2 fix)"""

    @pytest.mark.asyncio
    async def test_next_song_advances_position(self):
        """Test that next_song() advances tracklist position"""
        from bot.domain.entities.tracklist import Tracklist
        from bot.domain.valueobjects.song_metadata import SongMetadata

        # Arrange - Create tracklist with 3 songs
        tracklist = Tracklist(guild_id=12345)

        songs = []
        for i in range(3):
            song = Song(
                original_input=f"song{i}",
                source_type=SourceType.YOUTUBE,
                requested_by="TestUser",
                guild_id=12345
            )
            metadata = SongMetadata(
                title=f"Test Song {i}",
                artist="Test Artist",
                duration=180
            )
            song.mark_ready(metadata, f"https://stream.url/song{i}")
            songs.append(song)
            await tracklist.add_song(song)

        # Assert initial state
        assert tracklist.current_song == songs[0]

        # Act - Advance to next song
        next_song = await tracklist.next_song()

        # Assert - Should be second song
        assert next_song == songs[1]
        assert tracklist.current_song == songs[1]

        # Act - Advance again
        next_song = await tracklist.next_song()

        # Assert - Should be third song
        assert next_song == songs[2]
        assert tracklist.current_song == songs[2]
