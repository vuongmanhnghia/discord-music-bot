package services

import (
	"fmt"

	"github.com/vuongmanhnghia/discord-music-bot/internal/database"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/repositories"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
	"github.com/vuongmanhnghia/discord-music-bot/pkg/logger"
)

// PlaylistService manages playlist operations
type PlaylistService struct {
	repo        repositories.PlaylistRepositoryInterface
	fileRepo    *repositories.PlaylistRepository // Legacy file-based repo
	useDatabase bool
	logger      *logger.Logger
}

// NewPlaylistService creates a new playlist service with file-based storage
func NewPlaylistService(playlistDir string, log *logger.Logger) *PlaylistService {
	fileRepo := repositories.NewPlaylistRepository(playlistDir)
	return &PlaylistService{
		repo:        &fileRepoAdapter{repo: fileRepo},
		fileRepo:    fileRepo,
		useDatabase: false,
		logger:      log,
	}
}

// NewPlaylistServiceWithDB creates a new playlist service with database storage
func NewPlaylistServiceWithDB(db *database.DB, log *logger.Logger) *PlaylistService {
	return &PlaylistService{
		repo:        repositories.NewDatabasePlaylistRepository(db),
		useDatabase: true,
		logger:      log,
	}
}

// fileRepoAdapter adapts the old PlaylistRepository to the new interface
type fileRepoAdapter struct {
	repo *repositories.PlaylistRepository
}

func (a *fileRepoAdapter) List(guildID string) ([]string, error) {
	// File-based storage ignores guildID (global playlists)
	return a.repo.List()
}

func (a *fileRepoAdapter) Load(guildID, name string) (*entities.Playlist, error) {
	return a.repo.Load(name)
}

func (a *fileRepoAdapter) Save(guildID string, playlist *entities.Playlist) error {
	return a.repo.Save(playlist)
}

func (a *fileRepoAdapter) Delete(guildID, name string) error {
	return a.repo.Delete(name)
}

func (a *fileRepoAdapter) Exists(guildID, name string) bool {
	return a.repo.Exists(name)
}

// ListPlaylists returns all available playlists for a guild
func (s *PlaylistService) ListPlaylists() ([]string, error) {
	return s.ListPlaylistsForGuild("")
}

// ListPlaylistsForGuild returns all available playlists for a specific guild
func (s *PlaylistService) ListPlaylistsForGuild(guildID string) ([]string, error) {
	names, err := s.repo.List(guildID)
	if err != nil {
		s.logger.WithError(err).Error("Failed to list playlists")
		return nil, err
	}
	return names, nil
}

// GetPlaylist loads a playlist by name
func (s *PlaylistService) GetPlaylist(name string) (*entities.Playlist, error) {
	return s.GetPlaylistForGuild("", name)
}

// GetPlaylistForGuild loads a playlist by name for a specific guild
func (s *PlaylistService) GetPlaylistForGuild(guildID, name string) (*entities.Playlist, error) {
	playlist, err := s.repo.Load(guildID, name)
	if err != nil {
		s.logger.WithError(err).WithField("name", name).Error("Failed to load playlist")
		return nil, err
	}
	if playlist == nil {
		return nil, fmt.Errorf("playlist '%s' not found", name)
	}
	return playlist, nil
}

// CreatePlaylist creates a new empty playlist
func (s *PlaylistService) CreatePlaylist(name string) error {
	return s.CreatePlaylistForGuild("", name)
}

// CreatePlaylistForGuild creates a new empty playlist for a specific guild
func (s *PlaylistService) CreatePlaylistForGuild(guildID, name string) error {
	if s.repo.Exists(guildID, name) {
		return fmt.Errorf("playlist '%s' already exists", name)
	}

	playlist := entities.NewPlaylist(name)
	if err := s.repo.Save(guildID, playlist); err != nil {
		s.logger.WithError(err).WithField("name", name).Error("Failed to create playlist")
		return err
	}

	s.logger.WithField("name", name).Info("Playlist created")
	return nil
}

// DeletePlaylist deletes a playlist
func (s *PlaylistService) DeletePlaylist(name string) error {
	return s.DeletePlaylistForGuild("", name)
}

// DeletePlaylistForGuild deletes a playlist for a specific guild
func (s *PlaylistService) DeletePlaylistForGuild(guildID, name string) error {
	if err := s.repo.Delete(guildID, name); err != nil {
		s.logger.WithError(err).WithField("name", name).Error("Failed to delete playlist")
		return err
	}

	s.logger.WithField("name", name).Info("Playlist deleted")
	return nil
}

