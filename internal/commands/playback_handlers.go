package commands

import (
	"fmt"
	"strings"

	"github.com/bwmarrin/discordgo"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
	"github.com/vuongmanhnghia/discord-music-bot/internal/services/soundcloud"
	"github.com/vuongmanhnghia/discord-music-bot/internal/services/spotify"
	"github.com/vuongmanhnghia/discord-music-bot/internal/services/youtube"
)

// handlePlay handles the play command
func (h *Handler) handlePlay(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	if err := deferResponse(s, i); err != nil {
		return err
	}

	options := i.ApplicationCommandData().Options
	query := options[0].StringValue()

	channelID, err := h.getUserVoiceChannel(s, i.GuildID, i.Member.User.ID)
	if err != nil {
		return followUpError(s, i, "You must be in a voice channel to play music")
	}

	// Check for Spotify playlist/album and use progressive loading
	if spotify.IsSpotifyURL(query) && h.spotifyService != nil {
		urlType, id, err := spotify.ParseSpotifyURL(query)
		if err == nil && (urlType == "playlist" || urlType == "album") {
			return h.handleSpotifyPlaylistPlay(s, i, urlType, id, channelID)
		}
	}

	// Resolve query to song URLs (handles single video, playlist, or search)
	songs, isPlaylist, err := h.ResolveSongURLs(query)
	if err != nil {
		return followUpError(s, i, err.Error())
	}

	// For single URL, extract metadata before adding to show proper title
	var extractedTitle string
	if !isPlaylist && len(songs) == 1 {
		songURL := songs[0].URL
		if strings.HasPrefix(songURL, "http://") || strings.HasPrefix(songURL, "https://") {
			h.logger.WithField("url", songURL).Debug("Extracting metadata for single URL")
			if info, err := h.ytService.ExtractInfo(songURL); err == nil {
				extractedTitle = info.Title
				songs[0].Title = info.Title // Update title for display
			}
		}
	}

	// Add all songs to queue
	addedCount := 0
	for _, songInfo := range songs {
		song := entities.NewSong(songInfo.URL, songInfo.SourceType, i.Member.User.ID, i.GuildID)
		if err := h.playbackService.AddSong(i.GuildID, song); err != nil {
			h.logger.WithError(err).Warn("Failed to add song")
			continue
		}
		addedCount++
	}

	if addedCount == 0 {
		return followUpError(s, i, "Failed to add any songs")
	}

	// Start playback if not already playing
	if !h.playbackService.IsPlaying(i.GuildID) {
		if err := h.playbackService.Play(i.GuildID, channelID); err != nil {
			return followUpError(s, i, fmt.Sprintf("Failed to start playback: %v", err))
		}
	}

	// Build appropriate response
	var embed *discordgo.MessageEmbed
	if isPlaylist {
		embed = NewEmbed().
			Title("📻 Playlist Added").
			Description(fmt.Sprintf("Successfully added **%d** songs to the queue", addedCount)).
			Color(ColorSuccess).
			Field("Songs Added", fmt.Sprintf("%d", addedCount), true).
			Footer("Use /queue to view the queue").
			Build()
	} else {
		displayTitle := extractedTitle
		if displayTitle == "" {
			displayTitle = songs[0].Title
		}
		if displayTitle == "" || displayTitle == songs[0].URL {
			displayTitle = query
		}
		embed = NewEmbed().
			Title("🎵 Added to Queue").
			Description(fmt.Sprintf("**%s**", displayTitle)).
			Color(ColorSuccess).
			Footer("Use /queue to view the queue").
			Build()
	}

	return followUpEmbed(s, i, embed)
}

