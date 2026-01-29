package errors

import (
	"errors"
	"fmt"
)

// Common error types for better error handling
var (
	// Playback errors
	ErrNotPlaying        = errors.New("no song is currently playing")
	ErrAlreadyPlaying    = errors.New("already playing")
	ErrPlayerNotFound    = errors.New("audio player not found")
	ErrNoVoiceConnection = errors.New("not connected to voice channel")

	// Queue errors
	ErrQueueEmpty      = errors.New("queue is empty")
	ErrQueueFull       = errors.New("queue is full")
	ErrInvalidPosition = errors.New("invalid queue position")

	// Playlist errors
	ErrPlaylistNotFound = errors.New("playlist not found")
	ErrPlaylistExists   = errors.New("playlist already exists")
	ErrSongNotFound     = errors.New("song not found")

	// Permission errors
	ErrNotInVoiceChannel = errors.New("you must be in a voice channel")
	ErrDifferentChannel  = errors.New("you must be in the same voice channel as the bot")
	ErrNoPermission      = errors.New("insufficient permissions")

	// Processing errors
	ErrProcessingFailed = errors.New("failed to process song")
	ErrServiceStopped   = errors.New("service is stopped")
	ErrTimeout          = errors.New("operation timed out")

	// Validation errors
	ErrInvalidInput  = errors.New("invalid input")
	ErrInvalidURL    = errors.New("invalid URL")
	ErrInvalidVolume = errors.New("volume must be between 0 and 100")
)

// UserError wraps an error with a user-friendly message
type UserError struct {
	Err     error
	Message string
}

func (e *UserError) Error() string {
	return e.Err.Error()
}

func (e *UserError) Unwrap() error {
	return e.Err
}

func (e *UserError) UserMessage() string {
	return e.Message
}

// NewUserError creates a new user error
func NewUserError(err error, message string) *UserError {
	return &UserError{
		Err:     err,
		Message: message,
	}
}

// WrapUserError wraps an error with a user-friendly message
func WrapUserError(err error, format string, args ...interface{}) *UserError {
	return &UserError{
		Err:     err,
		Message: fmt.Sprintf(format, args...),
	}
}

// GetUserMessage extracts user-friendly message from error
func GetUserMessage(err error) string {
	var userErr *UserError
	if errors.As(err, &userErr) {
		return userErr.UserMessage()
	}

	// Map common errors to user-friendly messages
	switch {
	case errors.Is(err, ErrNotPlaying):
		return "❌ Nothing is playing right now"
	case errors.Is(err, ErrAlreadyPlaying):
		return "⚠️ Already playing. Use `/pause` to pause or `/skip` to skip"
	case errors.Is(err, ErrQueueEmpty):
		return "📋 Queue is empty. Use `/play` to add songs"
	case errors.Is(err, ErrQueueFull):
		return "⚠️ Queue is full. Please wait or clear the queue"
	case errors.Is(err, ErrNotInVoiceChannel):
		return "🔊 You need to join a voice channel first"
	case errors.Is(err, ErrDifferentChannel):
		return "⚠️ You must be in the same voice channel as the bot"
	case errors.Is(err, ErrPlaylistNotFound):
		return "📋 Playlist not found"
	case errors.Is(err, ErrInvalidURL):
		return "🔗 Invalid URL. Please provide a valid YouTube or SoundCloud link"
	case errors.Is(err, ErrInvalidVolume):
		return "🔊 Volume must be between 0 and 100"
	case errors.Is(err, ErrTimeout):
		return "⏱️ Operation timed out. Please try again"
	default:
		return "❌ An error occurred. Please try again later"
	}
}
