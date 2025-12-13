package youtube

import (
	"encoding/json"
	"errors"
	"fmt"
	"os/exec"
	"strings"
	"time"

	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
	"github.com/vuongmanhnghia/discord-music-bot/internal/utils"
	"github.com/vuongmanhnghia/discord-music-bot/pkg/logger"
)

var (
	// ErrYtDlpNotFound is returned when yt-dlp is not installed
	ErrYtDlpNotFound = errors.New("yt-dlp not found in PATH")
	// ErrExtractionFailed is returned when video extraction fails
	ErrExtractionFailed = errors.New("failed to extract video information")
	// ErrInvalidURL is returned when the URL is invalid
	ErrInvalidURL = errors.New("invalid YouTube URL")
)

// YouTubeInfo represents extracted YouTube video information
type YouTubeInfo struct {
	ID         string        `json:"id"`
	Title      string        `json:"title"`
	Duration   int           `json:"duration"`
	Uploader   string        `json:"uploader"`
	Thumbnail  string        `json:"thumbnail"`
	WebpageURL string        `json:"webpage_url"`
	StreamURL  string        `json:"url,omitempty"`
	Formats    []Format      `json:"formats,omitempty"`
	Entries    []YouTubeInfo `json:"entries,omitempty"` // For playlists
	Type       string        `json:"_type,omitempty"`   // "video", "playlist", etc
}

// IsPlaylist checks if this is a playlist
func (info *YouTubeInfo) IsPlaylist() bool {
	return info.Type == "playlist"
}

// Format represents an available stream format
type Format struct {
	FormatID   string  `json:"format_id"`
	Ext        string  `json:"ext"`
	URL        string  `json:"url"`
	AudioCodec string  `json:"acodec"`
	Quality    float64 `json:"quality"` // Can be float like 2.0
	ABR        float64 `json:"abr"`     // Audio bitrate
}

// Service handles YouTube operations
type Service struct {
	cache     *utils.SmartCache
	logger    *logger.Logger
	ytDlpPath string
}

// NewService creates a new YouTube service
func NewService(log *logger.Logger) (*Service, error) {
	// Check if yt-dlp is available
	ytDlpPath, err := exec.LookPath("yt-dlp")
	if err != nil {
		return nil, fmt.Errorf("%w: please install yt-dlp", ErrYtDlpNotFound)
	}

	// Create cache with 5-minute TTL for stream URLs (they expire)
	cache := utils.NewSmartCache(500, 5*time.Minute)

	log.WithField("ytdlp_path", ytDlpPath).Info("YouTube service initialized")

	return &Service{
		cache:     cache,
		logger:    log,
		ytDlpPath: ytDlpPath,
	}, nil
}

// ExtractInfo extracts video/playlist information from URL
func (s *Service) ExtractInfo(url string) (*YouTubeInfo, error) {
	// Check cache first
	if cached, ok := s.cache.Get(url); ok {
		s.logger.Debug("Cache hit for URL")
		return cached.(*YouTubeInfo), nil
	}

	s.logger.WithField("url", url).Info("Extracting YouTube info...")

	// Build yt-dlp command
	args := []string{
		"--dump-json",
		"--no-playlist", // Handle playlists separately
		"--format", "bestaudio/best",
		"--no-check-certificate",
		"--geo-bypass",
		url,
	}

	cmd := exec.Command(s.ytDlpPath, args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		s.logger.WithError(err).WithField("output", string(output)).Error("yt-dlp extraction failed")
		return nil, fmt.Errorf("%w: %v", ErrExtractionFailed, err)
	}

	var info YouTubeInfo
	if err := json.Unmarshal(output, &info); err != nil {
		s.logger.WithError(err).Error("Failed to parse yt-dlp output")
		return nil, fmt.Errorf("failed to parse video info: %w", err)
	}

	// Cache the result
	s.cache.Set(url, &info)

	s.logger.WithFields(map[string]interface{}{
		"title":    info.Title,
		"duration": info.Duration,
	}).Info("✅ Successfully extracted video info")

	return &info, nil
}