// handleSpotifyPlaylistPlay handles Spotify playlist/album with progressive loading
func (h *Handler) handleSpotifyPlaylistPlay(s *discordgo.Session, i *discordgo.InteractionCreate, urlType, id, channelID string) error {
	h.logger.WithFields(map[string]interface{}{
		"type": urlType,
		"id":   id,
	}).Info("Using progressive loading for Spotify playlist/album")

	// Get all tracks from Spotify
	var tracks []spotify.Track
	var err error
	if urlType == "playlist" {
		tracks, err = h.spotifyService.GetPlaylistTracks(id)
	} else {
		tracks, err = h.spotifyService.GetAlbumTracks(id)
	}
	if err != nil {
		return followUpError(s, i, fmt.Sprintf("Failed to get Spotify %s: %v", urlType, err))
	}

	if len(tracks) == 0 {
		return followUpError(s, i, fmt.Sprintf("Spotify %s is empty", urlType))
	}

	// Resolve tracks progressively
	initialSongs, totalCount := h.addSpotifyTracksProgressively(i.GuildID, i.Member.User.ID, tracks, h.config.InitialLoadSize)

	if len(initialSongs) == 0 {
		return followUpError(s, i, "Failed to resolve any songs from Spotify playlist")
	}

	// Add initial songs to queue
	addedCount := 0
	for _, songInfo := range initialSongs {
		song := entities.NewSong(songInfo.URL, songInfo.SourceType, i.Member.User.ID, i.GuildID)
		if err := h.playbackService.AddSong(i.GuildID, song); err != nil {
			h.logger.WithError(err).Warn("Failed to add song")
			continue
		}
		addedCount++
	}

	if addedCount == 0 {
		return followUpError(s, i, "Failed to add any songs to queue")
	}

	// Start playback if not already playing
	if !h.playbackService.IsPlaying(i.GuildID) {
		if err := h.playbackService.Play(i.GuildID, channelID); err != nil {
			return followUpError(s, i, fmt.Sprintf("Failed to start playback: %v", err))
		}
	}

	// Build response showing progressive loading
	description := fmt.Sprintf("🎵 Playing first **%d** songs immediately\n⏳ Loading remaining **%d** songs in background...", addedCount, totalCount-addedCount)
	if totalCount == addedCount {
		description = fmt.Sprintf("✅ Successfully added **%d** songs to the queue", addedCount)
	}

	embed := NewEmbed().
		Title("📻 Spotify Playlist Added").
		Description(description).
		Color(ColorSuccess).
		Field("Total Tracks", fmt.Sprintf("%d", totalCount), true).
		Field("Playing Now", fmt.Sprintf("%d", addedCount), true).
		Footer("Use /queue to view the queue").
		Build()

	return followUpEmbed(s, i, embed)
}

// SongInfo represents a resolved song with URL, title, and source type
type SongInfo struct {
	URL        string
	Title      string
	SourceType valueobjects.SourceType
}

