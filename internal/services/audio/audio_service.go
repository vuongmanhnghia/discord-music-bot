package audio

import (
	"errors"
	"fmt"
	"sync"

	"github.com/bwmarrin/discordgo"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
	"github.com/vuongmanhnghia/discord-music-bot/pkg/logger"
)

var (
	// ErrGuildNotFound is returned when guild is not found
	ErrGuildNotFound = errors.New("guild not found")
)

// AudioService manages voice connections, audio players, and tracklists for all guilds
type AudioService struct {
	session *discordgo.Session
	logger  *logger.Logger

	voiceConnections map[string]*VoiceConnection    // guildID -> voice connection
	audioPlayers     map[string]*AudioPlayer        // guildID -> audio player
	tracklists       map[string]*entities.Tracklist // guildID -> tracklist

	mu sync.RWMutex
}

// NewAudioService creates a new audio service
func NewAudioService(session *discordgo.Session, log *logger.Logger) *AudioService {
	return &AudioService{
		session:          session,
		logger:           log,
		voiceConnections: make(map[string]*VoiceConnection),
		audioPlayers:     make(map[string]*AudioPlayer),
		tracklists:       make(map[string]*entities.Tracklist),
	}
}

// ConnectToChannel connects to a voice channel
func (s *AudioService) ConnectToChannel(guildID, channelID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.logger.WithFields(map[string]interface{}{
		"guild":   guildID,
		"channel": channelID,
	}).Info("Connecting to voice channel...")

	// Get or create voice connection
	vc, exists := s.voiceConnections[guildID]
	if !exists {
		vc = NewVoiceConnection(guildID, s.logger)
		s.voiceConnections[guildID] = vc
	}

	// Connect
	if err := vc.Connect(s.session, channelID); err != nil {
		return err
	}

	// Initialize audio player if not exists
	if _, exists := s.audioPlayers[guildID]; !exists {
		player := NewAudioPlayer(guildID, vc, s.logger)
		s.audioPlayers[guildID] = player
	}

	// Initialize tracklist if not exists
	if _, exists := s.tracklists[guildID]; !exists {
		tracklist := entities.NewTracklist(guildID)
		s.tracklists[guildID] = tracklist
	}

	return nil
}

// DisconnectFromGuild disconnects from a guild's voice channel
func (s *AudioService) DisconnectFromGuild(guildID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.logger.WithField("guild", guildID).Info("Disconnecting from guild...")

	// Stop playback first
	if player, exists := s.audioPlayers[guildID]; exists {
		if player.IsPlaying() {
			if err := player.Stop(); err != nil {
				s.logger.WithError(err).Warn("Failed to stop player")
			}
		}
		player.Cleanup()
		delete(s.audioPlayers, guildID)
	}

	// Disconnect voice
	if vc, exists := s.voiceConnections[guildID]; exists {
		if err := vc.Disconnect(); err != nil {
			s.logger.WithError(err).Warn("Failed to disconnect voice")
		}
		delete(s.voiceConnections, guildID)
	}

	// Clear tracklist
	if tracklist, exists := s.tracklists[guildID]; exists {
		tracklist.Clear()
	}

	return nil
}

// PlaySong starts playing a song
func (s *AudioService) PlaySong(guildID string, song *entities.Song, callback PlaybackCallback) error {
	s.mu.RLock()
	player, exists := s.audioPlayers[guildID]
	s.mu.RUnlock()

	if !exists {
		return fmt.Errorf("%w: %s", ErrGuildNotFound, guildID)
	}

	return player.Play(song, callback)
}

// StopPlayback stops current playback
func (s *AudioService) StopPlayback(guildID string) error {
	s.mu.RLock()
	player, exists := s.audioPlayers[guildID]
	s.mu.RUnlock()

	if !exists {
		return fmt.Errorf("%w: %s", ErrGuildNotFound, guildID)
	}

	return player.Stop()
}

// PausePlayback pauses current playback
func (s *AudioService) PausePlayback(guildID string) error {
	s.mu.RLock()
	player, exists := s.audioPlayers[guildID]
	s.mu.RUnlock()

	if !exists {
		return fmt.Errorf("%w: %s", ErrGuildNotFound, guildID)
	}

	return player.Pause()
}

// ResumePlayback resumes playback
func (s *AudioService) ResumePlayback(guildID string) error {
	s.mu.RLock()
	player, exists := s.audioPlayers[guildID]
	s.mu.RUnlock()

	if !exists {
		return fmt.Errorf("%w: %s", ErrGuildNotFound, guildID)
	}

	return player.Resume()
}

