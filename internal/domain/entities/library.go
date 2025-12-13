package entities

import (
	"sync"

	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
)

// PlaylistRepository interface for persistence
type PlaylistRepository interface {
	Save(playlist *Playlist) error
	Load(playlistName string) (*Playlist, error)
	Delete(playlistName string) error
	Exists(playlistName string) bool
	ListAll() ([]string, error)
}

// Library manages the music library with persistent storage
type Library struct {
	repository PlaylistRepository
	cache      map[string]*Playlist
	mu         sync.RWMutex
}

// NewLibrary creates a new library instance
func NewLibrary(repository PlaylistRepository) *Library {
	return &Library{
		repository: repository,
		cache:      make(map[string]*Playlist),
	}
}

// CreatePlaylist creates a new empty playlist
func (l *Library) CreatePlaylist(name string) error {
	l.mu.Lock()
	defer l.mu.Unlock()

	if l.repository.Exists(name) {
		return ErrPlaylistExists
	}

	playlist := NewPlaylist(name)
	if err := l.repository.Save(playlist); err != nil {
		return err
	}

	l.cache[name] = playlist
	return nil
}

// GetPlaylist retrieves a playlist by name (with caching)
func (l *Library) GetPlaylist(name string) (*Playlist, error) {
	l.mu.RLock()
	if cached, ok := l.cache[name]; ok {
		l.mu.RUnlock()
		return cached, nil
	}
	l.mu.RUnlock()

	l.mu.Lock()
	defer l.mu.Unlock()

	// Double-check after acquiring write lock
	if cached, ok := l.cache[name]; ok {
		return cached, nil
	}

	playlist, err := l.repository.Load(name)
	if err != nil {
		return nil, err
	}

	if playlist == nil {
		return nil, ErrPlaylistNotFound
	}

	l.cache[name] = playlist
	return playlist, nil
}

// SavePlaylist saves a playlist to storage
func (l *Library) SavePlaylist(playlist *Playlist) error {
	l.mu.Lock()
	defer l.mu.Unlock()

	if err := l.repository.Save(playlist); err != nil {
		return err
	}

	l.cache[playlist.Name] = playlist
	return nil
}

// DeletePlaylist deletes a playlist
func (l *Library) DeletePlaylist(name string) error {
	l.mu.Lock()
	defer l.mu.Unlock()

	if err := l.repository.Delete(name); err != nil {
		return err
	}

	delete(l.cache, name)
	return nil
}

// ListPlaylists returns all playlist names
func (l *Library) ListPlaylists() ([]string, error) {
	return l.repository.ListAll()
}

// AddToPlaylist adds a song to a playlist
func (l *Library) AddToPlaylist(playlistName, originalInput string, sourceType valueobjects.SourceType, title string) (bool, error) {
	playlist, err := l.GetPlaylist(playlistName)
	if err != nil {
		return false, err
	}

	// Check for duplicate
	if playlist.HasEntry(originalInput) {
		return true, nil // Not an error, just a duplicate
	}

	playlist.AddEntry(originalInput, sourceType, title)

	if err := l.SavePlaylist(playlist); err != nil {
		return false, err
	}

	return false, nil // Not a duplicate, added successfully
}

// RemoveFromPlaylist removes a song from a playlist
func (l *Library) RemoveFromPlaylist(playlistName, originalInput string) error {
	playlist, err := l.GetPlaylist(playlistName)
	if err != nil {
		return err
	}

	if !playlist.RemoveEntry(originalInput) {
		return ErrSongNotInPlaylist
	}

	return l.SavePlaylist(playlist)
}

// Custom errors
var (
	ErrPlaylistExists    = &LibraryError{Message: "playlist already exists"}
	ErrPlaylistNotFound  = &LibraryError{Message: "playlist not found"}
	ErrSongNotInPlaylist = &LibraryError{Message: "song not in playlist"}
)

// LibraryError represents a library-specific error
type LibraryError struct {
	Message string
}

func (e *LibraryError) Error() string {
	return e.Message
}