// ResolveSongURLs resolves a query (URL/search) into a list of song URLs and titles
// Returns: list of (URL, title) pairs and whether it was a playlist
func (h *Handler) ResolveSongURLs(query string) ([]SongInfo, bool, error) {
	// Check if query is a Spotify URL
	if spotify.IsSpotifyURL(query) {
		if h.spotifyService == nil {
			return nil, false, fmt.Errorf("Spotify support is not enabled. Please contact the bot owner to add Spotify credentials")
		}

		urlType, id, err := spotify.ParseSpotifyURL(query)
		if err != nil {
			return nil, false, fmt.Errorf("invalid Spotify URL: %w", err)
		}

		h.logger.WithFields(map[string]interface{}{
			"type": urlType,
			"id":   id,
		}).Info("Detected Spotify URL")

		var tracks []spotify.Track
		isPlaylist := false

		switch urlType {
		case "track":
			track, err := h.spotifyService.GetTrack(id)
			if err != nil {
				return nil, false, fmt.Errorf("failed to get Spotify track: %w", err)
			}
			tracks = []spotify.Track{*track}

		case "playlist":
			var err error
			tracks, err = h.spotifyService.GetPlaylistTracks(id)
			if err != nil {
				return nil, false, fmt.Errorf("failed to get Spotify playlist: %w", err)
			}
			isPlaylist = true

		case "album":
			var err error
			tracks, err = h.spotifyService.GetAlbumTracks(id)
			if err != nil {
				return nil, false, fmt.Errorf("failed to get Spotify album: %w", err)
			}
			isPlaylist = true

		default:
			return nil, false, fmt.Errorf("unsupported Spotify URL type: %s", urlType)
		}

		if len(tracks) == 0 {
			return nil, false, fmt.Errorf("no tracks found in Spotify content")
		}

		// Search YouTube for each Spotify track
		songs := make([]SongInfo, 0, len(tracks))
		for _, track := range tracks {
			var videoID string
			var found bool
			spotifyDuration := track.GetDurationSeconds()

			// Strategy 1: Try ISRC search first (most accurate)
			if isrc := track.GetISRC(); isrc != "" {
				h.logger.WithFields(map[string]interface{}{
					"track": track.Name,
					"isrc":  isrc,
				}).Debug("Trying ISRC search")

				if info, err := h.ytService.SearchByISRC(isrc); err == nil {
					// Verify duration (±5 seconds tolerance)
					if absFloat(info.Duration-float64(spotifyDuration)) <= 5 {
						videoID = info.ID
						found = true
						h.logger.WithField("track", track.Name).Info("✅ Found by ISRC with duration match")
					} else {
						h.logger.WithFields(map[string]interface{}{
							"track":            track.Name,
							"spotify_duration": spotifyDuration,
							"youtube_duration": info.Duration,
						}).Warn("ISRC match but duration mismatch, trying other methods")
					}
				}
			}

			// Strategy 2: Try detailed search with album info
			if !found {
				detailedQuery := track.ToDetailedSearchQuery()
				h.logger.WithField("query", detailedQuery).Debug("Trying detailed search")

				results, err := h.ytService.Search(detailedQuery, 3) // Get top 3 results
				if err == nil && len(results) > 0 {
					// Find best match by duration
					bestMatch := findBestDurationMatch(results, spotifyDuration)
					if bestMatch != nil {
						videoID = bestMatch.ID
						found = true
						h.logger.WithField("track", track.Name).Info("✅ Found by detailed search")
					}
				}
			}

			// Strategy 3: Fall back to simple search
			if !found {
				simpleQuery := track.ToSearchQuery()
				h.logger.WithField("query", simpleQuery).Debug("Trying simple search")

				results, err := h.ytService.Search(simpleQuery, 3)
				if err != nil {
					h.logger.WithError(err).WithField("track", track.Name).Warn("All search methods failed")
					continue
				}

				if len(results) == 0 {
					h.logger.WithField("track", track.Name).Warn("No YouTube results found")
					continue
				}

				// Find best match by duration
				bestMatch := findBestDurationMatch(results, spotifyDuration)
				if bestMatch != nil {
					videoID = bestMatch.ID
					found = true
					h.logger.WithField("track", track.Name).Info("✅ Found by simple search")
				} else {
					// Last resort: use first result
					videoID = results[0].ID
					h.logger.WithField("track", track.Name).Warn("⚠️ Using first result (no duration match)")
				}
			}

			if found || videoID != "" {
				songs = append(songs, SongInfo{
					URL:        fmt.Sprintf("https://www.youtube.com/watch?v=%s", videoID),
					Title:      track.ToSearchQuery(),
					SourceType: valueobjects.SourceTypeYouTube,
				})
			}
		}

		if len(songs) == 0 {
			return nil, false, fmt.Errorf("could not find any YouTube videos for Spotify tracks")
		}

		return songs, isPlaylist, nil
	}

	// Check if query is a SoundCloud URL
	if soundcloud.IsSoundCloudURL(query) {
		h.logger.WithField("url", query).Info("Detected SoundCloud URL")

		// SoundCloud playlists/sets
		if soundcloud.IsPlaylistURL(query) {
			h.logger.Info("Extracting SoundCloud playlist")
			videos, err := h.ytService.ExtractPlaylist(query)
			if err != nil {
				return nil, false, fmt.Errorf("failed to extract SoundCloud playlist: %w", err)
			}

			if len(videos) == 0 {
				return nil, false, fmt.Errorf("SoundCloud playlist is empty or invalid")
			}

			songs := make([]SongInfo, 0, len(videos))
			for _, video := range videos {
				// For SoundCloud, the ID field from yt-dlp contains the full track URL
				trackURL := video.ID
				if !strings.HasPrefix(trackURL, "http") {
					// If ID is not a URL, construct SoundCloud URL
					trackURL = fmt.Sprintf("https://soundcloud.com/%s", video.ID)
				}

				songs = append(songs, SongInfo{
					URL:        trackURL,
					Title:      video.Title,
					SourceType: valueobjects.SourceTypeYouTube,
				})
			}

			return songs, true, nil
		}

		// Single SoundCloud track - return the URL directly (yt-dlp will handle it)
		return []SongInfo{{
			URL:        query,
			Title:      query, // Will be updated after extraction
			SourceType: valueobjects.SourceTypeYouTube,
		}}, false, nil
	}

	// Check if query is a YouTube playlist URL
	if youtube.IsPlaylistURL(query) {
		h.logger.WithField("url", query).Info("Detected YouTube playlist URL")

		videos, err := h.ytService.ExtractPlaylist(query)
		if err != nil {
			return nil, false, fmt.Errorf("failed to extract playlist: %w", err)
		}

		if len(videos) == 0 {
			return nil, false, fmt.Errorf("playlist is empty or invalid")
		}

		songs := make([]SongInfo, 0, len(videos))
		for _, video := range videos {
			songs = append(songs, SongInfo{
				URL:        fmt.Sprintf("https://www.youtube.com/watch?v=%s", video.ID),
				Title:      video.Title,
				SourceType: valueobjects.SourceTypeYouTube,
			})
		}

		return songs, true, nil
	}

	// If query is not a YouTube URL, search for it
	if !youtube.IsYouTubeURL(query) {
		h.logger.WithField("query", query).Info("Searching YouTube...")
		results, err := h.ytService.Search(query, 1)
		if err != nil {
			return nil, false, fmt.Errorf("search failed: %w", err)
		}
		if len(results) == 0 {
			return nil, false, fmt.Errorf("no results found for: %s", query)
		}

		return []SongInfo{{
			URL:        fmt.Sprintf("https://www.youtube.com/watch?v=%s", results[0].ID),
			Title:      results[0].Title,
			SourceType: valueobjects.SourceTypeYouTube,
		}}, false, nil
	}

	// Regular YouTube video URL
	return []SongInfo{{
		URL:        query,
		Title:      query, // Will be updated after extraction
		SourceType: valueobjects.SourceTypeYouTube,
	}}, false, nil
}

