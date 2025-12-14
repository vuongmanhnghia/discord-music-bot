package persistence

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
)

// PlaylistRepository handles persistence of playlists to JSON files
type PlaylistRepository struct {
	basePath string
	mu       sync.RWMutex
}

// NewPlaylistRepository creates a new playlist repository
func NewPlaylistRepository(basePath string) (*PlaylistRepository, error) {
	// Ensure base path exists
	if err := os.MkdirAll(basePath, 0755); err != nil {
		return nil, fmt.Errorf("failed to create playlist directory: %w", err)
	}

	return &PlaylistRepository{
		basePath: basePath,
	}, nil
}

// Save saves a playlist to a JSON file with atomic write
func (r *PlaylistRepository) Save(playlist *entities.Playlist) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	filePath := r.getFilePath(playlist.Name)

	// Create backup if file exists
	if _, err := os.Stat(filePath); err == nil {
		backupPath := filePath + ".backup"
		if err := r.copyFile(filePath, backupPath); err != nil {
			// Log warning but continue
			fmt.Printf("Warning: could not create backup: %v\n", err)
		}
	}

	// Atomic write using temp file
	tempPath := filePath + ".tmp"
	file, err := os.Create(tempPath)
	if err != nil {
		return fmt.Errorf("failed to create temp file: %w", err)
	}

	encoder := json.NewEncoder(file)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(playlist); err != nil {
		file.Close()
		os.Remove(tempPath)
		return fmt.Errorf("failed to encode playlist: %w", err)
	}

	if err := file.Close(); err != nil {
		os.Remove(tempPath)
		return fmt.Errorf("failed to close temp file: %w", err)
	}

	// Rename for atomicity
	if err := os.Rename(tempPath, filePath); err != nil {
		return fmt.Errorf("failed to rename temp file: %w", err)
	}

	return nil
}

// Load loads a playlist from a JSON file
func (r *PlaylistRepository) Load(playlistName string) (*entities.Playlist, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	filePath := r.getFilePath(playlistName)

	file, err := os.Open(filePath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil // Playlist not found
		}
		return nil, fmt.Errorf("failed to open playlist file: %w", err)
	}
	defer file.Close()

	var playlist entities.Playlist
	decoder := json.NewDecoder(file)
	if err := decoder.Decode(&playlist); err != nil {
		return nil, fmt.Errorf("failed to decode playlist: %w", err)
	}

	return &playlist, nil
}

// Delete deletes a playlist file (soft delete by renaming)
func (r *PlaylistRepository) Delete(playlistName string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	filePath := r.getFilePath(playlistName)

	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		return fmt.Errorf("playlist not found: %s", playlistName)
	}

	// Soft delete by renaming
	deletedPath := filePath + ".deleted"
	if err := os.Rename(filePath, deletedPath); err != nil {
		return fmt.Errorf("failed to delete playlist: %w", err)
	}

	return nil
}

// Exists checks if a playlist exists
func (r *PlaylistRepository) Exists(playlistName string) bool {
	r.mu.RLock()
	defer r.mu.RUnlock()

	filePath := r.getFilePath(playlistName)
	_, err := os.Stat(filePath)
	return err == nil
}

// ListAll returns all playlist names
func (r *PlaylistRepository) ListAll() ([]string, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	files, err := os.ReadDir(r.basePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read playlist directory: %w", err)
	}

	playlists := make([]string, 0)
	for _, file := range files {
		if file.IsDir() {
			continue
		}

		name := file.Name()
		if strings.HasSuffix(name, ".json") &&
			!strings.HasSuffix(name, ".backup") &&
			!strings.HasSuffix(name, ".tmp") &&
			!strings.HasSuffix(name, ".deleted") {
			// Remove .json extension
			playlistName := strings.TrimSuffix(name, ".json")
			playlists = append(playlists, playlistName)
		}
	}

	return playlists, nil
}

// getFilePath returns the full file path for a playlist
func (r *PlaylistRepository) getFilePath(playlistName string) string {
	// Sanitize filename
	safeName := r.sanitizeFilename(playlistName)
	return filepath.Join(r.basePath, safeName+".json")
}

// sanitizeFilename removes unsafe characters from filename
func (r *PlaylistRepository) sanitizeFilename(name string) string {
	// Replace unsafe characters with underscore
	safeName := ""
	for _, char := range name {
		if (char >= 'a' && char <= 'z') ||
			(char >= 'A' && char <= 'Z') ||
			(char >= '0' && char <= '9') ||
			char == '-' || char == '_' {
			safeName += string(char)
		} else {
			safeName += "_"
		}
	}
	return safeName
}

// copyFile copies a file from src to dst
func (r *PlaylistRepository) copyFile(src, dst string) error {
	sourceFile, err := os.Open(src)
	if err != nil {
		return err
	}
	defer sourceFile.Close()

	destFile, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer destFile.Close()

	_, err = io.Copy(destFile, sourceFile)
	return err
}
