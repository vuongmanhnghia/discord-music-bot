package commands

import (
	"fmt"

	"github.com/bwmarrin/discordgo"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
)

// handleQueue handles the queue command
func (h *Handler) handleQueue(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	tracklist := h.playbackService.GetTracklist(i.GuildID)

	// Build first page
	embed, components := buildQueuePage(tracklist, 0)

	// Send response with pagination buttons
	return s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseChannelMessageWithSource,
		Data: &discordgo.InteractionResponseData{
			Embeds:     []*discordgo.MessageEmbed{embed},
			Components: components,
		},
	})
}

// handleNowPlaying handles the nowplaying command
func (h *Handler) handleNowPlaying(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	tracklist := h.playbackService.GetTracklist(i.GuildID)
	if tracklist == nil {
		return respondError(s, i, "Nothing is currently playing")
	}

	current := tracklist.CurrentSong()
	if current == nil || current.GetMetadata() == nil {
		return respondError(s, i, "Nothing is currently playing")
	}

	metadata := current.GetMetadata()

	builder := NewEmbed().
		Title("Now Playing").
		Description(fmt.Sprintf("**%s**", metadata.Title)).
		Color(ColorPrimary).
		Thumbnail(metadata.Thumbnail).
		Field("Duration", metadata.DurationFormatted(), true)

	if metadata.Uploader != "" {
		builder.Field("Artist", metadata.Uploader, true)
	}

	// Add progress indicator
	builder.Field("Status", "Playing", true)

	builder.Footer("Use /skip to play next song")

	return respondEmbed(s, i, builder.Build())
}

// handleShuffle handles the shuffle command
func (h *Handler) handleShuffle(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	tracklist := h.playbackService.GetTracklist(i.GuildID)
	if tracklist == nil || tracklist.Size() == 0 {
		return respondError(s, i, "Queue is empty - nothing to shuffle")
	}

	count := tracklist.Size()
	tracklist.Shuffle()

	embed := NewEmbed().
		Title("Queue Shuffled").
		Description(fmt.Sprintf("Successfully shuffled **%d** songs in the queue", count)).
		Color(ColorSuccess).
		Build()

	return respondEmbed(s, i, embed)
}

// handleClear handles the clear command
func (h *Handler) handleClear(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	// Stop playback
	h.playbackService.Stop(i.GuildID)

	// Clear queue
	if tracklist := h.playbackService.GetTracklist(i.GuildID); tracklist != nil {
		tracklist.Clear()
	}

	// Clear active playlist
	h.activePlaylistMu.Lock()
	delete(h.activePlaylist, i.GuildID)
	h.activePlaylistMu.Unlock()

	embed := NewEmbed().
		Title("Queue Cleared").
		Description("Playback stopped and queue has been cleared\nActive playlist has been reset").
		Color(ColorWarning).
		Build()

	return respondEmbed(s, i, embed)
}

// handleRepeat handles the repeat command
func (h *Handler) handleRepeat(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	tracklist := h.playbackService.GetTracklist(i.GuildID)
	if tracklist == nil {
		return respondError(s, i, "No active playback session")
	}

	options := i.ApplicationCommandData().Options
	modeStr := options[0].StringValue()

	var mode entities.RepeatMode
	var modeDisplay string
	var modeIcon string

	switch modeStr {
	case "none":
		mode = entities.RepeatModeNone
		modeDisplay = "Off"
		modeIcon = "➡️"
	case "track":
		mode = entities.RepeatModeTrack
		modeDisplay = "Single Track"
		modeIcon = "🔂"
	case "queue":
		mode = entities.RepeatModeQueue
		modeDisplay = "Entire Queue"
		modeIcon = "🔁"
	default:
		return respondError(s, i, "Invalid repeat mode")
	}

	tracklist.SetRepeatMode(mode)

	embed := NewEmbed().
		Title(fmt.Sprintf("%s Repeat Mode Updated", modeIcon)).
		Description(fmt.Sprintf("Repeat mode set to: **%s**", modeDisplay)).
		Color(ColorInfo).
		Build()

	return respondEmbed(s, i, embed)
}
