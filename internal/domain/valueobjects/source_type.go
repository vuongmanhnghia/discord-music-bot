package valueobjects

// SourceType represents the type of media source
type SourceType string

const (
	SourceTypeYouTube         SourceType = "youtube"
	SourceTypeYouTubePlaylist SourceType = "youtube_playlist"
	SourceTypeSpotify         SourceType = "spotify"
	SourceTypeSoundCloud      SourceType = "soundcloud"
	SourceTypeURL             SourceType = "url"
	SourceTypeSearch          SourceType = "search"
)

// String returns the string representation
func (s SourceType) String() string {
	return string(s)
}

// IsValid checks if the source type is valid
func (s SourceType) IsValid() bool {
	switch s {
	case SourceTypeYouTube, SourceTypeYouTubePlaylist, SourceTypeSpotify,
		SourceTypeSoundCloud, SourceTypeURL, SourceTypeSearch:
		return true
	}
	return false
}
