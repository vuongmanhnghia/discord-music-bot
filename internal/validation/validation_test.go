package validation

import "testing"

func TestIsYouTubePlaylistURL(t *testing.T) {
	tests := []struct {
		name     string
		url      string
		expected bool
	}{
		{
			name:     "Actual playlist URL",
			url:      "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf",
			expected: true,
		},
		{
			name:     "Actual playlist URL with additional params",
			url:      "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf&si=abc123",
			expected: true,
		},
		{
			name:     "Video URL with autoplay list parameter (YouTube Radio)",
			url:      "https://www.youtube.com/watch?v=D8OCBS2UZOk&list=RDD8OCBS2UZOk&start_radio=1",
			expected: false,
		},
		{
			name:     "Video URL with regular list parameter",
			url:      "https://www.youtube.com/watch?v=D8OCBS2UZOk&list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf",
			expected: false,
		},
		{
			name:     "Single video URL without list parameter",
			url:      "https://www.youtube.com/watch?v=D8OCBS2UZOk",
			expected: false,
		},
		{
			name:     "Short YouTube URL",
			url:      "https://youtu.be/D8OCBS2UZOk",
			expected: false,
		},
		{
			name:     "Non-YouTube URL",
			url:      "https://soundcloud.com/artist/track",
			expected: false,
		},
		{
			name:     "Video URL with list parameter at start",
			url:      "https://www.youtube.com/watch?list=RDD8OCBS2UZOk&v=D8OCBS2UZOk",
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := IsYouTubePlaylistURL(tt.url)
			if result != tt.expected {
				t.Errorf("IsYouTubePlaylistURL(%s) = %v, expected %v", tt.url, result, tt.expected)
			}
		})
	}
}
