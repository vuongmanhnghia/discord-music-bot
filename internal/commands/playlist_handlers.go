package commands

import (
	"fmt"
	"strings"

	"github.com/bwmarrin/discordgo"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
)

// handlePlaylists shows all available playlists
func (h *Handler) handlePlaylists(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	guildID := i.GuildID
	playlists, err := h.playlistService.ListPlaylistsForGuild(guildID)
	if err != nil {
		return respondError(s, i, "Failed to retrieve playlists")
	}

	if len(playlists) == 0 {
		embed := NewEmbed().
			Title("Playlists").
			Description("No playlists found.\nUse `/playlist create <name>` to create one!").
			Color(ColorInfo).
			Build()
		return respondEmbed(s, i, embed)
	}

	var sb strings.Builder
	for _, name := range playlists {
		sb.WriteString(fmt.Sprintf("⚬ **%s**\n", name))
	}

	embed := NewEmbed().
		Title("Available Playlists").
		Description(sb.String()).
		Color(ColorPrimary).
		Footer(fmt.Sprintf("%d playlists • Use /use <name> to load a playlist", len(playlists))).
		Build()

	return respondEmbed(s, i, embed)
}

// handleUsePlaylist loads and plays a playlist
func (h *Handler) handleUsePlaylist(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	guildID := i.GuildID
	options := i.ApplicationCommandData().Options
	playlistName := options[0].StringValue()

	// Get optional start_index parameter
	var startIndex *int
	if len(options) > 1 {
		idx := int(options[1].IntValue())
		startIndex = &idx
	}

	playlist, err := h.playlistService.GetPlaylistForGuild(guildID, playlistName)
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
			Title("Playlist Activated").
			Description(fmt.Sprintf("**%s** is now the active playlist (empty)", playlistName)).
			Color(ColorInfo).
			Field("💡 Tip", "Use `/add <url>` to add songs to this playlist", false).
			Build()
		return respondEmbed(s, i, embed)
	}

	// Validate start_index if provided
	if startIndex != nil {
		if *startIndex < 1 || *startIndex > len(playlist.Entries) {
			return respondError(s, i, fmt.Sprintf("Invalid start index. Playlist has %d songs (use 1-%d)", len(playlist.Entries), len(playlist.Entries)))
		}
	}

	if err := deferResponse(s, i); err != nil {
		return err
	}

	channelID, err := h.getUserVoiceChannel(s, i.GuildID, i.Member.User.ID)
	if err != nil {
		return followUpError(s, i, "You must be in a voice channel to play music")
	}

	songs, err := h.playlistService.GetPlaylistSongsForGuild(guildID, playlistName)
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

	// Jump to start_index if provided
	if startIndex != nil {
		if tracklist := h.playbackService.GetTracklist(i.GuildID); tracklist != nil {
			tracklist.SkipToPosition(*startIndex)
		}
	}

	// Start playback
	if err := h.playbackService.Play(i.GuildID, channelID); err != nil {
		return followUpError(s, i, "Failed to start playback")
	}

	// Build embed with start position info
	description := fmt.Sprintf("Now playing **%s**", playlistName)
	if startIndex != nil {
		description = fmt.Sprintf("Now playing **%s** from song #%d", playlistName, *startIndex)
	}

	embed := NewEmbed().
		Title("Playlist Loaded").
		Description(description).
		Color(ColorSuccess).
		Field("Songs", fmt.Sprintf("%d", len(songs)), true).
		Field("Status", "Active", true).
		Footer("Use /queue to view the queue").
		Build()

	return followUpEmbed(s, i, embed)
}

// handleQuickAdd adds a song or playlist to the active playlist
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

	// Resolve query to song URLs (handles single video, playlist, or search)
	songs, isPlaylist, err := h.ResolveSongURLs(songQuery)
	if err != nil {
		return followUpError(s, i, err.Error())
	}

	// Add all songs to playlist
	addedCount := 0
	for _, songInfo := range songs {
		err := h.playlistService.AddToPlaylistForGuild(
			i.GuildID,
			playlistName,
			songInfo.URL,
			valueobjects.SourceTypeYouTube,
			songInfo.Title,
		)
		if err != nil {
			h.logger.WithError(err).Warn("Failed to add song to playlist")
			continue
		}
		addedCount++
	}

	if addedCount == 0 {
		return followUpError(s, i, "Failed to add any songs to playlist")
	}

	// Build appropriate response
	var embed *discordgo.MessageEmbed
	if isPlaylist {
		embed = NewEmbed().
			Title("✅ Playlist Added to Playlist").
			Description(fmt.Sprintf("Added **%d** songs to **%s**", addedCount, playlistName)).
			Color(ColorSuccess).
			Field("Songs Added", fmt.Sprintf("%d", addedCount), true).
			Field("Playlist", playlistName, true).
			Build()
	} else {
		embed = NewEmbed().
			Title("✅ Song Added to Playlist").
			Description(fmt.Sprintf("**%s**", songs[0].Title)).
			Color(ColorSuccess).
			Field("Playlist", playlistName, true).
			Build()
	}

	return followUpEmbed(s, i, embed)
}

