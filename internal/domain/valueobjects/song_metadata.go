package valueobjects

import "fmt"

// SongMetadata contains metadata information about a song
type SongMetadata struct {
	Title     string `json:"title"`
	Artist    string `json:"artist,omitempty"`
	Duration  int    `json:"duration"` // seconds
	Thumbnail string `json:"thumbnail,omitempty"`
	Uploader  string `json:"uploader,omitempty"`
}

// DisplayName returns the best display name for the song
func (m *SongMetadata) DisplayName() string {
	if m.Artist != "" {
		return fmt.Sprintf("%s - %s", m.Artist, m.Title)
	}
	return m.Title
}

// DurationFormatted returns duration in MM:SS format
func (m *SongMetadata) DurationFormatted() string {
	if m.Duration <= 0 {
		return "00:00"
	}

	minutes := m.Duration / 60
	seconds := m.Duration % 60
	return fmt.Sprintf("%02d:%02d", minutes, seconds)
}
