package commands

import (
	"fmt"
	"strings"

	"github.com/bwmarrin/discordgo"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
)

// handlePlaylists shows all available playlists
func (h *Handler) handlePlaylists(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	playlists, err := h.playlistService.ListPlaylists()
	if err != nil {
		return respondError(s, i, "Failed to retrieve playlists")
	}

	if len(playlists) == 0 {
		embed := NewEmbed().
			Title("📋 Playlists").
			Description("No playlists found.\nUse `/playlist create <name>` to create one!").
			Color(ColorInfo).
			Build()
		return respondEmbed(s, i, embed)
	}

	var sb strings.Builder
	for idx, name := range playlists {
		sb.WriteString(fmt.Sprintf("`%d.` **%s**\n", idx+1, name))
	}

	embed := NewEmbed().
		Title("📋 Available Playlists").
		Description(sb.String()).
		Color(ColorPrimary).
		Footer(fmt.Sprintf("%d playlists • Use /use <name> to load a playlist", len(playlists))).
		Build()

	return respondEmbed(s, i, embed)
}

// handleUsePlaylist loads and plays a playlist
func (h *Handler) handleUsePlaylist(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	options := i.ApplicationCommandData().Options
	playlistName := options[0].StringValue()

	playlist, err := h.playlistService.GetPlaylist(playlistName)
	if err != nil {
		return respondError(s, i, fmt.Sprintf("Playlist '%s' not found", playlistName))
	}

	// Set as active playlist
	h.activePlaylistMu.Lock()
	h.activePlaylist[i.GuildID] = playlistName
	h.activePlaylistMu.Unlock()

	// If empty, just set as active
	if len(playlist.Entries) == 0 {
		embed := NewEmbed().
			Title("📋 Playlist Activated").
			Description(fmt.Sprintf("**%s** is now the active playlist (empty)", playlistName)).
			Color(ColorInfo).
			Field("💡 Tip", "Use `/add <url>` to add songs to this playlist", false).
			Build()
		return respondEmbed(s, i, embed)
	}

	if err := deferResponse(s, i); err != nil {
		return err
	}

	channelID, err := h.getUserVoiceChannel(s, i.GuildID, i.Member.User.ID)
	if err != nil {
		return followUpError(s, i, "You must be in a voice channel to play music")
	}

	songs, err := h.playlistService.GetPlaylistSongs(playlistName)
	if err != nil {
		return followUpError(s, i, fmt.Sprintf("Failed to load playlist: %v", err))
	}

	// Stop and clear
	h.playbackService.Stop(i.GuildID)
	if tracklist := h.playbackService.GetTracklist(i.GuildID); tracklist != nil {
		tracklist.Clear()
	}

	// Add songs
	for _, song := range songs {
		if err := h.playbackService.AddSong(i.GuildID, song); err != nil {
			h.logger.WithError(err).Warn("Failed to add song to queue")
		}
	}

	// Start playback
	if err := h.playbackService.Play(i.GuildID, channelID); err != nil {
		return followUpError(s, i, "Failed to start playback")
	}

	embed := NewEmbed().
		Title("📻 Playlist Loaded").
		Description(fmt.Sprintf("Now playing **%s**", playlistName)).
		Color(ColorSuccess).
		Field("🎵 Songs", fmt.Sprintf("%d", len(songs)), true).
		Field("📋 Status", "Active", true).
		Footer("Use /queue to view the queue").
		Build()

	return followUpEmbed(s, i, embed)
}

// handleQuickAdd adds a song to the active playlist
func (h *Handler) handleQuickAdd(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	h.activePlaylistMu.RLock()
	playlistName, hasActive := h.activePlaylist[i.GuildID]
	h.activePlaylistMu.RUnlock()

	if !hasActive || playlistName == "" {
		return respondError(s, i, "No active playlist. Use `/use <name>` first to set one")
	}

	if err := deferResponse(s, i); err != nil {
		return err
	}

	options := i.ApplicationCommandData().Options
	songQuery := options[0].StringValue()

	info, err := h.ytService.ExtractInfo(songQuery)
	if err != nil {
		return followUpError(s, i, "Failed to extract song info: "+err.Error())
	}

	err = h.playlistService.AddToPlaylist(
		playlistName,
		info.WebpageURL,
		valueobjects.SourceTypeYouTube,
		info.Title,
	)
	if err != nil {
		return followUpError(s, i, err.Error())
	}

	embed := NewEmbed().
		Title("✅ Song Added to Playlist").
		Description(fmt.Sprintf("**%s**", info.Title)).
		Color(ColorSuccess).
		Field("📋 Playlist", playlistName, true).
		Build()

	return followUpEmbed(s, i, embed)
}

// handleRemove removes a song from a playlist
func (h *Handler) handleRemove(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	options := i.ApplicationCommandData().Options
	playlistName := options[0].StringValue()
	index := int(options[1].IntValue())

	playlist, err := h.playlistService.GetPlaylist(playlistName)
	if err != nil {
		return respondError(s, i, err.Error())
	}

	if index < 1 || index > len(playlist.Entries) {
		return respondError(s, i, fmt.Sprintf("Invalid index. Playlist has %d songs", len(playlist.Entries)))
	}

	songTitle := playlist.Entries[index-1].Title
	if songTitle == "" {
		songTitle = playlist.Entries[index-1].OriginalInput
	}

	originalInput := playlist.Entries[index-1].OriginalInput
	if err := h.playlistService.RemoveFromPlaylist(playlistName, originalInput); err != nil {
		return respondError(s, i, err.Error())
	}

	embed := NewEmbed().
		Title("🗑️ Song Removed").
		Description(fmt.Sprintf("Removed **%s** from **%s**", songTitle, playlistName)).
		Color(ColorWarning).
		Build()

	return respondEmbed(s, i, embed)
}

