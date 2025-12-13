package services

import (
	"fmt"

	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/repositories"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
	"github.com/vuongmanhnghia/discord-music-bot/pkg/logger"
)

// PlaylistService manages playlist operations
type PlaylistService struct {
	repo   *repositories.PlaylistRepository
	logger *logger.Logger
}

// NewPlaylistService creates a new playlist service
func NewPlaylistService(playlistDir string, log *logger.Logger) *PlaylistService {
	return &PlaylistService{
		repo:   repositories.NewPlaylistRepository(playlistDir),
		logger: log,
	}
}

// ListPlaylists returns all available playlists
func (s *PlaylistService) ListPlaylists() ([]string, error) {
	names, err := s.repo.List()
	if err != nil {
		s.logger.WithError(err).Error("Failed to list playlists")
		return nil, err
	}
	return names, nil
}

// GetPlaylist loads a playlist by name
func (s *PlaylistService) GetPlaylist(name string) (*entities.Playlist, error) {
	playlist, err := s.repo.Load(name)
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
	if s.repo.Exists(name) {
		return fmt.Errorf("playlist '%s' already exists", name)
	}

	playlist := entities.NewPlaylist(name)
	if err := s.repo.Save(playlist); err != nil {
		s.logger.WithError(err).WithField("name", name).Error("Failed to create playlist")
		return err
	}

	s.logger.WithField("name", name).Info("Playlist created")
	return nil
}

// DeletePlaylist deletes a playlist
func (s *PlaylistService) DeletePlaylist(name string) error {
	if err := s.repo.Delete(name); err != nil {
		s.logger.WithError(err).WithField("name", name).Error("Failed to delete playlist")
		return err
	}

	s.logger.WithField("name", name).Info("Playlist deleted")
	return nil
}

// AddToPlaylist adds a song to a playlist
func (s *PlaylistService) AddToPlaylist(name, originalInput string, sourceType valueobjects.SourceType, title string) error {
	playlist, err := s.repo.Load(name)
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

	if err := s.repo.Save(playlist); err != nil {
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
	playlist, err := s.repo.Load(name)
	if err != nil {
		return err
	}
	if playlist == nil {
		return fmt.Errorf("playlist '%s' not found", name)
	}

	if !playlist.RemoveEntry(originalInput) {
		return fmt.Errorf("song not found in playlist")
	}

	if err := s.repo.Save(playlist); err != nil {
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
	playlist, err := s.repo.Load(name)
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
	return s.repo.Exists(name)
}
