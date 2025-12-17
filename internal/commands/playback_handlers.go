package commands

import (
	"fmt"
	"strings"

	"github.com/bwmarrin/discordgo"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
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

	// Resolve query to song URLs (handles single video, playlist, or search)
	songs, isPlaylist, err := h.ResolveSongURLs(query)
	if err != nil {
		return followUpError(s, i, err.Error())
	}

	// Add all songs to queue
	addedCount := 0
	for _, songInfo := range songs {
		song := entities.NewSong(songInfo.URL, valueobjects.SourceTypeYouTube, i.Member.User.ID, i.GuildID)
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
			Title("📻 YouTube Playlist Added").
			Description(fmt.Sprintf("Successfully added **%d** songs to the queue", addedCount)).
			Color(ColorSuccess).
			Field("Source", "YouTube Playlist", true).
			Field("Songs Added", fmt.Sprintf("%d", addedCount), true).
			Footer("Use /queue to view the queue").
			Build()
	} else {
		displayTitle := songs[0].Title
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

// SongInfo represents a resolved song with URL and title
type SongInfo struct {
	URL   string
	Title string
}

// ResolveSongURLs resolves a query (URL/search) into a list of song URLs and titles
// Returns: list of (URL, title) pairs and whether it was a playlist
func (h *Handler) ResolveSongURLs(query string) ([]SongInfo, bool, error) {

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
				URL:   fmt.Sprintf("https://www.youtube.com/watch?v=%s", video.ID),
				Title: video.Title,
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
			URL:   fmt.Sprintf("https://www.youtube.com/watch?v=%s", results[0].ID),
			Title: results[0].Title,
		}}, false, nil
	}

	// Regular YouTube video URL
	return []SongInfo{{
		URL:   query,
		Title: query, // Will be updated after extraction
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

// handleStop handles the stop command
func (h *Handler) handleStop(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	if err := h.playbackService.Stop(i.GuildID); err != nil {
		return respondError(s, i, "No active playback to stop")
	}

	if tracklist := h.playbackService.GetTracklist(i.GuildID); tracklist != nil {
		tracklist.Clear()
	}

	embed := NewEmbed().
		Title("⏹️ Playback Stopped").
		Description("Playback has been stopped and the queue has been cleared").
		Color(ColorError).
		Build()

	return respondEmbed(s, i, embed)
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
