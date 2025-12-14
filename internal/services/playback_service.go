package services

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/bwmarrin/discordgo"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
	"github.com/vuongmanhnghia/discord-music-bot/internal/services/audio"
	"github.com/vuongmanhnghia/discord-music-bot/pkg/logger"
)

var (
	// ErrNotPlaying is returned when no song is playing
	ErrNotPlaying = errors.New("no song is currently playing")
	// ErrAlreadyPlaying is returned when already playing
	ErrAlreadyPlaying = errors.New("already playing")
)

// PlaybackService orchestrates the complete playback flow
type PlaybackService struct {
	session           *discordgo.Session
	audioService      *audio.AudioService
	processingService *ProcessingService
	logger            *logger.Logger
	guildStates       map[string]*GuildPlaybackState
	mu                sync.RWMutex
}

// GuildPlaybackState represents playback state for a guild
type GuildPlaybackState struct {
	guildID    string
	tracklist  *entities.Tracklist
	isPlaying  bool
	currentPos int
	loopCtx    context.Context
	loopCancel context.CancelFunc
	mu         sync.RWMutex
}

// NewPlaybackService creates a new playback service
func NewPlaybackService(
	session *discordgo.Session,
	audioSvc *audio.AudioService,
	processingSvc *ProcessingService,
	log *logger.Logger,
) *PlaybackService {
	return &PlaybackService{
		session:           session,
		audioService:      audioSvc,
		processingService: processingSvc,
		logger:            log,
		guildStates:       make(map[string]*GuildPlaybackState),
	}
}

// Play starts or resumes playback in a guild
func (s *PlaybackService) Play(guildID, channelID string) error {
	state := s.getOrCreateState(guildID)

	state.mu.Lock()
	defer state.mu.Unlock()

	// Check if already playing
	if state.isPlaying {
		// Try to resume if paused
		if player := s.audioService.GetPlayer(guildID); player != nil {
			return player.Resume()
		}
		return ErrAlreadyPlaying
	}

	// Connect to voice channel
	if err := s.audioService.ConnectToChannel(guildID, channelID); err != nil {
		return fmt.Errorf("failed to connect: %w", err)
	}

	// Start playback loop
	state.isPlaying = true
	state.loopCtx, state.loopCancel = context.WithCancel(context.Background())

	go s.playbackLoop(state)

	s.logger.WithField("guild", guildID).Info("✅ Playback started")
	return nil
}

// Stop stops playback in a guild
func (s *PlaybackService) Stop(guildID string) error {
	state := s.getState(guildID)
	if state == nil {
		return ErrNotPlaying
	}

	state.mu.Lock()
	if !state.isPlaying {
		state.mu.Unlock()
		return ErrNotPlaying
	}

	// Cancel playback loop
	if state.loopCancel != nil {
		state.loopCancel()
	}
	state.isPlaying = false
	state.mu.Unlock()

	// Stop audio
	if player := s.audioService.GetPlayer(guildID); player != nil {
		player.Stop()
	}

	s.logger.WithField("guild", guildID).Info("Playback stopped")
	return nil
}

// Pause pauses playback
func (s *PlaybackService) Pause(guildID string) error {
	player := s.audioService.GetPlayer(guildID)
	if player == nil {
		return ErrNotPlaying
	}
	return player.Pause()
}

// Resume resumes playback
func (s *PlaybackService) Resume(guildID string) error {
	player := s.audioService.GetPlayer(guildID)
	if player == nil {
		return ErrNotPlaying
	}
	return player.Resume()
}

// Skip skips to the next song
func (s *PlaybackService) Skip(guildID string) error {
	state := s.getState(guildID)
	if state == nil {
		return ErrNotPlaying
	}

	// Stop current song to trigger next
	if player := s.audioService.GetPlayer(guildID); player != nil {
		player.Stop()
	}

	return nil
}

// AddSong adds a song to the queue and starts processing
func (s *PlaybackService) AddSong(guildID string, song *entities.Song) error {
	state := s.getOrCreateState(guildID)

	// Add to tracklist
	state.tracklist.AddSong(song)

	s.logger.WithFields(map[string]interface{}{
		"guild":   guildID,
		"song_id": song.ID,
	}).Info("Song added to queue")

	// Submit for processing
	return s.processingService.Submit(song, 0)
}

// playbackLoop is the main playback loop for a guild
func (s *PlaybackService) playbackLoop(state *GuildPlaybackState) {
	s.logger.WithField("guild", state.guildID).Debug("Playback loop started")

	ticker := time.NewTicker(500 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-state.loopCtx.Done():
			s.logger.WithField("guild", state.guildID).Debug("Playback loop stopped")
			return
		case <-ticker.C:
			// Check for next song periodically
			s.playNextSong(state)
		}
	}
}

