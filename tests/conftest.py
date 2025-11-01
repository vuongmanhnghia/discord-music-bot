"""
Pytest configuration and shared fixtures
"""
import pytest
import asyncio
from unittest.mock import Mock, MagicMock
from typing import AsyncGenerator

# Import domain entities for testing
from bot.domain.entities.song import Song
from bot.domain.entities.tracklist import Tracklist
from bot.domain.valueobjects.source_type import SourceType
from bot.domain.valueobjects.song_status import SongStatus
from bot.domain.valueobjects.song_metadata import SongMetadata


@pytest.fixture
def event_loop():
    """Create an event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_song() -> Song:
    """Create a mock Song entity"""
    return Song(
        original_input="https://www.youtube.com/watch?v=test",
        source_type=SourceType.YOUTUBE,
        requested_by="TestUser",
        guild_id=12345,
    )


@pytest.fixture
def mock_ready_song() -> Song:
    """Create a ready Song entity with metadata"""
    metadata = SongMetadata(
        title="Test Song",
        artist="Test Artist",
        duration=180,
        thumbnail_url="https://example.com/thumb.jpg",
    )

    song = Song(
        original_input="https://www.youtube.com/watch?v=test",
        source_type=SourceType.YOUTUBE,
        requested_by="TestUser",
        guild_id=12345,
    )

    song.mark_ready(metadata, "https://stream.url/test")
    return song


@pytest.fixture
def mock_failed_song() -> Song:
    """Create a failed Song entity"""
    song = Song(
        original_input="invalid_url",
        source_type=SourceType.YOUTUBE,
        requested_by="TestUser",
        guild_id=12345,
    )

    song.mark_failed("Failed to extract video info")
    return song


@pytest.fixture
def mock_tracklist() -> Tracklist:
    """Create a mock Tracklist"""
    return Tracklist(guild_id=12345)


@pytest.fixture
def mock_discord_voice_client():
    """Create a mock Discord VoiceClient"""
    mock_client = MagicMock()
    mock_client.is_connected.return_value = True
    mock_client.is_playing.return_value = False
    mock_client.is_paused.return_value = False
    mock_client.guild.id = 12345
    mock_client.channel.id = 67890
    mock_client.channel.name = "Test Voice Channel"
    return mock_client


@pytest.fixture
def mock_discord_interaction():
    """Create a mock Discord Interaction"""
    mock_interaction = MagicMock()
    mock_interaction.user.id = 99999
    mock_interaction.user.name = "TestUser"
    mock_interaction.guild.id = 12345
    mock_interaction.guild.name = "Test Guild"

    # Mock voice state
    mock_interaction.user.voice = MagicMock()
    mock_interaction.user.voice.channel = MagicMock()
    mock_interaction.user.voice.channel.id = 67890
    mock_interaction.user.voice.channel.name = "Test Voice Channel"

    # Mock response
    mock_interaction.response.send_message = MagicMock()
    mock_interaction.followup.send = MagicMock()

    return mock_interaction


@pytest.fixture
def sample_song_metadata() -> dict:
    """Sample YouTube metadata for testing"""
    return {
        "id": "test_video_id",
        "title": "Test Song Title",
        "uploader": "Test Artist",
        "duration": 180,
        "thumbnail": "https://example.com/thumb.jpg",
        "url": "https://www.youtube.com/watch?v=test",
        "formats": [
            {
                "url": "https://stream.url/test",
                "acodec": "opus",
                "quality": "audio",
            }
        ],
    }


@pytest.fixture
def sample_playlist_data() -> list:
    """Sample playlist data for testing"""
    return [
        {
            "original_input": "https://www.youtube.com/watch?v=song1",
            "title": "Song 1",
        },
        {
            "original_input": "https://www.youtube.com/watch?v=song2",
            "title": "Song 2",
        },
        {
            "original_input": "https://www.youtube.com/watch?v=song3",
            "title": "Song 3",
        },
    ]
