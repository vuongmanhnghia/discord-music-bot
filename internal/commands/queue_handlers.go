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
	h.logger.WithField("guild", i.GuildID).Info("🔄 Performing full reset...")

	// 1. Stop playback immediately
	h.playbackService.Stop(i.GuildID)

	// 2. Clear queue
	if tracklist := h.playbackService.GetTracklist(i.GuildID); tracklist != nil {
		tracklist.Clear()
	}

	// 3. Clear active playlist
	h.activePlaylistMu.Lock()
	delete(h.activePlaylist, i.GuildID)
	h.activePlaylistMu.Unlock()

	// 4. Clear YouTube cache
	h.ytService.ClearCache()

	// 5. Leave voice channel to fully disconnect
	voiceConnections := s.VoiceConnections
	if vc, exists := voiceConnections[i.GuildID]; exists && vc != nil {
		if err := vc.Disconnect(); err != nil {
			h.logger.WithError(err).Warn("Failed to disconnect from voice channel")
		}
	}

	h.logger.Info("✅ Full reset completed")

	embed := NewEmbed().
		Title("🔄 Bot Reset Complete").
		Description("✅ All operations stopped\n✅ Queue cleared\n✅ Active playlist reset\n✅ Cache cleared\n✅ Disconnected from voice\n\nBot is back to initial state").
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
