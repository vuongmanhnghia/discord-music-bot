package repositories

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/vuongmanhnghia/discord-music-bot/internal/database"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
)

// DatabasePlaylistRepository implements PlaylistRepositoryInterface using PostgreSQL
type DatabasePlaylistRepository struct {
	db *database.DB
}

// NewDatabasePlaylistRepository creates a new database-backed playlist repository
func NewDatabasePlaylistRepository(db *database.DB) *DatabasePlaylistRepository {
	return &DatabasePlaylistRepository{
		db: db,
	}
}

// toGuildIDPtr converts empty string to nil pointer
func toGuildIDPtr(guildID string) *string {
	if guildID == "" {
		return nil
	}
	return &guildID
}

// List returns all playlist names for a guild
func (r *DatabasePlaylistRepository) List(guildID string) ([]string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	playlists, err := r.db.Queries.ListPlaylistsByGuild(ctx, toGuildIDPtr(guildID))
	if err != nil {
		return nil, fmt.Errorf("failed to list playlists: %w", err)
	}

	names := make([]string, 0, len(playlists))
	for _, p := range playlists {
		names = append(names, p.Name)
	}

	return names, nil
}

// Load loads a playlist by name for a guild
func (r *DatabasePlaylistRepository) Load(guildID, name string) (*entities.Playlist, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// Get playlist by name and guild
	dbPlaylist, err := r.db.Queries.GetPlaylistByNameAndGuild(ctx, database.GetPlaylistByNameAndGuildParams{
		Name:    name,
		GuildID: toGuildIDPtr(guildID),
	})
	if err != nil {
		return nil, nil // Playlist doesn't exist
	}

	// Get playlist entries
	dbEntries, err := r.db.Queries.ListPlaylistEntries(ctx, dbPlaylist.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to load playlist entries: %w", err)
	}

	// Convert to domain entity
	playlist := &entities.Playlist{
		Name:      dbPlaylist.Name,
		Entries:   make([]*entities.PlaylistEntry, 0, len(dbEntries)),
		CreatedAt: entities.FlexTime{Time: dbPlaylist.CreatedAt},
		UpdatedAt: entities.FlexTime{Time: dbPlaylist.UpdatedAt},
	}

	for _, entry := range dbEntries {
		title := ""
		if entry.Title != nil {
			title = *entry.Title
		}
		playlist.Entries = append(playlist.Entries, &entities.PlaylistEntry{
			OriginalInput: entry.OriginalInput,
			SourceType:    valueobjects.SourceType(entry.SourceType),
			Title:         title,
			AddedAt:       entities.FlexTime{Time: entry.AddedAt},
		})
	}

	return playlist, nil
}

// Save saves a playlist for a guild
func (r *DatabasePlaylistRepository) Save(guildID string, playlist *entities.Playlist) error {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// Start a transaction
	tx, err := r.db.Pool.Begin(ctx)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback(ctx)

	queries := r.db.Queries.WithTx(tx)

	// Convert empty guildID to nil for global playlists
	guildIDPtr := toGuildIDPtr(guildID)

	// Ensure guild exists first (upsert) - only for non-global playlists
	if guildID != "" {
		_, err := queries.UpsertGuild(ctx, database.UpsertGuildParams{
			ID:   guildID,
			Name: nil, // We don't have guild name here, allow NULL
		})
		if err != nil {
			return fmt.Errorf("failed to upsert guild: %w", err)
		}
	}

	// Try to get existing playlist
	dbPlaylist, err := queries.GetPlaylistByNameAndGuild(ctx, database.GetPlaylistByNameAndGuildParams{
		Name:    playlist.Name,
		GuildID: guildIDPtr,
	})

	var playlistID uuid.UUID
	if err != nil || dbPlaylist == nil {
		// Create new playlist
		newPlaylist, err := queries.CreatePlaylist(ctx, database.CreatePlaylistParams{
			Name:    playlist.Name,
			GuildID: guildIDPtr,
		})
		if err != nil {
			return fmt.Errorf("failed to create playlist: %w", err)
		}
		playlistID = newPlaylist.ID
	} else {
		playlistID = dbPlaylist.ID
		// Update existing playlist timestamp
		if err := queries.UpdatePlaylistName(ctx, database.UpdatePlaylistNameParams{
			ID:   playlistID,
			Name: playlist.Name,
		}); err != nil {
			return fmt.Errorf("failed to update playlist: %w", err)
		}
	}

	// Delete existing entries and re-add
	if err := queries.DeletePlaylistEntriesByPlaylistID(ctx, playlistID); err != nil {
		return fmt.Errorf("failed to clear playlist entries: %w", err)
	}

	// Add entries
	for _, entry := range playlist.Entries {
		title := entry.Title
		_, err := queries.AddPlaylistEntry(ctx, database.AddPlaylistEntryParams{
			PlaylistID:    playlistID,
			OriginalInput: entry.OriginalInput,
			SourceType:    string(entry.SourceType),
			Title:         &title,
		})
		if err != nil {
			return fmt.Errorf("failed to add playlist entry: %w", err)
		}
	}

	if err := tx.Commit(ctx); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	return nil
}

// Delete deletes a playlist by name for a guild
func (r *DatabasePlaylistRepository) Delete(guildID, name string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	err := r.db.Queries.DeletePlaylistByName(ctx, database.DeletePlaylistByNameParams{
		Name:    name,
		GuildID: toGuildIDPtr(guildID),
	})
	if err != nil {
		return fmt.Errorf("failed to delete playlist: %w", err)
	}

	return nil
}

// Exists checks if a playlist exists for a guild
func (r *DatabasePlaylistRepository) Exists(guildID, name string) bool {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	exists, err := r.db.Queries.PlaylistExists(ctx, database.PlaylistExistsParams{
		Name:    name,
		GuildID: toGuildIDPtr(guildID),
	})
	if err != nil {
		return false
	}

	return exists
}