// playNextSong plays the next available song
func (s *PlaybackService) playNextSong(state *GuildPlaybackState) bool {
	// Get next song
	song := state.tracklist.CurrentSong()
	if song == nil {
		return false
	}

	// Wait for song to be ready
	if !s.waitForSong(song, state.loopCtx) {
		// Song failed or context cancelled
		s.handleFailedSong(state, song)
		return false
	}

	// Check voice connection
	if !s.audioService.IsConnected(state.guildID) {
		s.logger.Error("Voice connection lost, stopping playback")
		state.mu.Lock()
		if state.loopCancel != nil {
			state.loopCancel()
		}
		state.isPlaying = false
		state.mu.Unlock()
		return false
	}

	// Play the song
	player := s.audioService.GetPlayer(state.guildID)
	if player == nil {
		s.logger.Error("No audio player available")
		return false
	}

	s.logger.WithFields(map[string]interface{}{
		"guild": state.guildID,
		"song":  song.GetMetadata().Title,
	}).Info("▶️ Now playing")

	// Set completion callback
	done := make(chan error)
	onComplete := func(completedSong *entities.Song, err error) {
		done <- err
	}

	// Play song
	if err := player.Play(song, onComplete); err != nil {
		s.logger.WithError(err).Error("Failed to play song")
		s.handleFailedSong(state, song)
		return false
	}

	// Wait for completion or context cancellation
	select {
	case err := <-done:
		if err != nil {
			s.logger.WithError(err).Error("Playback failed")
			s.handleFailedSong(state, song)
		} else {
			s.logger.Debug("Song completed")
			s.handleSongComplete(state)
		}
		return true
	case <-state.loopCtx.Done():
		return false
	}
}

// waitForSong waits for a song to become ready
func (s *PlaybackService) waitForSong(song *entities.Song, ctx context.Context) bool {
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()

	timeout := time.After(30 * time.Second)

	for {
		status := song.GetStatus()

		if status == valueobjects.SongStatusReady {
			return true
		}

		if status == valueobjects.SongStatusFailed {
			return false
		}

		select {
		case <-ticker.C:
			continue
		case <-timeout:
			s.logger.Warn("Timeout waiting for song to be ready")
			return false
		case <-ctx.Done():
			return false
		}
	}
}

// handleSongComplete handles song completion
func (s *PlaybackService) handleSongComplete(state *GuildPlaybackState) {
	// Move to next based on repeat mode
	switch state.tracklist.GetRepeatMode() {
	case entities.RepeatModeNone:
		state.tracklist.NextSong()
	case entities.RepeatModeTrack:
		// Stay on current song
	case entities.RepeatModeQueue:
		state.tracklist.NextSong() // Will wrap around
	}
}

// handleFailedSong handles a failed song
func (s *PlaybackService) handleFailedSong(state *GuildPlaybackState, song *entities.Song) {
	s.logger.WithField("song_id", song.ID).Warn("Skipping failed song")
	state.tracklist.NextSong()
}

// getOrCreateState gets or creates guild state
func (s *PlaybackService) getOrCreateState(guildID string) *GuildPlaybackState {
	s.mu.Lock()
	defer s.mu.Unlock()

	if state, exists := s.guildStates[guildID]; exists {
		return state
	}

	state := &GuildPlaybackState{
		guildID:   guildID,
		tracklist: entities.NewTracklist(guildID),
	}
	s.guildStates[guildID] = state
	return state
}

// getState gets guild state if it exists
func (s *PlaybackService) getState(guildID string) *GuildPlaybackState {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.guildStates[guildID]
}

// GetTracklist returns the tracklist for a guild
func (s *PlaybackService) GetTracklist(guildID string) *entities.Tracklist {
	state := s.getState(guildID)
	if state == nil {
		return nil
	}
	return state.tracklist
}

// IsPlaying checks if a guild is currently playing
func (s *PlaybackService) IsPlaying(guildID string) bool {
	state := s.getState(guildID)
	if state == nil {
		return false
	}

	state.mu.RLock()
	defer state.mu.RUnlock()
	return state.isPlaying
}

// Cleanup cleans up resources for a guild
func (s *PlaybackService) Cleanup(guildID string) {
	s.logger.WithField("guild", guildID).Info("Cleaning up playback state")

	// Stop playback
	s.Stop(guildID)

	// Disconnect audio
	s.audioService.DisconnectFromGuild(guildID)

	// Remove state
	s.mu.Lock()
	delete(s.guildStates, guildID)
	s.mu.Unlock()
}

// SetVolume sets the volume for a guild (0-100)
func (s *PlaybackService) SetVolume(guildID string, level int) error {
	if level < 0 || level > 100 {
		return errors.New("volume must be between 0 and 100")
	}

	player := s.audioService.GetPlayer(guildID)
	if player != nil {
		player.SetVolume(level)
	}

	return nil
}