// handlePause handles the pause command
func (h *Handler) handlePause(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	if err := h.playbackService.Pause(i.GuildID); err != nil {
		return respondError(s, i, "No active playback to pause")
	}

	embed := NewEmbed().
		Title("⏸️ Playback Paused").
		Description("Use `/resume` to continue playing").
		Color(ColorWarning).
		Build()

	return respondEmbed(s, i, embed)
}

// handleResume handles the resume command
func (h *Handler) handleResume(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	if err := h.playbackService.Resume(i.GuildID); err != nil {
		return respondError(s, i, "No paused playback to resume")
	}

	embed := NewEmbed().
		Title("▶️ Playback Resumed").
		Description("Music is now playing").
		Color(ColorSuccess).
		Build()

	return respondEmbed(s, i, embed)
}

// handleSkip handles the skip command
func (h *Handler) handleSkip(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	tracklist := h.playbackService.GetTracklist(i.GuildID)
	if tracklist == nil || tracklist.Size() == 0 {
		return respondError(s, i, "No songs in queue")
	}

	options := i.ApplicationCommandData().Options
	var targetIndex *int
	if len(options) > 0 {
		idx := int(options[0].IntValue())
		targetIndex = &idx
	}

	// Validate index if provided
	if targetIndex != nil {
		totalSongs := tracklist.Size()
		if *targetIndex < 1 || *targetIndex > totalSongs {
			return respondError(s, i, fmt.Sprintf("Invalid index. Queue has %d songs (use 1-%d)", totalSongs, totalSongs))
		}

		// Jump to the specific position (this handles both skip and stop)
		if err := h.playbackService.JumpToPosition(i.GuildID, *targetIndex); err != nil {
			return respondError(s, i, fmt.Sprintf("Failed to skip to position: %v", err))
		}

		// Get the song at the target position for display
		nextSong := tracklist.CurrentSong()

		// Build embed with next song info
		embed := h.buildSkipEmbed(nextSong, fmt.Sprintf("⏭️ Skipped to song #%d", *targetIndex))
		return respondEmbed(s, i, embed)
	}

	// Regular skip to next song
	if err := h.playbackService.Skip(i.GuildID); err != nil {
		return respondError(s, i, "No song to skip")
	}

	// Get the next song that will play
	nextSong := tracklist.CurrentSong()

	embed := h.buildSkipEmbed(nextSong, "⏭️ Skipped to Next")
	return respondEmbed(s, i, embed)
}

