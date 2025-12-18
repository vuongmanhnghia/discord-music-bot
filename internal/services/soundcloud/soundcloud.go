package soundcloud

import (
	"strings"
)

// IsSoundCloudURL checks if the given URL is a SoundCloud URL
func IsSoundCloudURL(url string) bool {
	return strings.Contains(url, "soundcloud.com/")
}

// IsPlaylistURL checks if the URL is a SoundCloud playlist/set
func IsPlaylistURL(url string) bool {
	return IsSoundCloudURL(url) && strings.Contains(url, "/sets/")
}

// IsTrackURL checks if the URL is a single SoundCloud track
func IsTrackURL(url string) bool {
	return IsSoundCloudURL(url) && !IsPlaylistURL(url)
}