// ExtractPlaylist extracts all videos from a playlist
func (s *Service) ExtractPlaylist(url string) ([]YouTubeInfo, error) {
	s.logger.WithField("url", url).Info("Extracting playlist...")

	// Build yt-dlp command for playlist
	args := []string{
		"--dump-json",
		"--flat-playlist", // Fast extraction
		"--no-check-certificate",
		"--geo-bypass",
		url,
	}

	cmd := exec.Command(s.ytDlpPath, args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		s.logger.WithError(err).Error("Playlist extraction failed")
		return nil, fmt.Errorf("%w: %v", ErrExtractionFailed, err)
	}

	// Parse multiple JSON objects (one per line)
	var videos []YouTubeInfo
	lines := strings.Split(string(output), "\n")
	for _, line := range lines {
		if strings.TrimSpace(line) == "" {
			continue
		}

		var info YouTubeInfo
		if err := json.Unmarshal([]byte(line), &info); err != nil {
			s.logger.WithError(err).Warn("Failed to parse playlist entry")
			continue
		}
		videos = append(videos, info)
	}

	s.logger.WithField("count", len(videos)).Info("✅ Successfully extracted playlist")
	return videos, nil
}

// Search searches YouTube and returns top results
func (s *Service) Search(query string, maxResults int) ([]YouTubeInfo, error) {
	if maxResults <= 0 {
		maxResults = 5
	}

	s.logger.WithFields(map[string]interface{}{
		"query":      query,
		"maxResults": maxResults,
	}).Info("Searching YouTube...")

	// Build search URL
	searchURL := fmt.Sprintf("ytsearch%d:%s", maxResults, query)

	args := []string{
		"--dump-json",
		"--no-check-certificate",
		"--geo-bypass",
		searchURL,
	}

	cmd := exec.Command(s.ytDlpPath, args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		s.logger.WithError(err).Error("Search failed")
		return nil, fmt.Errorf("search failed: %w", err)
	}

	// Parse results
	var videos []YouTubeInfo
	lines := strings.Split(string(output), "\n")
	for _, line := range lines {
		if strings.TrimSpace(line) == "" {
			continue
		}

		var info YouTubeInfo
		if err := json.Unmarshal([]byte(line), &info); err != nil {
			s.logger.WithError(err).Warn("Failed to parse search result")
			continue
		}
		videos = append(videos, info)
	}

	s.logger.WithField("results", len(videos)).Info("✅ Search completed")
	return videos, nil
}

// GetStreamURL gets the best audio stream URL for a video
func (s *Service) GetStreamURL(videoID string) (string, error) {
	// Check cache first
	cacheKey := fmt.Sprintf("stream:%s", videoID)
	if cached, ok := s.cache.Get(cacheKey); ok {
		s.logger.Debug("Cache hit for stream URL")
		return cached.(string), nil
	}

	videoURL := fmt.Sprintf("https://www.youtube.com/watch?v=%s", videoID)

	args := []string{
		"--get-url",
		"--format", "bestaudio/best",
		"--no-check-certificate",
		"--geo-bypass",
		videoURL,
	}

	cmd := exec.Command(s.ytDlpPath, args...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		s.logger.WithError(err).Error("Failed to get stream URL")
		return "", fmt.Errorf("failed to get stream URL: %w", err)
	}

	streamURL := strings.TrimSpace(string(output))
	if streamURL == "" {
		return "", errors.New("empty stream URL returned")
	}

	// Cache stream URL
	s.cache.Set(cacheKey, streamURL)

	return streamURL, nil
}

// IsPlaylistURL checks if URL is a playlist
func IsPlaylistURL(url string) bool {
	return strings.Contains(url, "playlist?list=") || strings.Contains(url, "&list=")
}

// IsYouTubeURL checks if URL is a valid YouTube URL
func IsYouTubeURL(url string) bool {
	return strings.Contains(url, "youtube.com") || strings.Contains(url, "youtu.be")
}

// ToSongMetadata converts YouTubeInfo to SongMetadata
func (info *YouTubeInfo) ToSongMetadata() *valueobjects.SongMetadata {
	return &valueobjects.SongMetadata{
		Title:     info.Title,
		Duration:  info.Duration, // Duration is in seconds
		Thumbnail: info.Thumbnail,
		Uploader:  info.Uploader,
	}
}

// CacheStats returns cache statistics
func (s *Service) CacheStats() (hits, misses, evictions int64, size int) {
	return s.cache.Stats()
}

// ClearCache clears the entire cache
func (s *Service) ClearCache() {
	s.cache.Clear()
	s.logger.Info("Cache cleared")
}
