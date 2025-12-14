package entities_test

import (
	"testing"

	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
)

func TestTracklistCreation(t *testing.T) {
	tracklist := entities.NewTracklist("123456789")

	if tracklist.Size() != 0 {
		t.Error("New tracklist should be empty")
	}

	if tracklist.CurrentSong() != nil {
		t.Error("Current song should be nil for empty tracklist")
	}
}

func TestTracklistAddSong(t *testing.T) {
	tracklist := entities.NewTracklist("123456789")

	song1 := entities.NewSong("url1", valueobjects.SourceTypeYouTube, "User1", "123456789")
	song2 := entities.NewSong("url2", valueobjects.SourceTypeYouTube, "User2", "123456789")

	pos1 := tracklist.AddSong(song1)
	pos2 := tracklist.AddSong(song2)

	if pos1 != 1 || pos2 != 2 {
		t.Errorf("Expected positions 1 and 2, got %d and %d", pos1, pos2)
	}

	if tracklist.Size() != 2 {
		t.Errorf("Expected size 2, got %d", tracklist.Size())
	}
}

func TestTracklistNavigation(t *testing.T) {
	tracklist := entities.NewTracklist("123456789")

	song1 := entities.NewSong("url1", valueobjects.SourceTypeYouTube, "User1", "123456789")
	song2 := entities.NewSong("url2", valueobjects.SourceTypeYouTube, "User2", "123456789")
	song3 := entities.NewSong("url3", valueobjects.SourceTypeYouTube, "User3", "123456789")

	tracklist.AddSong(song1)
	tracklist.AddSong(song2)
	tracklist.AddSong(song3)

	// Test current song
	current := tracklist.CurrentSong()
	if current == nil || current.ID != song1.ID {
		t.Error("Current song should be song1")
	}

	// Test next song
	next := tracklist.NextSong()
	if next == nil || next.ID != song2.ID {
		t.Error("Next song should be song2")
	}

	// Test current after next
	current = tracklist.CurrentSong()
	if current == nil || current.ID != song2.ID {
		t.Error("Current song should be song2 after next")
	}

	// Test next again
	next = tracklist.NextSong()
	if next == nil || next.ID != song3.ID {
		t.Error("Next song should be song3")
	}
}

func TestTracklistRepeatModes(t *testing.T) {
	tracklist := entities.NewTracklist("123456789")

	song1 := entities.NewSong("url1", valueobjects.SourceTypeYouTube, "User1", "123456789")
	song2 := entities.NewSong("url2", valueobjects.SourceTypeYouTube, "User2", "123456789")

	tracklist.AddSong(song1)
	tracklist.AddSong(song2)

	// Test queue repeat mode (default)
	tracklist.NextSong()         // Move to song2
	next := tracklist.NextSong() // Should loop back to song1
	if next == nil || next.ID != song1.ID {
		t.Error("Queue repeat should loop back to first song")
	}

	// Test track repeat mode
	tracklist.SetRepeatMode(entities.RepeatModeTrack)
	current := tracklist.CurrentSong()
	next = tracklist.NextSong()
	if next == nil || next.ID != current.ID {
		t.Error("Track repeat should stay on same song")
	}

	// Test no repeat mode
	tracklist.SetRepeatMode(entities.RepeatModeNone)
	tracklist.NextSong()        // Move to song2
	next = tracklist.NextSong() // Should return nil at end
	if next != nil {
		t.Error("No repeat mode should return nil at end")
	}
}

func TestTracklistSkipToPosition(t *testing.T) {
	tracklist := entities.NewTracklist("123456789")

	song1 := entities.NewSong("url1", valueobjects.SourceTypeYouTube, "User1", "123456789")
	song2 := entities.NewSong("url2", valueobjects.SourceTypeYouTube, "User2", "123456789")
	song3 := entities.NewSong("url3", valueobjects.SourceTypeYouTube, "User3", "123456789")

	tracklist.AddSong(song1)
	tracklist.AddSong(song2)
	tracklist.AddSong(song3)

	// Skip to position 3 (1-indexed)
	skipped := tracklist.SkipToPosition(3)
	if skipped == nil || skipped.ID != song3.ID {
		t.Error("Should skip to song3")
	}

	current := tracklist.CurrentSong()
	if current == nil || current.ID != song3.ID {
		t.Error("Current song should be song3 after skip")
	}
}

func TestTracklistRemoveSong(t *testing.T) {
	tracklist := entities.NewTracklist("123456789")

	song1 := entities.NewSong("url1", valueobjects.SourceTypeYouTube, "User1", "123456789")
	song2 := entities.NewSong("url2", valueobjects.SourceTypeYouTube, "User2", "123456789")
	song3 := entities.NewSong("url3", valueobjects.SourceTypeYouTube, "User3", "123456789")

	tracklist.AddSong(song1)
	tracklist.AddSong(song2)
	tracklist.AddSong(song3)

	// Remove song at position 2
	removed := tracklist.RemoveSong(2)
	if !removed {
		t.Error("Should successfully remove song")
	}

	if tracklist.Size() != 2 {
		t.Errorf("Expected size 2 after removal, got %d", tracklist.Size())
	}
}

func TestTracklistClear(t *testing.T) {
	tracklist := entities.NewTracklist("123456789")

	song1 := entities.NewSong("url1", valueobjects.SourceTypeYouTube, "User1", "123456789")
	song2 := entities.NewSong("url2", valueobjects.SourceTypeYouTube, "User2", "123456789")

	tracklist.AddSong(song1)
	tracklist.AddSong(song2)

	tracklist.Clear()

	if tracklist.Size() != 0 {
		t.Error("Tracklist should be empty after clear")
	}

	if tracklist.CurrentSong() != nil {
		t.Error("Current song should be nil after clear")
	}
}

func TestTracklistThreadSafety(t *testing.T) {
	tracklist := entities.NewTracklist("123456789")

	// Add initial songs
	for i := 0; i < 10; i++ {
		song := entities.NewSong("url", valueobjects.SourceTypeYouTube, "User", "123456789")
		tracklist.AddSong(song)
	}

	done := make(chan bool, 100)

	// 50 goroutines reading
	for i := 0; i < 50; i++ {
		go func() {
			_ = tracklist.CurrentSong()
			_ = tracklist.Size()
			_ = tracklist.GetUpcoming(5)
			done <- true
		}()
	}

	// 50 goroutines writing
	for i := 0; i < 50; i++ {
		go func() {
			song := entities.NewSong("url", valueobjects.SourceTypeYouTube, "User", "123456789")
			tracklist.AddSong(song)
			tracklist.NextSong()
			done <- true
		}()
	}

	// Wait for all goroutines
	for i := 0; i < 100; i++ {
		<-done
	}

	// Should not panic
	if tracklist.Size() < 10 {
		t.Error("Tracklist should have at least 10 songs after concurrent operations")
	}
}
