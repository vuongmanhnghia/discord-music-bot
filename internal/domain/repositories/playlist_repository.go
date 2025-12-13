package repositories

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
)

// PlaylistRepository handles persistence of playlists
type PlaylistRepository struct {
	baseDir string
}

// NewPlaylistRepository creates a new playlist repository
func NewPlaylistRepository(baseDir string) *PlaylistRepository {
	return &PlaylistRepository{
		baseDir: baseDir,
	}
}

// List returns all playlist names
func (r *PlaylistRepository) List() ([]string, error) {
	entries, err := os.ReadDir(r.baseDir)
	if err != nil {
		if os.IsNotExist(err) {
			return []string{}, nil
		}
		return nil, fmt.Errorf("failed to read playlist directory: %w", err)
	}

	var names []string
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		name := entry.Name()
		if strings.HasSuffix(name, ".json") && !strings.HasSuffix(name, ".backup") && !strings.HasSuffix(name, ".deleted") {
			names = append(names, strings.TrimSuffix(name, ".json"))
		}
	}

	return names, nil
}

// Load loads a playlist from disk
func (r *PlaylistRepository) Load(name string) (*entities.Playlist, error) {
	path := r.getPath(name)

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil // Playlist doesn't exist
		}
		return nil, fmt.Errorf("failed to read playlist file: %w", err)
	}

	var playlist entities.Playlist
	if err := json.Unmarshal(data, &playlist); err != nil {
		return nil, fmt.Errorf("failed to parse playlist JSON: %w", err)
	}

	return &playlist, nil
}

// Save saves a playlist to disk
func (r *PlaylistRepository) Save(playlist *entities.Playlist) error {
	// Ensure directory exists
	if err := os.MkdirAll(r.baseDir, 0755); err != nil {
		return fmt.Errorf("failed to create playlist directory: %w", err)
	}

	path := r.getPath(playlist.Name)

	// Create backup if file exists
	if _, err := os.Stat(path); err == nil {
		backupPath := path + ".backup"
		if data, err := os.ReadFile(path); err == nil {
			os.WriteFile(backupPath, data, 0644)
		}
	}

	data, err := json.MarshalIndent(playlist, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal playlist: %w", err)
	}

	if err := os.WriteFile(path, data, 0644); err != nil {
		return fmt.Errorf("failed to write playlist file: %w", err)
	}

	return nil
}

// Delete deletes a playlist (moves to .deleted)
func (r *PlaylistRepository) Delete(name string) error {
	path := r.getPath(name)
	deletedPath := path + ".deleted"

	if err := os.Rename(path, deletedPath); err != nil {
		if os.IsNotExist(err) {
			return fmt.Errorf("playlist '%s' not found", name)
		}
		return fmt.Errorf("failed to delete playlist: %w", err)
	}

	return nil
}

// Exists checks if a playlist exists
func (r *PlaylistRepository) Exists(name string) bool {
	path := r.getPath(name)
	_, err := os.Stat(path)
	return err == nil
}

// getPath returns the file path for a playlist
func (r *PlaylistRepository) getPath(name string) string {
	// Replace spaces with underscores for filename safety
	safeName := strings.ReplaceAll(name, " ", "_")
	return filepath.Join(r.baseDir, safeName+".json")
}
