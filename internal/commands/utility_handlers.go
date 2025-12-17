package commands

import (
	"fmt"
	"time"

	"github.com/bwmarrin/discordgo"
)

// handleJoin handles the join command
func (h *Handler) handleJoin(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	channelID, err := h.getUserVoiceChannel(s, i.GuildID, i.Member.User.ID)
	if err != nil {
		return respondError(s, i, "You must be in a voice channel")
	}

	_, err = s.ChannelVoiceJoin(i.GuildID, channelID, false, true)
	if err != nil {
		return respondError(s, i, "Failed to join voice channel: "+err.Error())
	}

	embed := NewEmbed().
		Title("🔊 Connected").
		Description("Successfully joined your voice channel").
		Color(ColorSuccess).
		Footer("Use /play to start playing music").
		Build()

	return respondEmbed(s, i, embed)
}

// handleLeave handles the leave command
func (h *Handler) handleLeave(s *discordgo.Session, i *discordgo.InteractionCreate) error {
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

	// Disconnect from voice
	for _, vs := range s.VoiceConnections {
		if vs.GuildID == i.GuildID {
			if err := vs.Disconnect(); err != nil {
				return respondError(s, i, "Failed to disconnect from voice channel")
			}

			embed := NewEmbed().
				Title("👋 Disconnected").
				Description("Left the voice channel and cleared all playback state").
				Color(ColorInfo).
				Build()

			return respondEmbed(s, i, embed)
		}
	}

	return respondError(s, i, "I'm not currently in a voice channel")
}

// handleStats handles the stats command
func (h *Handler) handleStats(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	voiceCount := len(s.VoiceConnections)
	guildCount := len(s.State.Guilds)
	latency := s.HeartbeatLatency().Milliseconds()

	// Latency indicator
	latencyStatus := "🟢 Excellent"
	if latency > 200 {
		latencyStatus = "🔴 Poor"
	} else if latency > 100 {
		latencyStatus = "🟡 Moderate"
	}

	embed := NewEmbed().
		Title("Bot Statistics").
		Color(ColorPrimary).
		Field("Servers", fmt.Sprintf("%d", guildCount), true).
		Field("Active Sessions", fmt.Sprintf("%d", voiceCount), true).
		Field("Latency", fmt.Sprintf("%dms %s", latency, latencyStatus), true).
		Footer(h.config.BotName).
		Timestamp(time.Now().Format(time.RFC3339)).
		Build()

	return respondEmbed(s, i, embed)
}

// handleHelp handles the help command
func (h *Handler) handleHelp(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	embed := NewEmbed().
		Title(h.config.BotName).
		Description("").
		Color(ColorPrimary).
		Field("Basic",
			"> **`/join` - Join voice channel**\n"+
				"> **`/leave` - Leave and clear state**\n",
			false).
		Field("Playback",
			"> **`/play <query>` - Play a song**\n"+
				"> **`/pause` - Pause playback**\n"+
				"> **`/resume` - Resume playback**\n"+
				"> **`/skip` - Skip current song**\n"+
				"> **`/stop` - Stop and clear queue**\n"+
				"> **`/volume <0-100>` - Adjust volume**",
			false).
		Field("Queue Management",
			"> **`/queue` - View current queue**\n"+
				"> **`/nowplaying` - Current song info**\n"+
				"> **`/shuffle` - Shuffle queue**\n"+
				"> **`/clear` - Clear queue & reset**\n"+
				"> **`/repeat <mode>` - Set repeat mode**",
			false).
		Field("Playlist Management",
			"> **`/playlists` - List all playlists**\n"+
				"> **`/use <name> <start_index>` - Load a playlist**\n"+
				"> **`/add <song>` - Quick add to active playlist**\n"+
				"> **`/playlist create/delete/show/add`**\n"+
				"> **`/remove <playlist> <index>` - Remove song**",
			false).
		Field("Utility",
			"> **`/stats` - Bot statistics**\n"+
				"> **`/help` - Show this help**\n"+
				"> **`/sync` - [Admin] Sync commands**",
			false).
		Footer("Discord Music Bot v2.0.0 • Built with Go").
		Build()

	return respondEmbed(s, i, embed)
}

// handleSync handles the sync command
func (h *Handler) handleSync(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	if err := deferEphemeral(s, i); err != nil {
		return err
	}

	if err := h.RegisterCommands(); err != nil {
		h.logger.WithError(err).Error("Failed to sync commands")
		return followUpError(s, i, "Failed to sync commands: "+err.Error())
	}

	h.logger.WithField("user", i.Member.User.Username).Info("Commands manually synced")

	embed := NewEmbed().
		Title("✅ Commands Synchronized").
		Description("All slash commands have been refreshed with Discord").
		Color(ColorSuccess).
		Build()

	return followUpEmbed(s, i, embed)
}
