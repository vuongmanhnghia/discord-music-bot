package spotify

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"

	"github.com/vuongmanhnghia/discord-music-bot/pkg/logger"
)

var (
	// Regex patterns for Spotify URLs
	trackRegex    = regexp.MustCompile(`spotify\.com/track/([a-zA-Z0-9]+)`)
	playlistRegex = regexp.MustCompile(`spotify\.com/playlist/([a-zA-Z0-9]+)`)
	albumRegex    = regexp.MustCompile(`spotify\.com/album/([a-zA-Z0-9]+)`)
)

// Service handles Spotify API operations
type Service struct {
	clientID     string
	clientSecret string
	accessToken  string
	tokenExpiry  time.Time
	logger       *logger.Logger
	httpClient   *http.Client
}

// Track represents a Spotify track
type Track struct {
	ID              string   `json:"id"`
	Name            string   `json:"name"`
	Artists         []Artist `json:"artists"`
	Album           Album    `json:"album"`
	DurationMs      int      `json:"duration_ms"`
	ExternalIDs     ExternalIDs `json:"external_ids"`
}

// ExternalIDs represents external identifiers for a track
type ExternalIDs struct {
	ISRC string `json:"isrc"`
}

// Artist represents a Spotify artist
type Artist struct {
	Name string `json:"name"`
}

// Album represents a Spotify album
type Album struct {
	Name string `json:"name"`
}

// PlaylistTracksResponse represents Spotify playlist tracks response
type PlaylistTracksResponse struct {
	Items []struct {
		Track Track `json:"track"`
	} `json:"items"`
	Next string `json:"next"`
}

// AlbumTracksResponse represents Spotify album tracks response
type AlbumTracksResponse struct {
	Items []Track `json:"items"`
	Next  string  `json:"next"`
}

// TokenResponse represents Spotify token response
type TokenResponse struct {
	AccessToken string `json:"access_token"`
	TokenType   string `json:"token_type"`
	ExpiresIn   int    `json:"expires_in"`
}

// NewService creates a new Spotify service
func NewService(clientID, clientSecret string, log *logger.Logger) (*Service, error) {
	if clientID == "" || clientSecret == "" {
		return nil, fmt.Errorf("spotify credentials not provided")
	}

	s := &Service{
		clientID:     clientID,
		clientSecret: clientSecret,
		logger:       log,
		httpClient:   &http.Client{Timeout: 10 * time.Second},
	}

	// Get initial access token
	if err := s.refreshAccessToken(); err != nil {
		return nil, fmt.Errorf("failed to get Spotify access token: %w", err)
	}

	log.Info("Spotify service initialized")
	return s, nil
}

// refreshAccessToken gets a new access token from Spotify
func (s *Service) refreshAccessToken() error {
	data := url.Values{}
	data.Set("grant_type", "client_credentials")

	req, err := http.NewRequest("POST", "https://accounts.spotify.com/api/token", strings.NewReader(data.Encode()))
	if err != nil {
		return err
	}

	auth := base64.StdEncoding.EncodeToString([]byte(s.clientID + ":" + s.clientSecret))
	req.Header.Set("Authorization", "Basic "+auth)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("spotify auth failed: %s - %s", resp.Status, string(body))
	}

	var tokenResp TokenResponse
	if err := json.NewDecoder(resp.Body).Decode(&tokenResp); err != nil {
		return err
	}

	s.accessToken = tokenResp.AccessToken
	s.tokenExpiry = time.Now().Add(time.Duration(tokenResp.ExpiresIn) * time.Second)

	s.logger.Debug("Spotify access token refreshed")
	return nil
}

// ensureValidToken ensures we have a valid access token
func (s *Service) ensureValidToken() error {
	if time.Now().After(s.tokenExpiry.Add(-5 * time.Minute)) {
		return s.refreshAccessToken()
	}
	return nil
}

