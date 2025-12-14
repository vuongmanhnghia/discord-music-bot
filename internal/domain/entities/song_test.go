package entities_test

import (
	"testing"
	"time"

	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
)

func TestSongCreation(t *testing.T) {
	song := entities.NewSong(
		"https://www.youtube.com/watch?v=test",
		valueobjects.SourceTypeYouTube,
		"TestUser#1234",
		"123456789",
	)

	if song.ID == "" {
		t.Error("Song ID should not be empty")
	}

	if song.GetStatus() != valueobjects.SongStatusPending {
		t.Errorf("Expected status PENDING, got %s", song.GetStatus())
	}

	if song.IsReady() {
		t.Error("Song should not be ready initially")
	}
}

func TestSongStateTransitions(t *testing.T) {
	song := entities.NewSong(
		"https://www.youtube.com/watch?v=test",
		valueobjects.SourceTypeYouTube,
		"TestUser#1234",
		"123456789",
	)

	// Test PENDING -> PROCESSING
	song.MarkProcessing()
	if song.GetStatus() != valueobjects.SongStatusProcessing {
		t.Error("Song should be in PROCESSING state")
	}

	// Test PROCESSING -> READY
	metadata := &valueobjects.SongMetadata{
		Title:    "Test Song",
		Artist:   "Test Artist",
		Duration: 180,
	}
	song.MarkReady(metadata, "https://stream.url")

	if song.GetStatus() != valueobjects.SongStatusReady {
		t.Error("Song should be in READY state")
	}

	if !song.IsReady() {
		t.Error("Song should be ready")
	}

	if song.GetStreamURL() == "" {
		t.Error("Stream URL should not be empty")
	}
}

func TestSongMarkFailed(t *testing.T) {
	song := entities.NewSong(
		"https://www.youtube.com/watch?v=test",
		valueobjects.SourceTypeYouTube,
		"TestUser#1234",
		"123456789",
	)

	song.MarkProcessing()
	song.MarkFailed("Test error message")

	if song.GetStatus() != valueobjects.SongStatusFailed {
		t.Error("Song should be in FAILED state")
	}
}

func TestSongStreamExpiration(t *testing.T) {
	song := entities.NewSong(
		"https://www.youtube.com/watch?v=test",
		valueobjects.SourceTypeYouTube,
		"TestUser#1234",
		"123456789",
	)

	metadata := &valueobjects.SongMetadata{
		Title:    "Test Song",
		Duration: 180,
	}
	song.MarkReady(metadata, "https://stream.url")

	// Should not be expired immediately
	if song.IsStreamExpired(5 * time.Hour) {
		t.Error("Stream should not be expired")
	}

	// Refresh stream URL
	song.RefreshStreamURL("https://new-stream.url")
	if song.GetStreamURL() != "https://new-stream.url" {
		t.Error("Stream URL should be updated")
	}
}

func TestSongThreadSafety(t *testing.T) {
	song := entities.NewSong(
		"https://www.youtube.com/watch?v=test",
		valueobjects.SourceTypeYouTube,
		"TestUser#1234",
		"123456789",
	)

	// Test concurrent reads and writes
	done := make(chan bool, 100)

	// 50 goroutines reading
	for i := 0; i < 50; i++ {
		go func() {
			_ = song.IsReady()
			_ = song.GetStatus()
			_ = song.DisplayName()
			done <- true
		}()
	}

	// 50 goroutines writing
	for i := 0; i < 50; i++ {
		go func() {
			song.MarkProcessing()
			metadata := &valueobjects.SongMetadata{
				Title:    "Test Song",
				Duration: 180,
			}
			song.MarkReady(metadata, "https://stream.url")
			done <- true
		}()
	}

	// Wait for all goroutines
	for i := 0; i < 100; i++ {
		<-done
	}

	// Should not panic and should be in a valid state
	if !song.IsReady() {
		t.Error("Song should be ready after concurrent operations")
	}
}