// buildSkipEmbed creates an embed for skip response
func (h *Handler) buildSkipEmbed(nextSong *entities.Song, title string) *discordgo.MessageEmbed {
	builder := NewEmbed().
		Title(title).
		Color(ColorInfo)

	if nextSong != nil {
		meta := nextSong.GetMetadata()
		if meta != nil {
			builder.Description(fmt.Sprintf("Now playing: **%s**", meta.Title))
			builder.Thumbnail(meta.Thumbnail)
			builder.Field("Duration", meta.DurationFormatted(), true)
			if meta.Uploader != "" {
				builder.Field("Artist", meta.Uploader, true)
			}
		} else {
			builder.Description(fmt.Sprintf("Now playing: **%s**", nextSong.DisplayName()))
		}
	} else {
		builder.Description("No more songs in queue")
	}

	return builder.Build()
}

// handleVolume handles the volume command
func (h *Handler) handleVolume(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	options := i.ApplicationCommandData().Options
	level := int(options[0].IntValue())

	if err := h.playbackService.SetVolume(i.GuildID, level); err != nil {
		return respondError(s, i, "Failed to set volume: "+err.Error())
	}

	// Create visual volume bar
	bars := level / 10
	var sb strings.Builder
	for j := 0; j < 10; j++ {
		if j < bars {
			sb.WriteString("█")
		} else {
			sb.WriteString("░")
		}
	}

	embed := NewEmbed().
		Title("🔊 Volume Adjusted").
		Description(fmt.Sprintf("%s **%d%%**", sb.String(), level)).
		Color(ColorInfo).
		Build()

	return respondEmbed(s, i, embed)
}

// findBestDurationMatch finds the YouTube video with closest duration to target
// Returns nil if no match within acceptable tolerance (±10 seconds)
func findBestDurationMatch(results []youtube.YouTubeInfo, targetDuration int) *youtube.YouTubeInfo {
	if len(results) == 0 {
		return nil
	}

	const maxDifference = 10.0 // ±10 seconds tolerance

	var bestMatch *youtube.YouTubeInfo
	minDifference := 999999.0 // Large number

	for i := range results {
		diff := absFloat(results[i].Duration - float64(targetDuration))
		if diff < minDifference {
			minDifference = diff
			bestMatch = &results[i]
		}
	}

	// Only return match if within acceptable tolerance
	if minDifference <= maxDifference {
		return bestMatch
	}

	return nil
}

// abs returns the absolute value of an integer
func abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}

// absFloat returns the absolute value of a float64
func absFloat(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}

