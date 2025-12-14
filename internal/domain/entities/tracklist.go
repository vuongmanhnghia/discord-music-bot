package entities

import (
	"container/list"
	"math/rand"
	"sync"
)

// RepeatMode defines how the tracklist repeats
type RepeatMode string

const (
	RepeatModeNone  RepeatMode = "none"
	RepeatModeTrack RepeatMode = "track"
	RepeatModeQueue RepeatMode = "queue"
)

// Tracklist manages the song queue with thread-safety
type Tracklist struct {
	guildID      string
	songs        []*Song
	currentIndex int
	history      *list.List // circular buffer for history
	maxHistory   int

	shuffleEnabled bool
	repeatMode     RepeatMode

	mu sync.RWMutex
}

// NewTracklist creates a new tracklist for a guild
func NewTracklist(guildID string) *Tracklist {
	return &Tracklist{
		guildID:        guildID,
		songs:          make([]*Song, 0),
		currentIndex:   0,
		history:        list.New(),
		maxHistory:     50,
		shuffleEnabled: false,
		repeatMode:     RepeatModeQueue, // Default: auto-repeat queue
	}
}

// AddSong adds a song to the queue and returns its position (1-indexed)
func (t *Tracklist) AddSong(song *Song) int {
	t.mu.Lock()
	defer t.mu.Unlock()

	t.songs = append(t.songs, song)
	return len(t.songs)
}

// CurrentSong returns the currently playing song
func (t *Tracklist) CurrentSong() *Song {
	t.mu.RLock()
	defer t.mu.RUnlock()

	if t.currentIndex >= 0 && t.currentIndex < len(t.songs) {
		return t.songs[t.currentIndex]
	}
	return nil
}

// NextSong moves to the next song based on repeat mode
func (t *Tracklist) NextSong() *Song {
	t.mu.Lock()
	defer t.mu.Unlock()

	// Track repeat: stay on same song
	if t.repeatMode == RepeatModeTrack {
		if t.currentIndex >= 0 && t.currentIndex < len(t.songs) {
			return t.songs[t.currentIndex]
		}
		return nil
	}

	// Add current song to history
	if t.currentIndex >= 0 && t.currentIndex < len(t.songs) {
		t.addToHistory(t.songs[t.currentIndex])
	}

	t.currentIndex++

	// Handle queue end
	if t.currentIndex >= len(t.songs) {
		if t.repeatMode == RepeatModeQueue && len(t.songs) > 0 {
			// Loop back to start
			t.currentIndex = 0
			return t.songs[t.currentIndex]
		}
		// No more songs
		if len(t.songs) > 0 {
			t.currentIndex = len(t.songs) - 1
		} else {
			t.currentIndex = 0
		}
		return nil
	}

	return t.songs[t.currentIndex]
}

// PreviousSong moves to the previous song
func (t *Tracklist) PreviousSong() *Song {
	t.mu.Lock()
	defer t.mu.Unlock()

	// Try to get from history first
	if t.history.Len() > 0 {
		element := t.history.Back()
		prevSong := element.Value.(*Song)
		t.history.Remove(element)

		// Find the song in the queue
		for i, song := range t.songs {
			if song.ID == prevSong.ID {
				t.currentIndex = i
				return song
			}
		}

		// If not found in queue, insert it
		if t.currentIndex >= 0 && t.currentIndex < len(t.songs) {
			t.songs = append(t.songs[:t.currentIndex], append([]*Song{prevSong}, t.songs[t.currentIndex:]...)...)
		} else {
			t.songs = append([]*Song{prevSong}, t.songs...)
			t.currentIndex = 0
		}
		return prevSong
	}

	// No history, go to previous in queue
	if t.currentIndex > 0 {
		t.currentIndex--
		return t.songs[t.currentIndex]
	}

	return nil
}

// SkipToPosition jumps to a specific position (1-indexed)
func (t *Tracklist) SkipToPosition(position int) *Song {
	t.mu.Lock()
	defer t.mu.Unlock()

	// Convert to 0-indexed
	index := position - 1

	if index >= 0 && index < len(t.songs) {
		// Add current to history if valid
		if t.currentIndex >= 0 && t.currentIndex < len(t.songs) {
			t.addToHistory(t.songs[t.currentIndex])
		}

		t.currentIndex = index
		return t.songs[t.currentIndex]
	}

	return nil
}