// handlePlaylistSubcommand handles playlist management subcommands
func (h *Handler) handlePlaylistSubcommand(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	options := i.ApplicationCommandData().Options
	if len(options) == 0 {
		return respondError(s, i, "Invalid subcommand")
	}

	subCmd := options[0]
	switch subCmd.Name {
	case "create":
		return h.handlePlaylistCreate(s, i, subCmd)
	case "delete":
		return h.handlePlaylistDelete(s, i, subCmd)
	case "show":
		return h.handlePlaylistShow(s, i, subCmd)
	case "add":
		return h.handlePlaylistAdd(s, i, subCmd)
	default:
		return respondError(s, i, "Unknown subcommand")
	}
}

func (h *Handler) handlePlaylistCreate(s *discordgo.Session, i *discordgo.InteractionCreate, subCmd *discordgo.ApplicationCommandInteractionDataOption) error {
	name := subCmd.Options[0].StringValue()

	if err := h.playlistService.CreatePlaylist(name); err != nil {
		return respondError(s, i, err.Error())
	}

	embed := NewEmbed().
		Title("✅ Playlist Created").
		Description(fmt.Sprintf("Successfully created playlist **%s**", name)).
		Color(ColorSuccess).
		Field("💡 Next Steps", fmt.Sprintf("• Use `/use %s` to activate\n• Use `/playlist add %s <song>` to add songs", name, name), false).
		Build()

	return respondEmbed(s, i, embed)
}

func (h *Handler) handlePlaylistDelete(s *discordgo.Session, i *discordgo.InteractionCreate, subCmd *discordgo.ApplicationCommandInteractionDataOption) error {
	name := subCmd.Options[0].StringValue()

	if err := h.playlistService.DeletePlaylist(name); err != nil {
		return respondError(s, i, err.Error())
	}

	embed := NewEmbed().
		Title("🗑️ Playlist Deleted").
		Description(fmt.Sprintf("Playlist **%s** has been permanently deleted", name)).
		Color(ColorWarning).
		Build()

	return respondEmbed(s, i, embed)
}

func (h *Handler) handlePlaylistShow(s *discordgo.Session, i *discordgo.InteractionCreate, subCmd *discordgo.ApplicationCommandInteractionDataOption) error {
	name := subCmd.Options[0].StringValue()

	playlist, err := h.playlistService.GetPlaylist(name)
	if err != nil {
		return respondError(s, i, err.Error())
	}

	if len(playlist.Entries) == 0 {
		embed := NewEmbed().
			Title(fmt.Sprintf("📋 %s", name)).
			Description("This playlist is empty").
			Color(ColorInfo).
			Footer("Use /playlist add to add songs").
			Build()
		return respondEmbed(s, i, embed)
	}

	var sb strings.Builder
	for idx, entry := range playlist.Entries {
		if idx >= 15 {
			sb.WriteString(fmt.Sprintf("\n*...and %d more songs*", len(playlist.Entries)-15))
			break
		}
		title := entry.Title
		if title == "" {
			title = entry.OriginalInput
		}
		if len(title) > 45 {
			title = title[:42] + "..."
		}
		sb.WriteString(fmt.Sprintf("`%d.` %s\n", idx+1, title))
	}

	embed := NewEmbed().
		Title(fmt.Sprintf("📋 %s", name)).
		Description(sb.String()).
		Color(ColorPrimary).
		Footer(fmt.Sprintf("%d songs • Use /use %s to play", len(playlist.Entries), name)).
		Build()

	return respondEmbed(s, i, embed)
}

func (h *Handler) handlePlaylistAdd(s *discordgo.Session, i *discordgo.InteractionCreate, subCmd *discordgo.ApplicationCommandInteractionDataOption) error {
	name := subCmd.Options[0].StringValue()

	var songQuery string
	if len(subCmd.Options) > 1 {
		songQuery = subCmd.Options[1].StringValue()
	}

	if songQuery != "" {
		if err := deferResponse(s, i); err != nil {
			return err
		}

		info, err := h.ytService.ExtractInfo(songQuery)
		if err != nil {
			return followUpError(s, i, "Failed to extract song info: "+err.Error())
		}

		err = h.playlistService.AddToPlaylist(
			name,
			info.WebpageURL,
			valueobjects.SourceTypeYouTube,
			info.Title,
		)
		if err != nil {
			return followUpError(s, i, err.Error())
		}

		embed := NewEmbed().
			Title("✅ Song Added").
			Description(fmt.Sprintf("Added **%s** to playlist **%s**", info.Title, name)).
			Color(ColorSuccess).
			Build()

		return followUpEmbed(s, i, embed)
	}

	// Add current playing song
	tracklist := h.playbackService.GetTracklist(i.GuildID)
	if tracklist == nil {
		return respondError(s, i, "Nothing is playing. Provide a song URL or search query")
	}

	current := tracklist.CurrentSong()
	if current == nil {
		return respondError(s, i, "No song is currently playing. Provide a song URL")
	}

	err := h.playlistService.AddToPlaylist(
		name,
		current.OriginalInput,
		current.SourceType,
		current.DisplayName(),
	)
	if err != nil {
		return respondError(s, i, err.Error())
	}

	embed := NewEmbed().
		Title("✅ Current Song Added").
		Description(fmt.Sprintf("Added **%s** to playlist **%s**", current.DisplayName(), name)).
		Color(ColorSuccess).
		Build()

	return respondEmbed(s, i, embed)
}