// resolveSpotifyTrackToYouTube searches YouTube for a Spotify track
// Returns YouTube URL or empty string if not found
func (h *Handler) resolveSpotifyTrackToYouTube(track spotify.Track) string {
	var videoID string
	var found bool
	spotifyDuration := track.GetDurationSeconds()

	// Strategy 1: Try ISRC search first (most accurate)
	if isrc := track.GetISRC(); isrc != "" {
		h.logger.WithFields(map[string]interface{}{
			"track": track.Name,
			"isrc":  isrc,
		}).Debug("Trying ISRC search")

		if info, err := h.ytService.SearchByISRC(isrc); err == nil {
			// Verify duration (±5 seconds tolerance)
			if absFloat(info.Duration-float64(spotifyDuration)) <= 5 {
				videoID = info.ID
				found = true
				h.logger.WithField("track", track.Name).Info("✅ Found by ISRC with duration match")
			} else {
				h.logger.WithFields(map[string]interface{}{
					"track":            track.Name,
					"spotify_duration": spotifyDuration,
					"youtube_duration": info.Duration,
				}).Warn("ISRC match but duration mismatch, trying other methods")
			}
		}
	}

	// Strategy 2: Try detailed search with album info
	if !found {
		detailedQuery := track.ToDetailedSearchQuery()
		h.logger.WithField("query", detailedQuery).Debug("Trying detailed search")

		results, err := h.ytService.Search(detailedQuery, 3)
		if err == nil && len(results) > 0 {
			bestMatch := findBestDurationMatch(results, spotifyDuration)
			if bestMatch != nil {
				videoID = bestMatch.ID
				found = true
				h.logger.WithField("track", track.Name).Info("✅ Found by detailed search")
			}
		}
	}

	// Strategy 3: Fall back to simple search
	if !found {
		simpleQuery := track.ToSearchQuery()
		h.logger.WithField("query", simpleQuery).Debug("Trying simple search")

		results, err := h.ytService.Search(simpleQuery, 3)
		if err != nil {
			h.logger.WithError(err).WithField("track", track.Name).Warn("All search methods failed")
			return ""
		}

		if len(results) == 0 {
			h.logger.WithField("track", track.Name).Warn("No YouTube results found")
			return ""
		}

		bestMatch := findBestDurationMatch(results, spotifyDuration)
		if bestMatch != nil {
			videoID = bestMatch.ID
			found = true
			h.logger.WithField("track", track.Name).Info("✅ Found by simple search")
		} else {
			// Last resort: use first result
			videoID = results[0].ID
			h.logger.WithField("track", track.Name).Warn("⚠️ Using first result (no duration match)")
		}
	}

	if videoID == "" {
		return ""
	}

	return fmt.Sprintf("https://www.youtube.com/watch?v=%s", videoID)
}

// addSpotifyTracksProgressively resolves Spotify tracks to YouTube progressively
// Resolves initialCount tracks immediately, then resolves remaining in background
// Returns: initial songs resolved and total track count
func (h *Handler) addSpotifyTracksProgressively(guildID, userID string, tracks []spotify.Track, initialCount int) ([]SongInfo, int) {
	totalTracks := len(tracks)
	if initialCount <= 0 || initialCount > totalTracks {
		initialCount = totalTracks
	}

	// Resolve initial batch immediately
	initialSongs := make([]SongInfo, 0, initialCount)
	for i := 0; i < initialCount && i < totalTracks; i++ {
		ytURL := h.resolveSpotifyTrackToYouTube(tracks[i])
		if ytURL != "" {
			initialSongs = append(initialSongs, SongInfo{
				URL:        ytURL,
				Title:      tracks[i].Name,
				SourceType: valueobjects.SourceTypeYouTube,
			})
		}
	}

	// Resolve and add remaining tracks in background
	if totalTracks > initialCount {
		remaining := tracks[initialCount:]
		h.logger.WithFields(map[string]interface{}{
			"initial_resolved": len(initialSongs),
			"remaining":        len(remaining),
			"total":            totalTracks,
		}).Info("Resolving remaining Spotify tracks in background...")

		go func() {
			addedCount := 0
			for _, track := range remaining {
				// Check if playback is still active before adding more songs
				if !h.playbackService.IsPlaying(guildID) {
					h.logger.WithField("added", addedCount).Info("⏹️ Playback stopped, halting background Spotify track loading")
					return
				}

				// Check if tracklist still exists
				if h.playbackService.GetTracklist(guildID) == nil {
					h.logger.WithField("added", addedCount).Info("⏹️ Tracklist cleared, halting background Spotify track loading")
					return
				}

				ytURL := h.resolveSpotifyTrackToYouTube(track)
				if ytURL == "" {
					continue
				}

				song := entities.NewSong(ytURL, valueobjects.SourceTypeYouTube, userID, guildID)
				if err := h.playbackService.AddSong(guildID, song); err != nil {
					h.logger.WithError(err).Debug("Failed to add background Spotify song")
					continue
				}
				addedCount++
			}
			h.logger.WithField("count", addedCount).Info("✅ Finished resolving background Spotify tracks")
		}()
	}

	return initialSongs, totalTracks
}