// handleRemove removes a song from a playlist
func (h *Handler) handleRemove(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	guildID := i.GuildID
	options := i.ApplicationCommandData().Options
	playlistName := options[0].StringValue()
	index := int(options[1].IntValue())

	playlist, err := h.playlistService.GetPlaylistForGuild(guildID, playlistName)
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
	if err := h.playlistService.RemoveFromPlaylistForGuild(guildID, playlistName, originalInput); err != nil {
		return respondError(s, i, err.Error())
	}

	embed := NewEmbed().
		Title("Song Removed").
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
	guildID := i.GuildID
	name := subCmd.Options[0].StringValue()

	if err := h.playlistService.CreatePlaylistForGuild(guildID, name); err != nil {
		return respondError(s, i, err.Error())
	}

	embed := NewEmbed().
		Title("Playlist Created").
		Description(fmt.Sprintf("Successfully created playlist **%s**", name)).
		Color(ColorSuccess).
		Field("Next Steps", fmt.Sprintf("> • Use `/use %s` to activate\n> • Use `/playlist add %s <song>` to add songs", name, name), false).
		Build()

	return respondEmbed(s, i, embed)
}

func (h *Handler) handlePlaylistDelete(s *discordgo.Session, i *discordgo.InteractionCreate, subCmd *discordgo.ApplicationCommandInteractionDataOption) error {
	guildID := i.GuildID
	name := subCmd.Options[0].StringValue()

	if err := h.playlistService.DeletePlaylistForGuild(guildID, name); err != nil {
		return respondError(s, i, err.Error())
	}

	embed := NewEmbed().
		Title("Playlist Deleted").
		Description(fmt.Sprintf("Playlist **%s** has been permanently deleted", name)).
		Color(ColorWarning).
		Build()

	return respondEmbed(s, i, embed)
}

func (h *Handler) handlePlaylistShow(s *discordgo.Session, i *discordgo.InteractionCreate, subCmd *discordgo.ApplicationCommandInteractionDataOption) error {
	guildID := i.GuildID
	name := subCmd.Options[0].StringValue()

	playlist, err := h.playlistService.GetPlaylistForGuild(guildID, name)
	if err != nil {
		return respondError(s, i, err.Error())
	}

	// Convert playlist entries to our pagination format
	entries := make([]PlaylistEntry, len(playlist.Entries))
	for i, entry := range playlist.Entries {
		entries[i] = PlaylistEntry{
			Title:         entry.Title,
			OriginalInput: entry.OriginalInput,
		}
	}

	// Build first page
	embed, components := buildPlaylistPage(name, entries, 0)

	// Send response with pagination buttons
	return s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseChannelMessageWithSource,
		Data: &discordgo.InteractionResponseData{
			Embeds:     []*discordgo.MessageEmbed{embed},
			Components: components,
		},
	})
}

func (h *Handler) handlePlaylistAdd(s *discordgo.Session, i *discordgo.InteractionCreate, subCmd *discordgo.ApplicationCommandInteractionDataOption) error {
	guildID := i.GuildID
	name := subCmd.Options[0].StringValue()

	var songQuery string
	if len(subCmd.Options) > 1 {
		songQuery = subCmd.Options[1].StringValue()
	}

	if songQuery != "" {
		if err := deferResponse(s, i); err != nil {
			return err
		}

		// Resolve query to song URLs (handles single video, playlist, or search)
		songs, isPlaylist, err := h.ResolveSongURLs(songQuery)
		if err != nil {
			return followUpError(s, i, err.Error())
		}

		// Add all songs to playlist
		addedCount := 0
		for _, songInfo := range songs {
			err := h.playlistService.AddToPlaylistForGuild(
				guildID,
				name,
				songInfo.URL,
				valueobjects.SourceTypeYouTube,
				songInfo.Title,
			)
			if err != nil {
				h.logger.WithError(err).Warn("Failed to add song to playlist")
				continue
			}
			addedCount++
		}

		if addedCount == 0 {
			return followUpError(s, i, "Failed to add any songs to playlist")
		}

		// Build appropriate response
		var embed *discordgo.MessageEmbed
		if isPlaylist {
			embed = NewEmbed().
				Title("✅ Playlist Added").
				Description(fmt.Sprintf("Added **%d** songs to playlist **%s**", addedCount, name)).
				Color(ColorSuccess).
				Field("Songs Added", fmt.Sprintf("%d", addedCount), true).
				Build()
		} else {
			embed = NewEmbed().
				Title("✅ Song Added").
				Description(fmt.Sprintf("Added **%s** to playlist **%s**", songs[0].Title, name)).
				Color(ColorSuccess).
				Build()
		}

		return followUpEmbed(s, i, embed)
	}

	// Add current playing song
	tracklist := h.playbackService.GetTracklist(guildID)
	if tracklist == nil {
		return respondError(s, i, "Nothing is playing. Provide a song URL or search query")
	}

	current := tracklist.CurrentSong()
	if current == nil {
		return respondError(s, i, "No song is currently playing. Provide a song URL")
	}

	err := h.playlistService.AddToPlaylistForGuild(
		guildID,
		name,
		current.OriginalInput,
		current.SourceType,
		current.DisplayName(),
	)
	if err != nil {
		return respondError(s, i, err.Error())
	}

	embed := NewEmbed().
		Title("Current Song Added").
		Description(fmt.Sprintf("Added **%s** to playlist **%s**", current.DisplayName(), name)).
		Color(ColorSuccess).
		Build()

	return respondEmbed(s, i, embed)
}
