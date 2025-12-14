package commands

import (
	"fmt"
	"strings"

	"github.com/bwmarrin/discordgo"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
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

	song := entities.NewSong(query, valueobjects.SourceTypeYouTube, i.Member.User.ID, i.GuildID)

	if err := h.playbackService.AddSong(i.GuildID, song); err != nil {
		return followUpError(s, i, fmt.Sprintf("Failed to add song: %v", err))
	}

	if !h.playbackService.IsPlaying(i.GuildID) {
		if err := h.playbackService.Play(i.GuildID, channelID); err != nil {
			return followUpError(s, i, fmt.Sprintf("Failed to start playback: %v", err))
		}
	}

	embed := NewEmbed().
		Title("🎵 Added to Queue").
		Description(fmt.Sprintf("**%s**", query)).
		Color(ColorSuccess).
		Footer("Use /queue to view the queue").
		Build()

	return followUpEmbed(s, i, embed)
}

// handleAPlay handles the aplay command (add YouTube playlist to queue)
func (h *Handler) handleAPlay(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	if err := deferResponse(s, i); err != nil {
		return err
	}

	options := i.ApplicationCommandData().Options
	playlistURL := options[0].StringValue()

	channelID, err := h.getUserVoiceChannel(s, i.GuildID, i.Member.User.ID)
	if err != nil {
		return followUpError(s, i, "You must be in a voice channel to play music")
	}

	videos, err := h.ytService.ExtractPlaylist(playlistURL)
	if err != nil {
		return followUpError(s, i, "Failed to extract playlist: "+err.Error())
	}

	if len(videos) == 0 {
		return followUpError(s, i, "Playlist is empty or invalid")
	}

	addedCount := 0
	for _, video := range videos {
		videoURL := fmt.Sprintf("https://www.youtube.com/watch?v=%s", video.ID)
		song := entities.NewSong(videoURL, valueobjects.SourceTypeYouTube, i.Member.User.ID, i.GuildID)

		if err := h.playbackService.AddSong(i.GuildID, song); err != nil {
			h.logger.WithError(err).Warn("Failed to add song from playlist")
			continue
		}
		addedCount++
	}

	if addedCount == 0 {
		return followUpError(s, i, "Failed to add any songs from playlist")
	}

	if !h.playbackService.IsPlaying(i.GuildID) {
		if err := h.playbackService.Play(i.GuildID, channelID); err != nil {
			h.logger.WithError(err).Error("Failed to start playback")
		}
	}

	embed := NewEmbed().
		Title("📻 YouTube Playlist Loaded").
		Description(fmt.Sprintf("Successfully added **%d** songs to the queue", addedCount)).
		Color(ColorSuccess).
		Field("Source", "YouTube Playlist", true).
		Field("Songs Added", fmt.Sprintf("%d", addedCount), true).
		Footer("Use /queue to view the queue").
		Build()

	return followUpEmbed(s, i, embed)
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
	var skippedTitle string
	if tracklist != nil && tracklist.CurrentSong() != nil {
		if meta := tracklist.CurrentSong().GetMetadata(); meta != nil {
			skippedTitle = meta.Title
		}
	}

	if err := h.playbackService.Skip(i.GuildID); err != nil {
		return respondError(s, i, "No song to skip")
	}

	desc := "Skipping to the next song"
	if skippedTitle != "" {
		desc = fmt.Sprintf("Skipped: **%s**", skippedTitle)
	}

	embed := NewEmbed().
		Title("⏭️ Skipped").
		Description(desc).
		Color(ColorInfo).
		Build()

	return respondEmbed(s, i, embed)
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
