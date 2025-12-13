package entities

import (
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
)

// Song represents a song in the music bot with full lifecycle management
type Song struct {
	// Identity
	ID            string                  `json:"id"`
	OriginalInput string                  `json:"original_input"`
	SourceType    valueobjects.SourceType `json:"source_type"`

	// State
	Status       valueobjects.SongStatus    `json:"status"`
	Metadata     *valueobjects.SongMetadata `json:"metadata,omitempty"`
	StreamURL    string                     `json:"stream_url,omitempty"`
	ErrorMessage string                     `json:"error_message,omitempty"`

	// Timestamps
	CreatedAt          time.Time `json:"created_at"`
	ProcessedAt        time.Time `json:"processed_at,omitempty"`
	StreamURLTimestamp time.Time `json:"stream_url_timestamp,omitempty"`

	// Requester info
	RequestedBy string `json:"requested_by,omitempty"`
	GuildID     string `json:"guild_id,omitempty"`

	mu sync.RWMutex
}

// NewSong creates a new song with PENDING status
func NewSong(originalInput string, sourceType valueobjects.SourceType, requestedBy, guildID string) *Song {
	return &Song{
		ID:            uuid.New().String(),
		OriginalInput: originalInput,
		SourceType:    sourceType,
		Status:        valueobjects.SongStatusPending,
		CreatedAt:     time.Now(),
		RequestedBy:   requestedBy,
		GuildID:       guildID,
	}
}

// IsReady checks if song is ready to play
func (s *Song) IsReady() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.Status == valueobjects.SongStatusReady &&
		s.Metadata != nil &&
		s.StreamURL != ""
}

// DisplayName returns the best display name for the song
func (s *Song) DisplayName() string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.Metadata != nil {
		return s.Metadata.DisplayName()
	}
	return s.OriginalInput
}

// DurationFormatted returns formatted duration
func (s *Song) DurationFormatted() string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.Metadata != nil {
		return s.Metadata.DurationFormatted()
	}
	return "00:00"
}

// MarkProcessing marks the song as being processed
func (s *Song) MarkProcessing() {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.Status = valueobjects.SongStatusProcessing
	s.ProcessedAt = time.Now()
}

// MarkReady marks the song as ready with metadata and stream URL
func (s *Song) MarkReady(metadata *valueobjects.SongMetadata, streamURL string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.Status = valueobjects.SongStatusReady
	s.Metadata = metadata
	s.StreamURL = streamURL
	s.StreamURLTimestamp = time.Now()
	s.ErrorMessage = ""
}

// MarkFailed marks the song as failed with an error message
func (s *Song) MarkFailed(err string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.Status = valueobjects.SongStatusFailed
	s.ErrorMessage = err
}

// RefreshStreamURL updates the stream URL (for expired URLs)
func (s *Song) RefreshStreamURL(newStreamURL string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.StreamURL = newStreamURL
	s.StreamURLTimestamp = time.Now()
}

// IsStreamExpired checks if stream URL is older than threshold
func (s *Song) IsStreamExpired(threshold time.Duration) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.StreamURLTimestamp.IsZero() {
		return false
	}
	return time.Since(s.StreamURLTimestamp) > threshold
}

// GetStreamURL safely returns the stream URL
func (s *Song) GetStreamURL() string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.StreamURL
}

// GetMetadata safely returns a copy of metadata
func (s *Song) GetMetadata() *valueobjects.SongMetadata {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.Metadata == nil {
		return nil
	}

	// Return a copy to prevent external modifications
	metadata := *s.Metadata
	return &metadata
}

// GetStatus safely returns the current status
func (s *Song) GetStatus() valueobjects.SongStatus {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.Status
}
