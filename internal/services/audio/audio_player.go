package audio

import (
	"errors"
	"fmt"
	"sync"
	"sync/atomic"
	"time"

	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
	"github.com/vuongmanhnghia/discord-music-bot/pkg/logger"
)

var (
	// ErrNoVoiceConnection is returned when there's no voice connection
	ErrNoVoiceConnection = errors.New("no voice connection")
	// ErrPlayerNotPlaying is returned when player is not playing
	ErrPlayerNotPlaying = errors.New("player is not playing")
)

// PlaybackCallback is called when playback ends or errors occur
type PlaybackCallback func(song *entities.Song, err error)

// AudioPlayer manages audio playback for a guild
type AudioPlayer struct {
	guildID string
	vc      *VoiceConnection
	encoder *AudioEncoder
	logger  *logger.Logger

	currentSong *entities.Song
	isPlaying   atomic.Bool
	isPaused    atomic.Bool
	stopSignal  chan struct{}
	callback    PlaybackCallback
	volume      int // Volume level 0-100

	mu sync.RWMutex
}

// NewAudioPlayer creates a new audio player
func NewAudioPlayer(guildID string, vc *VoiceConnection, log *logger.Logger) *AudioPlayer {
	return &AudioPlayer{
		guildID:    guildID,
		vc:         vc,
		encoder:    NewAudioEncoder(log),
		logger:     log,
		stopSignal: make(chan struct{}),
		volume:     30, // Default volume 30%
	}
}

// Play starts playing a song
func (p *AudioPlayer) Play(song *entities.Song, callback PlaybackCallback) error {
	p.mu.Lock()
	defer p.mu.Unlock()

	// Check if already playing
	if p.isPlaying.Load() {
		return ErrAlreadyPlaying
	}

	// Check voice connection
	if !p.vc.IsConnected() {
		return ErrNoVoiceConnection
	}

	// Ensure song is ready
	if !song.IsReady() {
		return fmt.Errorf("song is not ready: status=%s", song.GetStatus())
	}

	// Use OriginalInput (YouTube URL) for yt-dlp pipe encoding
	// This bypasses 403 errors that occur with direct stream URLs
	sourceURL := song.OriginalInput
	if sourceURL == "" {
		return fmt.Errorf("song has no source URL")
	}

	p.logger.WithFields(map[string]interface{}{
		"song":   song.DisplayName(),
		"status": song.GetStatus(),
	}).Info("🎵 Starting playback...")

	p.currentSong = song
	p.callback = callback
	p.stopSignal = make(chan struct{})
	p.isPlaying.Store(true)
	p.isPaused.Store(false)

	// Start playback in goroutine
	go p.playbackLoop(song, sourceURL)

	return nil
}

// playbackLoop handles the actual playback
func (p *AudioPlayer) playbackLoop(song *entities.Song, sourceURL string) {
	defer func() {
		p.isPlaying.Store(false)
		p.isPaused.Store(false)

		p.mu.Lock()
		callback := p.callback
		p.callback = nil
		p.mu.Unlock()

		if callback != nil {
			callback(song, nil)
		}
	}()

	// Set speaking status
	if err := p.vc.Speaking(true); err != nil {
		p.logger.WithError(err).Error("Failed to set speaking status")
		return
	}
	defer p.vc.Speaking(false)

	// Encode stream using yt-dlp -> FFmpeg pipe approach
	// This downloads audio with yt-dlp and encodes to Opus via FFmpeg
	// Using sourceURL (original YouTube URL) to bypass 403 errors
	options := DefaultEncodeOptions()

	// Apply current volume setting
	p.mu.RLock()
	options.Volume = p.volume
	p.mu.RUnlock()

	p.logger.WithField("volume", options.Volume).Debug("Starting playback with volume")

	frameChannel, errorChannel, err := p.encoder.EncodeStream(sourceURL, options)
	if err != nil {
		p.logger.WithError(err).Error("Failed to start encoding")

		p.mu.Lock()
		callback := p.callback
		p.mu.Unlock()

		if callback != nil {
			callback(song, err)
		}
		return
	}

	// Get voice connection
	vc := p.vc.GetVoiceConnection()
	if vc == nil {
		p.logger.Error("Voice connection is nil")
		return
	}

	p.logger.Info("📻 Streaming audio to Discord...")

	// Stream audio frames
	frameCount := 0
	for {
		select {
		case <-p.stopSignal:
			p.logger.Info("⏹️ Playback stopped by user")
			return

		case err := <-errorChannel:
			if err != nil {
				p.logger.WithError(err).Error("Encoding error")

				p.mu.Lock()
				callback := p.callback
				p.mu.Unlock()

				if callback != nil {
					callback(song, err)
				}
				return
			}

		case frame, ok := <-frameChannel:
			if !ok {
				// Channel closed, playback finished
				p.logger.WithField("frames", frameCount).Info("✅ Playback completed")
				return
			}

			// Handle pause
			for p.isPaused.Load() {
				select {
				case <-p.stopSignal:
					return
				case <-time.After(100 * time.Millisecond):
					// Continue checking pause state
				}
			}

			// Send frame to Discord
			select {
			case vc.OpusSend <- frame:
				frameCount++
			case <-p.stopSignal:
				p.logger.Info("⏹️ Playback stopped during frame send")
				return
			}
		}
	}
}

