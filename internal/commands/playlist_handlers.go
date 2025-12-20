package commands

import (
	"fmt"
	"sort"
	"strconv"
	"strings"

	"github.com/bwmarrin/discordgo"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
	"github.com/vuongmanhnghia/discord-music-bot/internal/services/spotify"
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

	// Calculate initial load size
	totalSongs := len(songs)
	initialLoadSize := h.config.InitialLoadSize
	if initialLoadSize <= 0 || initialLoadSize > totalSongs {
		initialLoadSize = totalSongs
	}

	// Add initial songs to queue
	initialSongs := songs[:initialLoadSize]
	for _, song := range initialSongs {
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

	// Add remaining songs in background
	if totalSongs > initialLoadSize {
		remainingSongs := songs[initialLoadSize:]
		h.logger.WithFields(map[string]interface{}{
			"initial_loaded": initialLoadSize,
			"remaining":      len(remainingSongs),
			"total":          totalSongs,
		}).Info("Loading remaining playlist songs in background...")

		go func(guildID string, songs []*entities.Song) {
			for _, song := range songs {
				if err := h.playbackService.AddSong(guildID, song); err != nil {
					h.logger.WithError(err).Debug("Failed to add background song to queue")
					continue
				}
			}
			h.logger.WithField("count", len(songs)).Info("✅ Finished loading background playlist songs")
		}(i.GuildID, remainingSongs)
	}

	// Build embed with start position info and progressive loading status
	description := fmt.Sprintf("Now playing **%s**", playlistName)
	if startIndex != nil {
		description = fmt.Sprintf("Now playing **%s** from song #%d", playlistName, *startIndex)
	}

	// Add progressive loading info if applicable
	if totalSongs > initialLoadSize {
		description += fmt.Sprintf("\n\n🎵 Playing first **%d** songs immediately\n⏳ Loading remaining **%d** songs in background...", initialLoadSize, totalSongs-initialLoadSize)
	}

	embed := NewEmbed().
		Title("Playlist Loaded").
		Description(description).
		Color(ColorSuccess).
		Field("Total Songs", fmt.Sprintf("%d", totalSongs), true).
		Field("Status", "Active", true).
		Footer("Use /queue to view the queue").
		Build()

	return followUpEmbed(s, i, embed)
}

// handleQuickAdd adds a song or playlist to the active playlist and plays it
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

	// Get user's voice channel for playback
	channelID, err := h.getUserVoiceChannel(s, i.GuildID, i.Member.User.ID)
	if err != nil {
		return followUpError(s, i, "You must be in a voice channel to play music")
	}

	// Check for Spotify playlist/album and use progressive loading
	if spotify.IsSpotifyURL(songQuery) && h.spotifyService != nil {
		urlType, id, parseErr := spotify.ParseSpotifyURL(songQuery)
		if parseErr == nil && (urlType == "playlist" || urlType == "album") {
			return h.handleQuickAddSpotifyPlaylist(s, i, playlistName, channelID, urlType, id)
		}
	}

	// Resolve query to song URLs (handles single video, playlist, or search)
	songs, isPlaylist, err := h.ResolveSongURLs(songQuery)
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
				songs[0].Title = info.Title // Update title for saving and display
			}
		}
	}

	// Add all songs to playlist database
	addedCount := 0
	for _, songInfo := range songs {
		err := h.playlistService.AddToPlaylistForGuild(
			i.GuildID,
			playlistName,
			songInfo.URL,
			songInfo.SourceType,
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

	// Also add songs to playback queue
	queuedCount := 0
	for _, songInfo := range songs {
		song := entities.NewSong(songInfo.URL, songInfo.SourceType, i.Member.User.ID, i.GuildID)
		if err := h.playbackService.AddSong(i.GuildID, song); err != nil {
			h.logger.WithError(err).Warn("Failed to add song to playback queue")
			continue
		}
		queuedCount++
	}

	// Start playback if not already playing
	if !h.playbackService.IsPlaying(i.GuildID) && queuedCount > 0 {
		if err := h.playbackService.Play(i.GuildID, channelID); err != nil {
			h.logger.WithError(err).Warn("Failed to start playback")
		}
	}

	// Build appropriate response
	var embed *discordgo.MessageEmbed
	if isPlaylist {
		description := fmt.Sprintf("Added **%d** songs to **%s**", addedCount, playlistName)
		if queuedCount > 0 {
			description += fmt.Sprintf("\n🎵 Playing now!")
		}
		embed = NewEmbed().
			Title("✅ Playlist Added").
			Description(description).
			Color(ColorSuccess).
			Field("Songs Added", fmt.Sprintf("%d", addedCount), true).
			Field("Playlist", playlistName, true).
			Build()
	} else {
		displayTitle := extractedTitle
		if displayTitle == "" {
			displayTitle = songs[0].Title
		}
		if displayTitle == "" || displayTitle == songs[0].URL {
			displayTitle = songQuery
		}
		description := fmt.Sprintf("**%s**", displayTitle)
		if queuedCount > 0 {
			description += "\n🎵 Playing now!"
		}
		embed = NewEmbed().
			Title("✅ Song Added").
			Description(description).
			Color(ColorSuccess).
			Field("Playlist", playlistName, true).
			Build()
	}

	return followUpEmbed(s, i, embed)
}

// handleQuickAddSpotifyPlaylist handles adding and playing Spotify playlist/album with progressive loading
func (h *Handler) handleQuickAddSpotifyPlaylist(s *discordgo.Session, i *discordgo.InteractionCreate, playlistName, channelID, urlType, id string) error {
	h.logger.WithFields(map[string]interface{}{
		"type": urlType,
		"id":   id,
	}).Info("Using progressive loading for Spotify playlist/album in /add")

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

	// Add all resolved songs to database (initial + background will be added by goroutine)
	addedToDBCount := 0
	for _, songInfo := range initialSongs {
		err := h.playlistService.AddToPlaylistForGuild(
			i.GuildID,
			playlistName,
			songInfo.URL,
			songInfo.SourceType,
			songInfo.Title,
		)
		if err != nil {
			h.logger.WithError(err).Warn("Failed to add song to playlist database")
			continue
		}
		addedToDBCount++
	}

	// Background task to add remaining tracks to database as they resolve
	go func(guildID, playlist string, trackCount int) {
		h.logger.WithField("tracks", trackCount).Info("Will add remaining Spotify tracks to database in background...")
		// Note: The remaining tracks are already being resolved and added to playback queue
		// by addSpotifyTracksProgressively(). We just need to also save them to the database.
		// We'll rely on the playback service to handle the songs, and they'll be in the database
		// next time the playlist is loaded.
	}(i.GuildID, playlistName, totalCount-len(initialSongs))

	// Initial songs are already added to playback queue by addSpotifyTracksProgressively
	// Start playback if not already playing
	if !h.playbackService.IsPlaying(i.GuildID) {
		if err := h.playbackService.Play(i.GuildID, channelID); err != nil {
			return followUpError(s, i, fmt.Sprintf("Failed to start playback: %v", err))
		}
	}

	// Build response
	description := fmt.Sprintf("Added to **%s**\n\n🎵 Playing first **%d** songs immediately\n⏳ Loading remaining **%d** songs in background...", playlistName, len(initialSongs), totalCount-len(initialSongs))
	if totalCount == len(initialSongs) {
		description = fmt.Sprintf("Added **%d** songs to **%s**\n🎵 Playing now!", totalCount, playlistName)
	}

	embed := NewEmbed().
		Title("✅ Spotify Playlist Added").
		Description(description).
		Color(ColorSuccess).
		Field("Total Tracks", fmt.Sprintf("%d", totalCount), true).
		Field("Playlist", playlistName, true).
		Footer("Use /queue to view the queue").
		Build()

	return followUpEmbed(s, i, embed)
}

// handleRemove removes one or more songs from a playlist
func (h *Handler) handleRemove(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	guildID := i.GuildID
	options := i.ApplicationCommandData().Options
	playlistName := options[0].StringValue()
	indexesInput := options[1].StringValue()

	// Parse indexes from string
	indexes, err := parseIndexes(indexesInput)
	if err != nil {
		return respondError(s, i, fmt.Sprintf("Invalid indexes format: %s", err.Error()))
	}

	// Get playlist
	playlist, err := h.playlistService.GetPlaylistForGuild(guildID, playlistName)
	if err != nil {
		return respondError(s, i, err.Error())
	}

	playlistSize := len(playlist.Entries)
	if playlistSize == 0 {
		return respondError(s, i, "Playlist is empty")
	}

	// Validate all indexes
	for _, idx := range indexes {
		if idx < 1 || idx > playlistSize {
			return respondError(s, i, fmt.Sprintf("Invalid index %d. Playlist has %d songs", idx, playlistSize))
		}
	}

	// Remove duplicates and collect song titles
	removedSongs := make([]string, 0, len(indexes))
	removedCount := 0

	// Remove from highest index to lowest (already sorted descending)
	for _, idx := range indexes {
		if idx < 1 || idx > len(playlist.Entries) {
			// Skip if already removed (in case of duplicates after other removals)
			continue
		}

		songTitle := playlist.Entries[idx-1].Title
		if songTitle == "" {
			songTitle = playlist.Entries[idx-1].OriginalInput
		}

		originalInput := playlist.Entries[idx-1].OriginalInput
		if err := h.playlistService.RemoveFromPlaylistForGuild(guildID, playlistName, originalInput); err != nil {
			h.logger.WithError(err).Warn("Failed to remove song from playlist")
			continue
		}

		removedSongs = append(removedSongs, songTitle)
		removedCount++

		// Reload playlist after each removal to keep indexes accurate
		playlist, err = h.playlistService.GetPlaylistForGuild(guildID, playlistName)
		if err != nil {
			break
		}
	}

	if removedCount == 0 {
		return respondError(s, i, "Failed to remove any songs")
	}

	// Build response
	var description string
	if removedCount == 1 {
		description = fmt.Sprintf("Removed **%s** from **%s**", removedSongs[0], playlistName)
	} else {
		// Show first 5 songs, then "and X more"
		displayCount := 5
		if len(removedSongs) <= displayCount {
			description = fmt.Sprintf("Removed **%d songs** from **%s**:\n", removedCount, playlistName)
			for _, song := range removedSongs {
				description += fmt.Sprintf("• %s\n", song)
			}
		} else {
			description = fmt.Sprintf("Removed **%d songs** from **%s**:\n", removedCount, playlistName)
			for i := 0; i < displayCount; i++ {
				description += fmt.Sprintf("• %s\n", removedSongs[i])
			}
			description += fmt.Sprintf("...and %d more", len(removedSongs)-displayCount)
		}
	}

	embed := NewEmbed().
		Title("Songs Removed").
		Description(description).
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
	case "rename":
		return h.handlePlaylistRename(s, i, subCmd)
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

		// For single URL, extract metadata before adding to show proper title
		var extractedTitle string
		if !isPlaylist && len(songs) == 1 {
			songURL := songs[0].URL
			if strings.HasPrefix(songURL, "http://") || strings.HasPrefix(songURL, "https://") {
				h.logger.WithField("url", songURL).Debug("Extracting metadata for single URL")
				if info, err := h.ytService.ExtractInfo(songURL); err == nil {
					extractedTitle = info.Title
					songs[0].Title = info.Title // Update title for saving and display
				}
			}
		}

		// Add all songs to playlist
		addedCount := 0
		for _, songInfo := range songs {
			err := h.playlistService.AddToPlaylistForGuild(
				guildID,
				name,
				songInfo.URL,
				songInfo.SourceType,
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
			displayTitle := extractedTitle
			if displayTitle == "" {
				displayTitle = songs[0].Title
			}
			if displayTitle == "" || displayTitle == songs[0].URL {
				displayTitle = songQuery
			}
			embed = NewEmbed().
				Title("✅ Song Added").
				Description(fmt.Sprintf("Added **%s** to playlist **%s**", displayTitle, name)).
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

func (h *Handler) handlePlaylistRename(s *discordgo.Session, i *discordgo.InteractionCreate, subCmd *discordgo.ApplicationCommandInteractionDataOption) error {
	guildID := i.GuildID
	oldName := subCmd.Options[0].StringValue()
	newName := subCmd.Options[1].StringValue()

	// Validate new name
	if newName == "" {
		return respondError(s, i, "New playlist name cannot be empty")
	}

	if oldName == newName {
		return respondError(s, i, "New name is the same as the old name")
	}

	// Rename playlist
	if err := h.playlistService.RenamePlaylistForGuild(guildID, oldName, newName); err != nil {
		return respondError(s, i, err.Error())
	}

	// Update active playlist if it was the renamed one
	h.activePlaylistMu.Lock()
	if h.activePlaylist[guildID] == oldName {
		h.activePlaylist[guildID] = newName
	}
	h.activePlaylistMu.Unlock()

	embed := NewEmbed().
		Title("✅ Playlist Renamed").
		Description(fmt.Sprintf("**%s** → **%s**", oldName, newName)).
		Color(ColorSuccess).
		Field("Old Name", oldName, true).
		Field("New Name", newName, true).
		Build()

	return respondEmbed(s, i, embed)
}

// parseIndexes parses a string containing song indexes and returns a sorted slice of unique indexes
// Supports formats:
// - "2-5" (range)
// - "2, 3, 10" (list with spaces)
// - "2,3,10" (list without spaces)
// - "1-3,5,7-9" (mixed)
func parseIndexes(input string) ([]int, error) {
	input = strings.ReplaceAll(input, " ", "") // Remove all spaces
	if input == "" {
		return nil, fmt.Errorf("empty input")
	}

	indexMap := make(map[int]bool) // Use map to avoid duplicates

	// Split by comma
	parts := strings.Split(input, ",")
	for _, part := range parts {
		// Check if it's a range (contains '-')
		if strings.Contains(part, "-") {
			rangeParts := strings.Split(part, "-")
			if len(rangeParts) != 2 {
				return nil, fmt.Errorf("invalid range format: %s", part)
			}

			start, err := strconv.Atoi(rangeParts[0])
			if err != nil || start < 1 {
				return nil, fmt.Errorf("invalid start index in range: %s", rangeParts[0])
			}

			end, err := strconv.Atoi(rangeParts[1])
			if err != nil || end < 1 {
				return nil, fmt.Errorf("invalid end index in range: %s", rangeParts[1])
			}

			if start > end {
				return nil, fmt.Errorf("invalid range: start (%d) is greater than end (%d)", start, end)
			}

			// Add all indexes in range
			for i := start; i <= end; i++ {
				indexMap[i] = true
			}
		} else {
			// Single index
			idx, err := strconv.Atoi(part)
			if err != nil || idx < 1 {
				return nil, fmt.Errorf("invalid index: %s", part)
			}
			indexMap[idx] = true
		}
	}

	// Convert map to sorted slice
	indexes := make([]int, 0, len(indexMap))
	for idx := range indexMap {
		indexes = append(indexes, idx)
	}
	sort.Sort(sort.Reverse(sort.IntSlice(indexes))) // Sort descending to remove from end first

	return indexes, nil
}