// GetUpcoming returns the next N songs
func (t *Tracklist) GetUpcoming(limit int) []*Song {
	t.mu.RLock()
	defer t.mu.RUnlock()

	start := t.currentIndex + 1
	end := start + limit
	if end > len(t.songs) {
		end = len(t.songs)
	}

	if start >= len(t.songs) {
		return []*Song{}
	}

	// Return copies to prevent external modification
	upcoming := make([]*Song, end-start)
	copy(upcoming, t.songs[start:end])
	return upcoming
}

// Size returns the total number of songs in queue
func (t *Tracklist) Size() int {
	t.mu.RLock()
	defer t.mu.RUnlock()
	return len(t.songs)
}

// Position returns current position as (current, total)
func (t *Tracklist) Position() (int, int) {
	t.mu.RLock()
	defer t.mu.RUnlock()
	return t.currentIndex + 1, len(t.songs)
}

// RemoveSong removes a song at position (1-indexed)
func (t *Tracklist) RemoveSong(position int) bool {
	t.mu.Lock()
	defer t.mu.Unlock()

	// Convert to 0-indexed
	index := position - 1

	if index < 0 || index >= len(t.songs) {
		return false
	}

	// Remove the song
	t.songs = append(t.songs[:index], t.songs[index+1:]...)

	// Adjust current index if needed
	if t.currentIndex >= len(t.songs) && len(t.songs) > 0 {
		t.currentIndex = len(t.songs) - 1
	} else if len(t.songs) == 0 {
		t.currentIndex = 0
	}

	return true
}

// Clear removes all songs from the queue
func (t *Tracklist) Clear() {
	t.mu.Lock()
	defer t.mu.Unlock()

	t.songs = make([]*Song, 0)
	t.currentIndex = 0
	t.history.Init() // Clear history
}

// SetRepeatMode sets the repeat mode
func (t *Tracklist) SetRepeatMode(mode RepeatMode) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.repeatMode = mode
}

// GetRepeatMode returns the current repeat mode
func (t *Tracklist) GetRepeatMode() RepeatMode {
	t.mu.RLock()
	defer t.mu.RUnlock()
	return t.repeatMode
}

// SetShuffle enables or disables shuffle mode
func (t *Tracklist) SetShuffle(enabled bool) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.shuffleEnabled = enabled
}

// Shuffle randomizes the order of songs in the queue (keeping current song in place)
func (t *Tracklist) Shuffle() {
	t.mu.Lock()
	defer t.mu.Unlock()

	if len(t.songs) <= 1 {
		return
	}

	// Keep current song, shuffle the rest
	currentSong := t.songs[t.currentIndex]

	// Remove current song from slice
	remaining := make([]*Song, 0, len(t.songs)-1)
	for i, s := range t.songs {
		if i != t.currentIndex {
			remaining = append(remaining, s)
		}
	}

	// Fisher-Yates shuffle
	for i := len(remaining) - 1; i > 0; i-- {
		j := rand.Intn(i + 1)
		remaining[i], remaining[j] = remaining[j], remaining[i]
	}

	// Rebuild songs with current song at start
	t.songs = append([]*Song{currentSong}, remaining...)
	t.currentIndex = 0
}

// IsShuffleEnabled returns whether shuffle is enabled
func (t *Tracklist) IsShuffleEnabled() bool {
	t.mu.RLock()
	defer t.mu.RUnlock()
	return t.shuffleEnabled
}

// addToHistory adds a song to history (private, must be called with lock held)
func (t *Tracklist) addToHistory(song *Song) {
	// Limit history size
	if t.history.Len() >= t.maxHistory {
		t.history.Remove(t.history.Front())
	}
	t.history.PushBack(song)
}

// GetAllSongs returns a copy of all songs (for display purposes)
func (t *Tracklist) GetAllSongs() []*Song {
	t.mu.RLock()
	defer t.mu.RUnlock()

	songs := make([]*Song, len(t.songs))
	copy(songs, t.songs)
	return songs
}