// IsPlaying returns true if audio is playing in the guild
func (s *AudioService) IsPlaying(guildID string) bool {
	s.mu.RLock()
	player, exists := s.audioPlayers[guildID]
	s.mu.RUnlock()

	if !exists {
		return false
	}

	return player.IsPlaying()
}

// IsPaused returns true if playback is paused in the guild
func (s *AudioService) IsPaused(guildID string) bool {
	s.mu.RLock()
	player, exists := s.audioPlayers[guildID]
	s.mu.RUnlock()

	if !exists {
		return false
	}

	return player.IsPaused()
}

// IsConnected returns true if connected to voice in the guild
func (s *AudioService) IsConnected(guildID string) bool {
	s.mu.RLock()
	vc, exists := s.voiceConnections[guildID]
	s.mu.RUnlock()

	if !exists {
		return false
	}

	return vc.IsConnected()
}

// GetCurrentSong returns the currently playing song
func (s *AudioService) GetCurrentSong(guildID string) *entities.Song {
	s.mu.RLock()
	player, exists := s.audioPlayers[guildID]
	s.mu.RUnlock()

	if !exists {
		return nil
	}

	return player.GetCurrentSong()
}

// GetPlayer returns the audio player for a guild
func (s *AudioService) GetPlayer(guildID string) *AudioPlayer {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.audioPlayers[guildID]
}

// GetTracklist returns the tracklist for a guild
func (s *AudioService) GetTracklist(guildID string) *entities.Tracklist {
	// First try with read lock
	s.mu.RLock()
	tracklist, exists := s.tracklists[guildID]
	s.mu.RUnlock()

	if exists {
		return tracklist
	}

	// Need to create - acquire write lock
	s.mu.Lock()
	defer s.mu.Unlock()

	// Double-check after acquiring write lock
	if tracklist, exists = s.tracklists[guildID]; exists {
		return tracklist
	}

	// Create new tracklist
	tracklist = entities.NewTracklist(guildID)
	s.tracklists[guildID] = tracklist
	return tracklist
}

// GetVoiceChannelID returns the current voice channel ID for a guild
func (s *AudioService) GetVoiceChannelID(guildID string) string {
	s.mu.RLock()
	vc, exists := s.voiceConnections[guildID]
	s.mu.RUnlock()

	if !exists {
		return ""
	}

	return vc.GetChannelID()
}

// Cleanup performs cleanup for all guilds
func (s *AudioService) Cleanup() {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.logger.Info("Cleaning up audio service...")

	// Stop all players
	for guildID, player := range s.audioPlayers {
		if player.IsPlaying() {
			player.Stop()
		}
		player.Cleanup()
		s.logger.WithField("guild", guildID).Debug("Cleaned up audio player")
	}

	// Disconnect all voice connections
	for guildID, vc := range s.voiceConnections {
		if vc.IsConnected() {
			vc.Disconnect()
		}
		s.logger.WithField("guild", guildID).Debug("Disconnected voice connection")
	}

	s.logger.Info("✅ Audio service cleanup complete")
}

// CleanupAll disconnects all voice connections and cleans up all resources
func (s *AudioService) CleanupAll() {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.logger.Info("Cleaning up all audio resources...")

	// Stop all players
	for guildID, player := range s.audioPlayers {
		if player.IsPlaying() {
			if err := player.Stop(); err != nil {
				s.logger.WithError(err).WithField("guild", guildID).Warn("Failed to stop player")
			}
		}
		player.Cleanup()
	}
	s.audioPlayers = make(map[string]*AudioPlayer)

	// Disconnect all voice connections
	for guildID, vc := range s.voiceConnections {
		if err := vc.Disconnect(); err != nil {
			s.logger.WithError(err).WithField("guild", guildID).Warn("Failed to disconnect voice")
		}
	}
	s.voiceConnections = make(map[string]*VoiceConnection)

	// Clear all tracklists
	for _, tracklist := range s.tracklists {
		tracklist.Clear()
	}
	s.tracklists = make(map[string]*entities.Tracklist)

	s.logger.Info("✅ All audio resources cleaned up")
}

// GetStats returns statistics about the audio service
func (s *AudioService) GetStats() map[string]interface{} {
	s.mu.RLock()
	defer s.mu.RUnlock()

	activeConnections := 0
	activePlayers := 0

	for _, vc := range s.voiceConnections {
		if vc.IsConnected() {
			activeConnections++
		}
	}

	for _, player := range s.audioPlayers {
		if player.IsPlaying() {
			activePlayers++
		}
	}

	return map[string]interface{}{
		"total_guilds":       len(s.tracklists),
		"active_connections": activeConnections,
		"active_players":     activePlayers,
		"total_connections":  len(s.voiceConnections),
		"total_players":      len(s.audioPlayers),
	}
}