// makeRequest makes an authenticated request to Spotify API
func (s *Service) makeRequest(endpoint string) ([]byte, error) {
	if err := s.ensureValidToken(); err != nil {
		return nil, err
	}

	req, err := http.NewRequest("GET", endpoint, nil)
	if err != nil {
		return nil, err
	}

	req.Header.Set("Authorization", "Bearer "+s.accessToken)

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("spotify API error: %s - %s", resp.Status, string(body))
	}

	return io.ReadAll(resp.Body)
}

// GetTrack gets track information by ID
func (s *Service) GetTrack(trackID string) (*Track, error) {
	endpoint := fmt.Sprintf("https://api.spotify.com/v1/tracks/%s", trackID)

	body, err := s.makeRequest(endpoint)
	if err != nil {
		return nil, err
	}

	var track Track
	if err := json.Unmarshal(body, &track); err != nil {
		return nil, err
	}

	return &track, nil
}

// GetPlaylistTracks gets all tracks from a playlist
func (s *Service) GetPlaylistTracks(playlistID string) ([]Track, error) {
	var allTracks []Track
	endpoint := fmt.Sprintf("https://api.spotify.com/v1/playlists/%s/tracks", playlistID)

	for endpoint != "" {
		body, err := s.makeRequest(endpoint)
		if err != nil {
			return nil, err
		}

		var resp PlaylistTracksResponse
		if err := json.Unmarshal(body, &resp); err != nil {
			return nil, err
		}

		for _, item := range resp.Items {
			allTracks = append(allTracks, item.Track)
		}

		endpoint = resp.Next
	}

	return allTracks, nil
}

// GetAlbumTracks gets all tracks from an album
func (s *Service) GetAlbumTracks(albumID string) ([]Track, error) {
	var allTracks []Track
	endpoint := fmt.Sprintf("https://api.spotify.com/v1/albums/%s/tracks", albumID)

	for endpoint != "" {
		body, err := s.makeRequest(endpoint)
		if err != nil {
			return nil, err
		}

		var resp AlbumTracksResponse
		if err := json.Unmarshal(body, &resp); err != nil {
			return nil, err
		}

		allTracks = append(allTracks, resp.Items...)
		endpoint = resp.Next
	}

	return allTracks, nil
}

// ToSearchQuery converts a track to a YouTube search query
func (t *Track) ToSearchQuery() string {
	if len(t.Artists) == 0 {
		return t.Name
	}
	// Format: "Artist - Track Name"
	return fmt.Sprintf("%s - %s", t.Artists[0].Name, t.Name)
}

// ToDetailedSearchQuery converts a track to a detailed YouTube search query with album info
func (t *Track) ToDetailedSearchQuery() string {
	if len(t.Artists) == 0 {
		return t.Name
	}
	// Format: "Artist - Track Name Album Name official audio"
	// Adding "official audio" helps find official uploads
	return fmt.Sprintf("%s - %s %s official audio", t.Artists[0].Name, t.Name, t.Album.Name)
}

// GetISRC returns the ISRC code if available
func (t *Track) GetISRC() string {
	return t.ExternalIDs.ISRC
}

// GetDurationSeconds returns duration in seconds
func (t *Track) GetDurationSeconds() int {
	return t.DurationMs / 1000
}

// IsSpotifyURL checks if URL is a Spotify URL
func IsSpotifyURL(urlStr string) bool {
	return strings.Contains(urlStr, "spotify.com/")
}

// ParseSpotifyURL parses a Spotify URL and returns the type and ID
func ParseSpotifyURL(urlStr string) (urlType, id string, err error) {
	if matches := trackRegex.FindStringSubmatch(urlStr); len(matches) > 1 {
		return "track", matches[1], nil
	}
	if matches := playlistRegex.FindStringSubmatch(urlStr); len(matches) > 1 {
		return "playlist", matches[1], nil
	}
	if matches := albumRegex.FindStringSubmatch(urlStr); len(matches) > 1 {
		return "album", matches[1], nil
	}
	return "", "", fmt.Errorf("invalid Spotify URL")
}
