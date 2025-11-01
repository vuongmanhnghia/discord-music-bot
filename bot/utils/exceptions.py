"""
Custom exception hierarchy for the music bot
Provides structured error handling with specific exception types
"""


class MusicBotException(Exception):
    """Base exception for all music bot errors"""

    def __init__(self, message: str, details: str = None):
        self.message = message
        self.details = details
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


# Voice Connection Errors
class VoiceConnectionError(MusicBotException):
    """Base class for voice connection related errors"""
    pass


class VoiceChannelNotFoundError(VoiceConnectionError):
    """Raised when voice channel is not found"""
    pass


class VoiceConnectionTimeoutError(VoiceConnectionError):
    """Raised when voice connection times out"""
    pass


class VoiceAlreadyConnectedError(VoiceConnectionError):
    """Raised when already connected to a voice channel"""
    pass


# Playback Errors
class PlaybackError(MusicBotException):
    """Base class for playback related errors"""
    pass


class NoAudioPlayerError(PlaybackError):
    """Raised when no audio player is available"""
    pass


class SongProcessingError(PlaybackError):
    """Raised when song processing fails"""
    pass


class StreamURLError(PlaybackError):
    """Raised when stream URL retrieval fails"""
    pass


class EmptyQueueError(PlaybackError):
    """Raised when queue is empty"""
    pass


# Playlist Errors
class PlaylistError(MusicBotException):
    """Base class for playlist related errors"""
    pass


class PlaylistNotFoundError(PlaylistError):
    """Raised when playlist is not found"""
    pass


class PlaylistAlreadyExistsError(PlaylistError):
    """Raised when trying to create a playlist that already exists"""
    pass


class PlaylistEmptyError(PlaylistError):
    """Raised when playlist is empty"""
    pass


class InvalidPlaylistFormatError(PlaylistError):
    """Raised when playlist format is invalid"""
    pass


# Song Errors
class SongError(MusicBotException):
    """Base class for song related errors"""
    pass


class InvalidSongURLError(SongError):
    """Raised when song URL is invalid"""
    pass


class SongNotReadyError(SongError):
    """Raised when attempting to play a song that is not ready"""
    pass


class SongDownloadError(SongError):
    """Raised when song download fails"""
    pass


# Queue Errors
class QueueError(MusicBotException):
    """Base class for queue related errors"""
    pass


class QueueFullError(QueueError):
    """Raised when queue is full"""
    pass


class QueueIndexError(QueueError):
    """Raised when queue index is out of bounds"""
    pass


# Permission Errors
class PermissionError(MusicBotException):
    """Base class for permission related errors"""
    pass


class UserNotInVoiceChannelError(PermissionError):
    """Raised when user is not in a voice channel"""
    pass


class BotNotInVoiceChannelError(PermissionError):
    """Raised when bot is not in a voice channel"""
    pass


class DifferentVoiceChannelError(PermissionError):
    """Raised when user and bot are in different voice channels"""
    pass


# Configuration Errors
class ConfigurationError(MusicBotException):
    """Base class for configuration related errors"""
    pass


class MissingEnvironmentVariableError(ConfigurationError):
    """Raised when required environment variable is missing"""
    pass


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration is invalid"""
    pass
