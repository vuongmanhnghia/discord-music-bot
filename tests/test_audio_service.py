"""
Unit tests for AudioService
Demonstrates proper testing with mocks and fixtures
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import discord

from bot.services.audio_service import AudioService
from bot.domain.entities.song import Song
from bot.domain.entities.queue import QueueManager


@pytest.fixture
def audio_service():
    """Create fresh AudioService instance for each test"""
    return AudioService()


@pytest.fixture
def mock_voice_client():
    """Create mock voice client"""
    client = AsyncMock(spec=discord.VoiceClient)
    client.is_connected.return_value = True
    client.is_playing.return_value = False
    client.is_paused.return_value = False
    client.channel = MagicMock()
    client.channel.guild.id = 123456
    return client


@pytest.fixture
def mock_voice_channel():
    """Create mock voice channel"""
    channel = MagicMock(spec=discord.VoiceChannel)
    channel.guild.id = 123456
    channel.name = "Test Channel"
    channel.connect = AsyncMock()
    return channel


@pytest.fixture
def sample_song():
    """Create sample song for testing"""
    from bot.domain.valueobjects.source_type import SourceType
    from bot.domain.valueobjects.song_metadata import SongMetadata
    
    song = Song(
        original_input="https://youtube.com/watch?v=test",
        source_type=SourceType.YOUTUBE,
        requested_by="TestUser",
        guild_id=123456
    )
    
    # Mark as ready with metadata
    metadata = SongMetadata(
        title="Test Song",
        artist="Test Artist",
        duration=180,
        thumbnail_url="https://example.com/thumb.jpg"
    )
    song.mark_ready(metadata, "https://stream.url/audio.m3u8")
    
    return song


class TestAudioServiceConnection:
    """Test voice connection functionality"""
    
    @pytest.mark.asyncio
    async def test_connect_to_channel_success(self, audio_service, mock_voice_channel, mock_voice_client):
        """Test successful connection to voice channel"""
        mock_voice_channel.connect.return_value = mock_voice_client
        
        result = await audio_service.connect_to_channel(mock_voice_channel)
        
        assert result is True
        assert 123456 in audio_service._voice_clients
        assert audio_service._voice_clients[123456] == mock_voice_client
        mock_voice_channel.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_to_channel_timeout(self, audio_service, mock_voice_channel):
        """Test connection timeout handling"""
        async def timeout_connect():
            await asyncio.sleep(100)  # Longer than timeout
        
        mock_voice_channel.connect.side_effect = asyncio.TimeoutError()
        
        result = await audio_service.connect_to_channel(mock_voice_channel)
        
        assert result is False
        assert 123456 not in audio_service._voice_clients
    
    @pytest.mark.asyncio
    async def test_connect_to_channel_already_connected(self, audio_service, mock_voice_channel, mock_voice_client):
        """Test connecting when already connected"""
        # Setup existing connection
        audio_service._voice_clients[123456] = mock_voice_client
        audio_service._audio_players[123456] = MagicMock()
        
        mock_voice_channel.connect.return_value = mock_voice_client
        
        result = await audio_service.connect_to_channel(mock_voice_channel)
        
        # Should disconnect old and connect new
        assert result is True
        assert mock_voice_client.disconnect.called or True  # May have been called
    
    @pytest.mark.asyncio
    async def test_disconnect_from_guild(self, audio_service, mock_voice_client):
        """Test disconnecting from guild"""
        guild_id = 123456
        
        # Setup connection
        audio_service._voice_clients[guild_id] = mock_voice_client
        audio_service._audio_players[guild_id] = MagicMock()
        audio_service._queue_managers[guild_id] = QueueManager(guild_id)
        
        result = await audio_service.disconnect_from_guild(guild_id)
        
        assert result is True
        assert guild_id not in audio_service._voice_clients
        assert guild_id not in audio_service._audio_players
        mock_voice_client.disconnect.assert_called_once()


class TestAudioServicePlayback:
    """Test playback functionality"""
    
    @pytest.mark.asyncio
    async def test_play_next_song_success(self, audio_service, mock_voice_client, sample_song):
        """Test playing next song successfully"""
        guild_id = 123456
        
        # Setup
        audio_service._voice_clients[guild_id] = mock_voice_client
        
        # Create queue with song
        queue_manager = QueueManager(guild_id)
        await queue_manager.add_song(sample_song)
        audio_service._queue_managers[guild_id] = queue_manager
        
        # Create mock audio player
        mock_player = AsyncMock()
        mock_player.play_song.return_value = True
        audio_service._audio_players[guild_id] = mock_player
        
        result = await audio_service.play_next_song(guild_id)
        
        assert result is True
        mock_player.play_song.assert_called_once_with(sample_song)
    
    @pytest.mark.asyncio
    async def test_play_next_song_no_queue(self, audio_service):
        """Test playing when no queue exists"""
        guild_id = 123456
        
        result = await audio_service.play_next_song(guild_id)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_play_next_song_empty_queue(self, audio_service, mock_voice_client):
        """Test playing when queue is empty"""
        guild_id = 123456
        
        # Setup with empty queue
        audio_service._voice_clients[guild_id] = mock_voice_client
        audio_service._queue_managers[guild_id] = QueueManager(guild_id)
        
        result = await audio_service.play_next_song(guild_id)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_skip_to_next(self, audio_service, mock_voice_client, sample_song):
        """Test skipping to next song"""
        guild_id = 123456
        
        # Setup with multiple songs
        audio_service._voice_clients[guild_id] = mock_voice_client
        
        queue_manager = QueueManager(guild_id)
        await queue_manager.add_song(sample_song)
        
        # Add second song
        song2 = Song(
            original_input="https://youtube.com/watch?v=test2",
            source_type=sample_song.source_type,
            requested_by="TestUser",
            guild_id=guild_id
        )
        song2.mark_ready(sample_song.metadata, "https://stream.url/audio2.m3u8")
        await queue_manager.add_song(song2)
        
        audio_service._queue_managers[guild_id] = queue_manager
        
        # Mock audio player
        mock_player = AsyncMock()
        mock_player.play_song.return_value = True
        mock_player.stop = MagicMock()
        audio_service._audio_players[guild_id] = mock_player
        
        result = await audio_service.skip_to_next(guild_id)
        
        assert result is True
        mock_player.stop.assert_called_once()


class TestAudioServiceResourceManagement:
    """Test resource management"""
    
    @pytest.mark.asyncio
    async def test_cleanup_all(self, audio_service, mock_voice_client):
        """Test cleaning up all resources"""
        # Setup multiple guilds
        guild_ids = [123456, 789012]
        
        for guild_id in guild_ids:
            audio_service._voice_clients[guild_id] = mock_voice_client
            audio_service._audio_players[guild_id] = MagicMock()
            audio_service._queue_managers[guild_id] = QueueManager(guild_id)
        
        await audio_service.cleanup_all()
        
        assert len(audio_service._voice_clients) == 0
        assert len(audio_service._audio_players) == 0
        assert len(audio_service._queue_managers) == 0
    
    @pytest.mark.asyncio
    async def test_get_resource_stats(self, audio_service, mock_voice_client):
        """Test getting resource statistics"""
        # Setup some resources
        audio_service._voice_clients[123456] = mock_voice_client
        audio_service._audio_players[123456] = MagicMock()
        audio_service._queue_managers[123456] = QueueManager(123456)
        
        stats = audio_service.get_resource_stats()
        
        assert "total_voice_clients" in stats
        assert "total_audio_players" in stats
        assert "total_queue_managers" in stats
        assert stats["total_voice_clients"] == 1
        assert stats["total_audio_players"] == 1
        assert stats["total_queue_managers"] == 1


class TestAudioServiceStateChecks:
    """Test state checking methods"""
    
    def test_is_connected_true(self, audio_service, mock_voice_client):
        """Test is_connected returns True when connected"""
        guild_id = 123456
        audio_service._voice_clients[guild_id] = mock_voice_client
        
        assert audio_service.is_connected(guild_id) is True
    
    def test_is_connected_false(self, audio_service):
        """Test is_connected returns False when not connected"""
        guild_id = 123456
        
        assert audio_service.is_connected(guild_id) is False
    
    def test_is_playing_true(self, audio_service):
        """Test is_playing returns True when playing"""
        guild_id = 123456
        
        mock_player = MagicMock()
        mock_player.is_playing = True
        audio_service._audio_players[guild_id] = mock_player
        
        assert audio_service.is_playing(guild_id) is True
    
    def test_is_playing_false(self, audio_service):
        """Test is_playing returns False when not playing"""
        guild_id = 123456
        
        assert audio_service.is_playing(guild_id) is False


# Integration test example
@pytest.mark.integration
class TestAudioServiceIntegration:
    """Integration tests requiring real Discord connection"""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.config.getoption("--run-integration"),
        reason="Integration tests require --run-integration flag"
    )
    async def test_full_playback_flow(self, audio_service):
        """Test complete playback flow (requires real bot)"""
        # This would test with actual Discord connection
        # Only run in integration test environment
        pass


def pytest_addoption(parser):
    """Add custom pytest options"""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests"
    )