// AddToPlaylist adds a song to a playlist
func (s *PlaylistService) AddToPlaylist(name, originalInput string, sourceType valueobjects.SourceType, title string) error {
	return s.AddToPlaylistForGuild("", name, originalInput, sourceType, title)
}

// AddToPlaylistForGuild adds a song to a playlist for a specific guild
func (s *PlaylistService) AddToPlaylistForGuild(guildID, name, originalInput string, sourceType valueobjects.SourceType, title string) error {
	playlist, err := s.repo.Load(guildID, name)
	if err != nil {
		return err
	}
	if playlist == nil {
		return fmt.Errorf("playlist '%s' not found", name)
	}

	// Check for duplicates
	if playlist.HasEntry(originalInput) {
		return fmt.Errorf("song already exists in playlist '%s'", name)
	}

	playlist.AddEntry(originalInput, sourceType, title)

	if err := s.repo.Save(guildID, playlist); err != nil {
		s.logger.WithError(err).Error("Failed to save playlist")
		return err
	}

	s.logger.WithFields(map[string]interface{}{
		"playlist": name,
		"song":     title,
	}).Info("Song added to playlist")

	return nil
}

// RemoveFromPlaylist removes a song from a playlist
func (s *PlaylistService) RemoveFromPlaylist(name, originalInput string) error {
	return s.RemoveFromPlaylistForGuild("", name, originalInput)
}

// RemoveFromPlaylistForGuild removes a song from a playlist for a specific guild
func (s *PlaylistService) RemoveFromPlaylistForGuild(guildID, name, originalInput string) error {
	playlist, err := s.repo.Load(guildID, name)
	if err != nil {
		return err
	}
	if playlist == nil {
		return fmt.Errorf("playlist '%s' not found", name)
	}

	if !playlist.RemoveEntry(originalInput) {
		return fmt.Errorf("song not found in playlist")
	}

	if err := s.repo.Save(guildID, playlist); err != nil {
		s.logger.WithError(err).Error("Failed to save playlist")
		return err
	}

	s.logger.WithFields(map[string]interface{}{
		"playlist": name,
	}).Info("Song removed from playlist")

	return nil
}

// GetPlaylistSongs returns all songs in a playlist as Song entities
func (s *PlaylistService) GetPlaylistSongs(name string) ([]*entities.Song, error) {
	return s.GetPlaylistSongsForGuild("", name)
}

// GetPlaylistSongsForGuild returns all songs in a playlist for a specific guild
func (s *PlaylistService) GetPlaylistSongsForGuild(guildID, name string) ([]*entities.Song, error) {
	playlist, err := s.repo.Load(guildID, name)
	if err != nil {
		return nil, err
	}
	if playlist == nil {
		return nil, fmt.Errorf("playlist '%s' not found", name)
	}

	songs := make([]*entities.Song, 0, len(playlist.Entries))
	for _, entry := range playlist.Entries {
		song := entities.NewSong(entry.OriginalInput, entry.SourceType, "", "")
		// Pre-set metadata with title from playlist (won't be ready until processed)
		song.Metadata = &valueobjects.SongMetadata{
			Title: entry.Title,
		}
		songs = append(songs, song)
	}

	return songs, nil
}

// PlaylistExists checks if a playlist exists
func (s *PlaylistService) PlaylistExists(name string) bool {
	return s.PlaylistExistsForGuild("", name)
}

// PlaylistExistsForGuild checks if a playlist exists for a specific guild
func (s *PlaylistService) PlaylistExistsForGuild(guildID, name string) bool {
	return s.repo.Exists(guildID, name)
}

// RenamePlaylistForGuild renames an existing playlist for a specific guild
func (s *PlaylistService) RenamePlaylistForGuild(guildID, oldName, newName string) error {
	// Check if old playlist exists
	if !s.repo.Exists(guildID, oldName) {
		return fmt.Errorf("playlist '%s' does not exist", oldName)
	}

	// Check if new name already exists
	if s.repo.Exists(guildID, newName) {
		return fmt.Errorf("playlist '%s' already exists", newName)
	}

	// Load old playlist
	playlist, err := s.repo.Load(guildID, oldName)
	if err != nil {
		return fmt.Errorf("failed to load playlist: %w", err)
	}

	// Update playlist name
	playlist.Name = newName

	// Save with new name
	if err := s.repo.Save(guildID, playlist); err != nil {
		return fmt.Errorf("failed to save renamed playlist: %w", err)
	}

	// Delete old playlist
	if err := s.repo.Delete(guildID, oldName); err != nil {
		s.logger.WithError(err).Warn("Failed to delete old playlist after rename")
		// Not returning error here because the new playlist is already saved
	}

	return nil
}
