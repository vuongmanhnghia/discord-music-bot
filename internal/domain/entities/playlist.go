package entities

import (
	"encoding/json"
	"time"

	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
)

// FlexTime is a time.Time that can parse multiple formats
type FlexTime struct {
	time.Time
}

// UnmarshalJSON handles multiple time formats (Python and Go)
func (ft *FlexTime) UnmarshalJSON(b []byte) error {
	var s string
	if err := json.Unmarshal(b, &s); err != nil {
		return err
	}

	// Try different formats
	formats := []string{
		time.RFC3339,                 // Standard Go format
		time.RFC3339Nano,             // Go with nanoseconds
		"2006-01-02T15:04:05.999999", // Python datetime without timezone
		"2006-01-02T15:04:05",        // Python datetime without microseconds
		"2006-01-02 15:04:05.999999", // Alternative format
		"2006-01-02 15:04:05",        // Simple datetime
	}

	for _, format := range formats {
		if t, err := time.Parse(format, s); err == nil {
			ft.Time = t
			return nil
		}
	}

	// Fallback to current time if all parsing fails
	ft.Time = time.Now()
	return nil
}

// MarshalJSON outputs in RFC3339 format
func (ft FlexTime) MarshalJSON() ([]byte, error) {
	return json.Marshal(ft.Time.Format(time.RFC3339))
}

// PlaylistEntry represents a single entry in a playlist
type PlaylistEntry struct {
	OriginalInput string                  `json:"original_input"`
	SourceType    valueobjects.SourceType `json:"source_type"`
	Title         string                  `json:"title,omitempty"`
	AddedAt       FlexTime                `json:"added_at"`
}

// Playlist represents a saved collection of songs
type Playlist struct {
	Name      string           `json:"name"`
	Entries   []*PlaylistEntry `json:"entries"`
	CreatedAt FlexTime         `json:"created_at,omitempty"`
	UpdatedAt FlexTime         `json:"updated_at,omitempty"`
}

// NewPlaylist creates a new empty playlist
func NewPlaylist(name string) *Playlist {
	now := FlexTime{time.Now()}
	return &Playlist{
		Name:      name,
		Entries:   make([]*PlaylistEntry, 0),
		CreatedAt: now,
		UpdatedAt: now,
	}
}

// AddEntry adds a new entry to the playlist
func (p *Playlist) AddEntry(originalInput string, sourceType valueobjects.SourceType, title string) {
	entry := &PlaylistEntry{
		OriginalInput: originalInput,
		SourceType:    sourceType,
		Title:         title,
		AddedAt:       FlexTime{time.Now()},
	}
	p.Entries = append(p.Entries, entry)
	p.UpdatedAt = FlexTime{time.Now()}
}

// RemoveEntry removes an entry by original input
func (p *Playlist) RemoveEntry(originalInput string) bool {
	for i, entry := range p.Entries {
		if entry.OriginalInput == originalInput {
			p.Entries = append(p.Entries[:i], p.Entries[i+1:]...)
			p.UpdatedAt = FlexTime{time.Now()}
			return true
		}
	}
	return false
}

// HasEntry checks if an entry exists
func (p *Playlist) HasEntry(originalInput string) bool {
	for _, entry := range p.Entries {
		if entry.OriginalInput == originalInput {
			return true
		}
	}
	return false
}

// TotalSongs returns the number of songs in the playlist
func (p *Playlist) TotalSongs() int {
	return len(p.Entries)
}
