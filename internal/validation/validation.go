package validation

import (
	"fmt"
	"net/url"
	"regexp"
	"strings"

	"github.com/vuongmanhnghia/discord-music-bot/internal/errors"
)

var (
	// URL patterns
	youtubePattern    = regexp.MustCompile(`^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$`)
	soundcloudPattern = regexp.MustCompile(`^https?://(www\.)?soundcloud\.com/.+$`)
	spotifyPattern    = regexp.MustCompile(`^https?://open\.spotify\.com/(track|album|playlist)/.+$`)
)

// ValidateURL validates if a string is a valid URL
func ValidateURL(input string) error {
	if input == "" {
		return fmt.Errorf("%w: URL cannot be empty", errors.ErrInvalidURL)
	}

	_, err := url.ParseRequestURI(input)
	if err != nil {
		return fmt.Errorf("%w: %v", errors.ErrInvalidURL, err)
	}

	return nil
}

// IsYouTubeURL checks if URL is a YouTube URL
func IsYouTubeURL(input string) bool {
	return youtubePattern.MatchString(input)
}

// IsSoundCloudURL checks if URL is a SoundCloud URL
func IsSoundCloudURL(input string) bool {
	return soundcloudPattern.MatchString(input)
}

// IsSpotifyURL checks if URL is a Spotify URL
func IsSpotifyURL(input string) bool {
	return spotifyPattern.MatchString(input)
}

// IsSupportedURL checks if URL is from a supported platform
func IsSupportedURL(input string) bool {
	return IsYouTubeURL(input) || IsSoundCloudURL(input) || IsSpotifyURL(input)
}

// ValidateVolume validates volume level (0-100)
func ValidateVolume(volume int) error {
	if volume < 0 || volume > 100 {
		return errors.ErrInvalidVolume
	}
	return nil
}

// ValidateQueuePosition validates queue position
func ValidateQueuePosition(position, maxSize int) error {
	if position < 0 || position >= maxSize {
		return fmt.Errorf("%w: must be between 0 and %d", errors.ErrInvalidPosition, maxSize-1)
	}
	return nil
}

// SanitizeInput sanitizes user input by removing potentially dangerous characters
func SanitizeInput(input string) string {
	// Remove null bytes
	input = strings.ReplaceAll(input, "\x00", "")

	// Trim whitespace
	input = strings.TrimSpace(input)

	return input
}

// ValidatePlaylistName validates playlist name
func ValidatePlaylistName(name string) error {
	name = SanitizeInput(name)

	if name == "" {
		return fmt.Errorf("%w: playlist name cannot be empty", errors.ErrInvalidInput)
	}

	if len(name) > 100 {
		return fmt.Errorf("%w: playlist name too long (max 100 characters)", errors.ErrInvalidInput)
	}

	// Check for invalid characters (only allow alphanumeric, spaces, hyphens, underscores)
	validName := regexp.MustCompile(`^[a-zA-Z0-9\s\-_]+$`)
	if !validName.MatchString(name) {
		return fmt.Errorf("%w: playlist name contains invalid characters", errors.ErrInvalidInput)
	}

	return nil
}

// TruncateString safely truncates a string to max length
func TruncateString(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}

	// Try to truncate at word boundary
	if maxLen > 3 {
		s = s[:maxLen-3]
		if idx := strings.LastIndexAny(s, " \t\n"); idx > 0 {
			s = s[:idx]
		}
		return s + "..."
	}

	return s[:maxLen]
}
