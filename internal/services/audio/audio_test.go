package audio_test

import (
	"fmt"
	"testing"
	"time"

	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
	"github.com/vuongmanhnghia/discord-music-bot/internal/services/audio"
	"github.com/vuongmanhnghia/discord-music-bot/pkg/logger"
)

func TestVoiceConnectionCreation(t *testing.T) {
	log := logger.New(logger.Config{Level: "info"})

	vc := audio.NewVoiceConnection("test-guild-123", log)

	if vc == nil {
		t.Fatal("Expected voice connection to be created")
	}

	if vc.IsConnected() {
		t.Error("New voice connection should not be connected")
	}

	if vc.GetChannelID() != "" {
		t.Error("New voice connection should have empty channel ID")
	}
}

func TestVoiceConnectionStates(t *testing.T) {
	log := logger.New(logger.Config{Level: "error"})

	vc := audio.NewVoiceConnection("test-guild-123", log)

	// Test initial state
	if vc.IsConnected() {
		t.Error("Should not be connected initially")
	}

	// Test disconnect when not connected
	err := vc.Disconnect()
	if err != audio.ErrNotConnected {
		t.Errorf("Expected ErrNotConnected, got %v", err)
	}
}

func TestAudioEncoderCreation(t *testing.T) {
	log := logger.New(logger.Config{Level: "info"})

	encoder := audio.NewAudioEncoder(log)

	if encoder == nil {
		t.Fatal("Expected encoder to be created")
	}
}

func TestEncodeOptions(t *testing.T) {
	options := audio.DefaultEncodeOptions()

	if options.Volume != 100 {
		t.Errorf("Expected default volume 100, got %d", options.Volume)
	}

	if options.Bitrate != 128 {
		t.Errorf("Expected default bitrate 128, got %d", options.Bitrate)
	}

	if options.Application != "audio" {
		t.Errorf("Expected default application 'audio', got %s", options.Application)
	}
}

func TestAudioPlayerCreation(t *testing.T) {
	log := logger.New(logger.Config{Level: "info"})

	vc := audio.NewVoiceConnection("test-guild-123", log)
	player := audio.NewAudioPlayer("test-guild-123", vc, log)

	if player == nil {
		t.Fatal("Expected player to be created")
	}

	if player.IsPlaying() {
		t.Error("New player should not be playing")
	}

	if player.IsPaused() {
		t.Error("New player should not be paused")
	}

	if player.GetCurrentSong() != nil {
		t.Error("New player should have no current song")
	}
}

func TestAudioPlayerStates(t *testing.T) {
	log := logger.New(logger.Config{Level: "error"})

	vc := audio.NewVoiceConnection("test-guild-123", log)
	player := audio.NewAudioPlayer("test-guild-123", vc, log)

	// Test stop when not playing
	err := player.Stop()
	if err != audio.ErrPlayerNotPlaying {
		t.Errorf("Expected ErrPlayerNotPlaying, got %v", err)
	}

	// Test pause when not playing
	err = player.Pause()
	if err != audio.ErrPlayerNotPlaying {
		t.Errorf("Expected ErrPlayerNotPlaying, got %v", err)
	}

	// Test resume when not playing
	err = player.Resume()
	if err != audio.ErrPlayerNotPlaying {
		t.Errorf("Expected ErrPlayerNotPlaying, got %v", err)
	}
}

func TestAudioPlayerPlayRequiresReadySong(t *testing.T) {
	log := logger.New(logger.Config{Level: "error"})

	vc := audio.NewVoiceConnection("test-guild-123", log)
	player := audio.NewAudioPlayer("test-guild-123", vc, log)

	// Create a song that's not ready
	song := entities.NewSong(
		"https://example.com/test.mp3",
		valueobjects.SourceTypeURL,
		"TestUser",
		"test-guild-123",
	)

	// Try to play song that's not ready
	err := player.Play(song, nil)
	if err == nil {
		t.Error("Expected error when playing non-ready song")
	}
}