// Stop stops the current playback
func (p *AudioPlayer) Stop() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	if !p.isPlaying.Load() {
		return ErrPlayerNotPlaying
	}

	p.logger.Info("⏹️ Stopping playback...")

	// Signal stop - use select to avoid panic on double close
	select {
	case <-p.stopSignal:
		// Already closed
	default:
		close(p.stopSignal)
	}

	// Wait a bit for cleanup
	time.Sleep(100 * time.Millisecond)

	p.isPlaying.Store(false)
	p.isPaused.Store(false)
	p.currentSong = nil

	return nil
}

// Pause pauses the playback
func (p *AudioPlayer) Pause() error {
	if !p.isPlaying.Load() {
		return ErrPlayerNotPlaying
	}

	if p.isPaused.Load() {
		return errors.New("already paused")
	}

	p.logger.Info("⏸️ Pausing playback...")
	p.isPaused.Store(true)

	// Set speaking to false when paused
	if err := p.vc.Speaking(false); err != nil {
		p.logger.WithError(err).Warn("Failed to update speaking status on pause")
	}

	return nil
}

// Resume resumes the playback
func (p *AudioPlayer) Resume() error {
	if !p.isPlaying.Load() {
		return ErrPlayerNotPlaying
	}

	if !p.isPaused.Load() {
		return errors.New("not paused")
	}

	p.logger.Info("▶️ Resuming playback...")
	p.isPaused.Store(false)

	// Set speaking to true when resumed
	if err := p.vc.Speaking(true); err != nil {
		p.logger.WithError(err).Warn("Failed to update speaking status on resume")
	}

	return nil
}

// IsPlaying returns true if currently playing
func (p *AudioPlayer) IsPlaying() bool {
	return p.isPlaying.Load()
}

// IsPaused returns true if currently paused
func (p *AudioPlayer) IsPaused() bool {
	return p.isPaused.Load()
}

// GetCurrentSong returns the currently playing song
func (p *AudioPlayer) GetCurrentSong() *entities.Song {
	p.mu.RLock()
	defer p.mu.RUnlock()
	return p.currentSong
}

// Cleanup performs cleanup when player is no longer needed
func (p *AudioPlayer) Cleanup() {
	if p.isPlaying.Load() {
		p.Stop()
	}
}

// SetVolume sets the volume level (0-100)
func (p *AudioPlayer) SetVolume(level int) {
	p.mu.Lock()
	defer p.mu.Unlock()
	if level < 0 {
		level = 0
	}
	if level > 100 {
		level = 100
	}
	p.volume = level
	p.logger.WithField("volume", level).Info("Volume set")
}

// GetVolume returns the current volume level
func (p *AudioPlayer) GetVolume() int {
	p.mu.RLock()
	defer p.mu.RUnlock()
	return p.volume
}
