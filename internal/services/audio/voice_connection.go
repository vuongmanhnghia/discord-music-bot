package audio

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/bwmarrin/discordgo"
	"github.com/vuongmanhnghia/discord-music-bot/pkg/logger"
)

var (
	// ErrAlreadyConnected is returned when already connected to a voice channel
	ErrAlreadyConnected = errors.New("already connected to voice channel")
	// ErrNotConnected is returned when not connected to a voice channel
	ErrNotConnected = errors.New("not connected to voice channel")
	// ErrConnectionFailed is returned when connection fails
	ErrConnectionFailed = errors.New("failed to connect to voice channel")
)

// VoiceConnection represents a voice connection to a Discord channel
type VoiceConnection struct {
	guildID   string
	channelID string
	vc        *discordgo.VoiceConnection
	logger    *logger.Logger
	mu        sync.RWMutex
}

// NewVoiceConnection creates a new voice connection
func NewVoiceConnection(guildID string, log *logger.Logger) *VoiceConnection {
	return &VoiceConnection{
		guildID: guildID,
		logger:  log,
	}
}

// Connect connects to a voice channel
func (v *VoiceConnection) Connect(session *discordgo.Session, channelID string) error {
	v.mu.Lock()
	defer v.mu.Unlock()

	// Check if already connected
	if v.vc != nil && v.vc.Status == discordgo.VoiceConnectionStatusReady {
		if v.channelID == channelID {
			v.logger.WithField("channel", channelID).Info("Already connected to this channel")
			return nil
		}
		// Need to disconnect first to move to new channel
		v.logger.Info("Disconnecting from current channel to move")
		if err := v.disconnectLocked(); err != nil {
			v.logger.WithError(err).Warn("Failed to disconnect before moving")
		}
	}

	v.logger.WithField("channel", channelID).Info("Connecting to voice channel...")

	// Join voice channel (mute=false, deaf=true); waits until Ready internally (with 10s timeout)
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	vc, err := session.ChannelVoiceJoin(ctx, v.guildID, channelID, false, true)
	if err != nil {
		v.logger.WithError(err).Error("Failed to join voice channel")
		return fmt.Errorf("%w: %v", ErrConnectionFailed, err)
	}

	v.vc = vc
	v.channelID = channelID

	v.logger.WithField("channel", channelID).Info("✅ Successfully connected to voice channel")
	return nil
}

// Disconnect disconnects from the voice channel
func (v *VoiceConnection) Disconnect() error {
	v.mu.Lock()
	defer v.mu.Unlock()
	return v.disconnectLocked()
}

// disconnectLocked disconnects without acquiring lock (must be called with lock held)
func (v *VoiceConnection) disconnectLocked() error {
	if v.vc == nil {
		return ErrNotConnected
	}

	v.logger.Info("Disconnecting from voice channel...")

	if err := v.vc.Disconnect(context.Background()); err != nil {
		v.logger.WithError(err).Error("Failed to disconnect")
		return err
	}

	v.vc = nil
	v.channelID = ""

	v.logger.Info("✅ Disconnected from voice channel")
	return nil
}

// IsConnected returns true if connected to a voice channel
func (v *VoiceConnection) IsConnected() bool {
	v.mu.RLock()
	defer v.mu.RUnlock()
	return v.vc != nil && v.vc.Status == discordgo.VoiceConnectionStatusReady
}

// GetChannelID returns the current channel ID
func (v *VoiceConnection) GetChannelID() string {
	v.mu.RLock()
	defer v.mu.RUnlock()
	return v.channelID
}

// GetVoiceConnection returns the underlying voice connection (for audio streaming)
func (v *VoiceConnection) GetVoiceConnection() *discordgo.VoiceConnection {
	v.mu.RLock()
	defer v.mu.RUnlock()
	return v.vc
}

// Speaking sets the speaking state
func (v *VoiceConnection) Speaking(speaking bool) error {
	v.mu.RLock()
	defer v.mu.RUnlock()

	if v.vc == nil {
		return ErrNotConnected
	}

	return v.vc.Speaking(speaking)
}