func TestAudioPlayerPlayRequiresConnection(t *testing.T) {
	log := logger.New(logger.Config{Level: "error"})

	vc := audio.NewVoiceConnection("test-guild-123", log)
	player := audio.NewAudioPlayer("test-guild-123", vc, log)

	// Create a ready song
	song := entities.NewSong(
		"https://example.com/test.mp3",
		valueobjects.SourceTypeURL,
		"TestUser",
		"test-guild-123",
	)

	metadata := &valueobjects.SongMetadata{
		Title:    "Test Song",
		Duration: 180,
	}
	song.MarkReady(metadata, "https://stream.example.com/audio.m3u8")

	// Try to play without voice connection (should fail)
	err := player.Play(song, nil)
	if err != audio.ErrNoVoiceConnection {
		t.Errorf("Expected ErrNoVoiceConnection, got %v", err)
	}
}

func TestAudioPlayerCleanup(t *testing.T) {
	log := logger.New(logger.Config{Level: "error"})

	vc := audio.NewVoiceConnection("test-guild-123", log)
	player := audio.NewAudioPlayer("test-guild-123", vc, log)

	// Cleanup should not panic even when not playing
	player.Cleanup()
}

func TestAudioServiceCreation(t *testing.T) {
	log := logger.New(logger.Config{Level: "info"})

	// Note: Cannot create real Discord session without token
	// In real tests, we'd use a mock
	service := audio.NewAudioService(nil, log)

	if service == nil {
		t.Fatal("Expected service to be created")
	}

	stats := service.GetStats()
	if stats == nil {
		t.Error("Stats should not be nil")
	}

	if stats["total_guilds"].(int) != 0 {
		t.Error("New service should have 0 guilds")
	}
}

func TestAudioServiceStates(t *testing.T) {
	log := logger.New(logger.Config{Level: "error"})
	service := audio.NewAudioService(nil, log)

	guildID := "test-guild-123"

	// Test initial states
	if service.IsConnected(guildID) {
		t.Error("Should not be connected initially")
	}

	if service.IsPlaying(guildID) {
		t.Error("Should not be playing initially")
	}

	if service.IsPaused(guildID) {
		t.Error("Should not be paused initially")
	}

	if service.GetCurrentSong(guildID) != nil {
		t.Error("Should have no current song")
	}
}

func TestAudioServiceTracklist(t *testing.T) {
	log := logger.New(logger.Config{Level: "error"})
	service := audio.NewAudioService(nil, log)

	guildID := "test-guild-123"

	// Get tracklist (should auto-create)
	tracklist := service.GetTracklist(guildID)
	if tracklist == nil {
		t.Fatal("Tracklist should be created")
	}

	if tracklist.Size() != 0 {
		t.Error("New tracklist should be empty")
	}

	// Get again (should return same instance)
	tracklist2 := service.GetTracklist(guildID)
	if tracklist != tracklist2 {
		t.Error("Should return same tracklist instance")
	}
}

func TestAudioServiceCleanup(t *testing.T) {
	log := logger.New(logger.Config{Level: "error"})
	service := audio.NewAudioService(nil, log)

	// Cleanup should not panic
	service.Cleanup()

	// Stats should still work after cleanup
	stats := service.GetStats()
	if stats == nil {
		t.Error("Stats should work after cleanup")
	}
}

func TestAudioServiceConcurrentAccess(t *testing.T) {
	log := logger.New(logger.Config{Level: "error"})
	service := audio.NewAudioService(nil, log)

	done := make(chan bool, 100)

	// 50 goroutines accessing different guilds
	for i := 0; i < 50; i++ {
		go func(id int) {
			guildID := fmt.Sprintf("guild-%d", id)

			// Get tracklist
			tracklist := service.GetTracklist(guildID)
			if tracklist == nil {
				t.Error("Failed to get tracklist")
			}

			// Check states
			_ = service.IsConnected(guildID)
			_ = service.IsPlaying(guildID)
			_ = service.GetCurrentSong(guildID)

			done <- true
		}(i)
	}

	// 50 goroutines reading stats
	for i := 0; i < 50; i++ {
		go func() {
			stats := service.GetStats()
			if stats == nil {
				t.Error("Failed to get stats")
			}
			done <- true
		}()
	}

	// Wait for all
	timeout := time.After(5 * time.Second)
	for i := 0; i < 100; i++ {
		select {
		case <-done:
			// OK
		case <-timeout:
			t.Fatal("Test timeout")
		}
	}
}
