package repositories

import "github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"

// PlaylistRepositoryInterface defines the contract for playlist storage
type PlaylistRepositoryInterface interface {
	// List returns all playlist names for a guild
	List(guildID string) ([]string, error)

	// Load loads a playlist by name for a guild
	Load(guildID, name string) (*entities.Playlist, error)

	// Save saves a playlist for a guild
	Save(guildID string, playlist *entities.Playlist) error

	// Delete deletes a playlist by name for a guild
	Delete(guildID, name string) error

	// Exists checks if a playlist exists for a guild
	Exists(guildID, name string) bool
}
