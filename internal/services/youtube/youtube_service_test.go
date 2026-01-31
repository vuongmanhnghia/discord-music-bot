package youtube

import (
	"testing"

	"github.com/vuongmanhnghia/discord-music-bot/pkg/logger"
)

func TestNewService(t *testing.T) {
	log := logger.New(logger.Config{Level: "info"})

	svc, err := NewService(log)
	if err != nil {
		t.Skipf("yt-dlp not installed: %v", err)
		return
	}

	if svc == nil {
		t.Fatal("Expected service to be created")
	}

	if svc.cache == nil {
		t.Error("Expected cache to be initialized")
	}

	if svc.ytDlpPath == "" {
		t.Error("Expected yt-dlp path to be set")
	}
}

func TestIsYouTubeURL(t *testing.T) {
	tests := []struct {
		url      string
		expected bool
	}{
		{"https://www.youtube.com/watch?v=dQw4w9WgXcQ", true},
		{"https://youtu.be/dQw4w9WgXcQ", true},
		{"https://www.youtube.com/playlist?list=PLtest", true},
		{"https://spotify.com/track/123", false},
		{"https://example.com", false},
		{"not a url", false},
	}

	for _, tt := range tests {
		result := IsYouTubeURL(tt.url)
		if result != tt.expected {
			t.Errorf("IsYouTubeURL(%s) = %v, expected %v", tt.url, result, tt.expected)
		}
	}
}

func TestIsPlaylistURL(t *testing.T) {
	tests := []struct {
		name     string
		url      string
		expected bool
	}{
		{
			name:     "Actual playlist URL",
			url:      "https://www.youtube.com/playlist?list=PLtest",
			expected: true,
		},
		{
			name:     "Video URL with regular list parameter (should extract single video)",
			url:      "https://www.youtube.com/watch?v=123&list=PLtest",
			expected: false,
		},
		{
			name:     "Video URL with YouTube Radio list parameter",
			url:      "https://www.youtube.com/watch?v=D8OCBS2UZOk&list=RDD8OCBS2UZOk&start_radio=1",
			expected: false,
		},
		{
			name:     "Single video URL without list",
			url:      "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
			expected: false,
		},
		{
			name:     "Short YouTube URL",
			url:      "https://youtu.be/dQw4w9WgXcQ",
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := IsPlaylistURL(tt.url)
			if result != tt.expected {
				t.Errorf("IsPlaylistURL(%s) = %v, expected %v", tt.url, result, tt.expected)
			}
		})
	}
}

func TestToSongMetadata(t *testing.T) {
	info := &YouTubeInfo{
		ID:         "dQw4w9WgXcQ",
		Title:      "Rick Astley - Never Gonna Give You Up",
		Duration:   213.0,
		Uploader:   "Rick Astley",
		Thumbnail:  "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
		WebpageURL: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
	}

	metadata := info.ToSongMetadata()

	if metadata.Title != info.Title {
		t.Errorf("Expected title %s, got %s", info.Title, metadata.Title)
	}

	if metadata.Duration != int(info.Duration) {
		t.Errorf("Expected duration %d, got %d", int(info.Duration), metadata.Duration)
	}

	if metadata.Thumbnail != info.Thumbnail {
		t.Errorf("Expected thumbnail %s, got %s", info.Thumbnail, metadata.Thumbnail)
	}

	if metadata.Uploader != info.Uploader {
		t.Errorf("Expected uploader %s, got %s", info.Uploader, metadata.Uploader)
	}
}

func TestServiceCacheOperations(t *testing.T) {
	log := logger.New(logger.Config{Level: "error"})

	svc, err := NewService(log)
	if err != nil {
		t.Skipf("yt-dlp not installed: %v", err)
		return
	}

	// Test cache stats
	hits, misses, evictions, size := svc.CacheStats()
	if hits != 0 || misses != 0 || evictions != 0 || size != 0 {
		t.Error("Expected empty cache initially")
	}

	// Test cache clear
	svc.ClearCache()

	hits, misses, evictions, size = svc.CacheStats()
	if size != 0 {
		t.Error("Expected cache to be empty after clear")
	}
}

// Integration tests (require yt-dlp and network)
func TestExtractInfoIntegration(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test")
	}

	log := logger.New(logger.Config{Level: "error"})

	svc, err := NewService(log)
	if err != nil {
		t.Skipf("yt-dlp not installed: %v", err)
		return
	}

	// Use a known stable video (Rick Roll)
	url := "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

	info, err := svc.ExtractInfo(url)
	if err != nil {
		t.Fatalf("Failed to extract info: %v", err)
	}

	if info.ID == "" {
		t.Error("Expected video ID to be set")
	}

	if info.Title == "" {
		t.Error("Expected title to be set")
	}

	if info.Duration <= 0 {
		t.Error("Expected positive duration")
	}

	// Test cache hit
	info2, err := svc.ExtractInfo(url)
	if err != nil {
		t.Fatalf("Failed to extract info from cache: %v", err)
	}

	if info2.ID != info.ID {
		t.Error("Expected cached result to match")
	}

	hits, _, _, _ := svc.CacheStats()
	if hits != 1 {
		t.Errorf("Expected 1 cache hit, got %d", hits)
	}
}

func TestGetStreamURLIntegration(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test")
	}

	log := logger.New(logger.Config{Level: "error"})

	svc, err := NewService(log)
	if err != nil {
		t.Skipf("yt-dlp not installed: %v", err)
		return
	}

	videoID := "dQw4w9WgXcQ"

	streamURL, err := svc.GetStreamURL(videoID)
	if err != nil {
		t.Fatalf("Failed to get stream URL: %v", err)
	}

	if streamURL == "" {
		t.Error("Expected non-empty stream URL")
	}

	// Should start with https://
	if len(streamURL) < 8 || streamURL[:8] != "https://" {
		t.Error("Expected HTTPS URL")
	}
}

func TestSearchIntegration(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test")
	}

	log := logger.New(logger.Config{Level: "error"})

	svc, err := NewService(log)
	if err != nil {
		t.Skipf("yt-dlp not installed: %v", err)
		return
	}

	results, err := svc.Search("never gonna give you up", 3)
	if err != nil {
		t.Fatalf("Failed to search: %v", err)
	}

	if len(results) == 0 {
		t.Error("Expected at least one search result")
	}

	if len(results) > 3 {
		t.Errorf("Expected max 3 results, got %d", len(results))
	}

	// Check first result
	if results[0].ID == "" {
		t.Error("Expected video ID in search result")
	}

	if results[0].Title == "" {
		t.Error("Expected title in search result")
	}
}
