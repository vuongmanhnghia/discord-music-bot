package commands

import (
	"fmt"
	"strings"
	"sync"

	"github.com/bwmarrin/discordgo"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/entities"
	"github.com/vuongmanhnghia/discord-music-bot/internal/domain/valueobjects"
	"github.com/vuongmanhnghia/discord-music-bot/internal/services"
	"github.com/vuongmanhnghia/discord-music-bot/internal/services/youtube"
	"github.com/vuongmanhnghia/discord-music-bot/pkg/logger"
)

// Handler manages all bot commands
type Handler struct {
	session         *discordgo.Session
	playbackService *services.PlaybackService
	playlistService *services.PlaylistService
	ytService       *youtube.Service
	logger          *logger.Logger

	// Track active playlist per guild
	activePlaylist   map[string]string
	activePlaylistMu sync.RWMutex
}

// NewHandler creates a new command handler
func NewHandler(
	session *discordgo.Session,
	playbackSvc *services.PlaybackService,
	playlistSvc *services.PlaylistService,
	ytSvc *youtube.Service,
	log *logger.Logger,
) *Handler {
	return &Handler{
		session:         session,
		playbackService: playbackSvc,
		playlistService: playlistSvc,
		ytService:       ytSvc,
		logger:          log,
		activePlaylist:  make(map[string]string),
	}
}

// RegisterCommands registers all slash commands
func (h *Handler) RegisterCommands() error {
	commands := []*discordgo.ApplicationCommand{
		{
			Name:        "play",
			Description: "Play a song from YouTube URL or search query",
			Options: []*discordgo.ApplicationCommandOption{
				{
					Type:        discordgo.ApplicationCommandOptionString,
					Name:        "query",
					Description: "YouTube URL or search query",
					Required:    true,
				},
			},
		},
		{
			Name:        "pause",
			Description: "Pause the current song",
		},
		{
			Name:        "resume",
			Description: "Resume playback",
		},
		{
			Name:        "skip",
			Description: "Skip the current song",
		},
		{
			Name:        "stop",
			Description: "Stop playback and clear the queue",
		},
		{
			Name:        "queue",
			Description: "Show the current queue",
		},
		{
			Name:        "nowplaying",
			Description: "Show the currently playing song",
		},
		{
			Name:        "repeat",
			Description: "Set repeat mode",
			Options: []*discordgo.ApplicationCommandOption{
				{
					Type:        discordgo.ApplicationCommandOptionString,
					Name:        "mode",
					Description: "Repeat mode",
					Required:    true,
					Choices: []*discordgo.ApplicationCommandOptionChoice{
						{Name: "Off", Value: "none"},
						{Name: "Track", Value: "track"},
						{Name: "Queue", Value: "queue"},
					},
				},
			},
		},
		{
			Name:        "shuffle",
			Description: "Shuffle the queue",
		},
		{
			Name:        "clear",
			Description: "Clear the queue",
		},
		{
			Name:        "aplay",
			Description: "Add all songs from a YouTube playlist to queue",
			Options: []*discordgo.ApplicationCommandOption{
				{
					Type:        discordgo.ApplicationCommandOptionString,
					Name:        "url",
					Description: "YouTube playlist URL",
					Required:    true,
				},
			},
		},
		// Playlist commands
		{
			Name:        "playlists",
			Description: "List all available playlists",
		},
		{
			Name:        "use",
			Description: "Load and play a playlist",
			Options: []*discordgo.ApplicationCommandOption{
				{
					Type:        discordgo.ApplicationCommandOptionString,
					Name:        "name",
					Description: "Playlist name",
					Required:    true,
				},
			},
		},
		{
			Name:        "playlist",
			Description: "Manage playlists",
			Options: []*discordgo.ApplicationCommandOption{
				{
					Type:        discordgo.ApplicationCommandOptionSubCommand,
					Name:        "create",
					Description: "Create a new playlist",
					Options: []*discordgo.ApplicationCommandOption{
						{
							Type:        discordgo.ApplicationCommandOptionString,
							Name:        "name",
							Description: "Playlist name",
							Required:    true,
						},
					},
				},
				{
					Type:        discordgo.ApplicationCommandOptionSubCommand,
					Name:        "delete",
					Description: "Delete a playlist",
					Options: []*discordgo.ApplicationCommandOption{
						{
							Type:        discordgo.ApplicationCommandOptionString,
							Name:        "name",
							Description: "Playlist name",
							Required:    true,
						},
					},
				},
				{
					Type:        discordgo.ApplicationCommandOptionSubCommand,
					Name:        "show",
					Description: "Show playlist contents",
					Options: []*discordgo.ApplicationCommandOption{
						{
							Type:        discordgo.ApplicationCommandOptionString,
							Name:        "name",
							Description: "Playlist name",
							Required:    true,
						},
					},
				},
				{
					Type:        discordgo.ApplicationCommandOptionSubCommand,
					Name:        "add",
					Description: "Add a song to playlist",
					Options: []*discordgo.ApplicationCommandOption{
						{
							Type:        discordgo.ApplicationCommandOptionString,
							Name:        "name",
							Description: "Playlist name",
							Required:    true,
						},
						{
							Type:        discordgo.ApplicationCommandOptionString,
							Name:        "song",
							Description: "YouTube URL or search query (leave empty to add current song)",
							Required:    false,
						},
					},
				},
			},
		},
		{
			Name:        "help",
			Description: "Show help information",
		},
		{
			Name:        "sync",
			Description: "[Admin] Force sync slash commands with Discord",
		},
		{
			Name:        "add",
			Description: "Quick add song to active playlist",
			Options: []*discordgo.ApplicationCommandOption{
				{
					Type:        discordgo.ApplicationCommandOptionString,
					Name:        "song",
					Description: "YouTube URL or search query",
					Required:    true,
				},
			},
		},
		{
			Name:        "join",
			Description: "Join your voice channel",
		},
		{
			Name:        "leave",
			Description: "Leave the voice channel",
		},
		{
			Name:        "stats",
			Description: "Show bot statistics",
		},
		{
			Name:        "volume",
			Description: "Set playback volume (0-100)",
			Options: []*discordgo.ApplicationCommandOption{
				{
					Type:        discordgo.ApplicationCommandOptionInteger,
					Name:        "level",
					Description: "Volume level (0-100)",
					Required:    true,
					MinValue:    func() *float64 { v := 0.0; return &v }(),
					MaxValue:    100,
				},
			},
		},
		{
			Name:        "remove",
			Description: "Remove a song from playlist by index",
			Options: []*discordgo.ApplicationCommandOption{
				{
					Type:        discordgo.ApplicationCommandOptionString,
					Name:        "playlist",
					Description: "Playlist name",
					Required:    true,
				},
				{
					Type:        discordgo.ApplicationCommandOptionInteger,
					Name:        "index",
					Description: "Song index (1-based)",
					Required:    true,
					MinValue:    func() *float64 { v := 1.0; return &v }(),
				},
			},
		},
	}

	// Use bulk overwrite to ensure all commands are updated
	_, err := h.session.ApplicationCommandBulkOverwrite(h.session.State.User.ID, "", commands)
	if err != nil {
		return fmt.Errorf("failed to bulk overwrite commands: %w", err)
	}

	h.logger.WithField("count", len(commands)).Info("✅ All commands registered")
	return nil
}

// HandleInteraction handles slash command interactions
func (h *Handler) HandleInteraction(s *discordgo.Session, i *discordgo.InteractionCreate) {
	// Panic recovery to prevent bot crashes
	defer func() {
		if r := recover(); r != nil {
			h.logger.WithField("panic", r).Error("Recovered from panic in command handler")
			// Try to respond with error
			_ = respondError(s, i, "An internal error occurred")
		}
	}()

	if i.Type != discordgo.InteractionApplicationCommand {
		return
	}

	data := i.ApplicationCommandData()

	h.logger.WithFields(map[string]interface{}{
		"command": data.Name,
		"guild":   i.GuildID,
		"user":    i.Member.User.Username,
	}).Info("Command received")

	// Route to appropriate handler
	var err error
	switch data.Name {
	case "play":
		err = h.handlePlay(s, i)
	case "pause":
		err = h.handlePause(s, i)
	case "resume":
		err = h.handleResume(s, i)
	case "skip":
		err = h.handleSkip(s, i)
	case "stop":
		err = h.handleStop(s, i)
	case "queue":
		err = h.handleQueue(s, i)
	case "nowplaying":
		err = h.handleNowPlaying(s, i)
	case "repeat":
		err = h.handleRepeat(s, i)
	case "shuffle":
		err = h.handleShuffle(s, i)
	case "clear":
		err = h.handleClear(s, i)
	case "aplay":
		err = h.handleAPlay(s, i)
	case "playlists":
		err = h.handlePlaylists(s, i)
	case "use":
		err = h.handleUsePlaylist(s, i)
	case "playlist":
		err = h.handlePlaylistSubcommand(s, i)
	case "help":
		err = h.handleHelp(s, i)
	case "sync":
		err = h.handleSync(s, i)
	case "add":
		err = h.handleQuickAdd(s, i)
	case "join":
		err = h.handleJoin(s, i)
	case "leave":
		err = h.handleLeave(s, i)
	case "stats":
		err = h.handleStats(s, i)
	case "volume":
		err = h.handleVolume(s, i)
	case "remove":
		err = h.handleRemove(s, i)
	default:
		err = respondError(s, i, "Unknown command")
	}

	if err != nil {
		h.logger.WithError(err).Error("Command handler failed")
	}
}

// handlePlay handles the play command
func (h *Handler) handlePlay(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	// Defer response
	if err := s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseDeferredChannelMessageWithSource,
	}); err != nil {
		return err
	}

	// Get query
	options := i.ApplicationCommandData().Options
	query := options[0].StringValue()

	// Get user's voice channel
	channelID, err := h.getUserVoiceChannel(s, i.GuildID, i.Member.User.ID)
	if err != nil {
		return followUpError(s, i, "You must be in a voice channel!")
	}

	// Create song
	song := entities.NewSong(query, valueobjects.SourceTypeYouTube, i.Member.User.ID, i.GuildID)

	// Add to queue
	if err := h.playbackService.AddSong(i.GuildID, song); err != nil {
		return followUpError(s, i, fmt.Sprintf("Failed to add song: %v", err))
	}

	// Start playback if not playing
	if !h.playbackService.IsPlaying(i.GuildID) {
		if err := h.playbackService.Play(i.GuildID, channelID); err != nil {
			return followUpError(s, i, fmt.Sprintf("Failed to start playback: %v", err))
		}
	}

	return followUp(s, i, fmt.Sprintf("🎵 Added to queue: **%s**", query))
}

// handlePause handles the pause command
func (h *Handler) handlePause(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	if err := h.playbackService.Pause(i.GuildID); err != nil {
		return respondError(s, i, "Nothing is playing!")
	}
	return respond(s, i, "⏸️ Paused")
}

// handleResume handles the resume command
func (h *Handler) handleResume(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	if err := h.playbackService.Resume(i.GuildID); err != nil {
		return respondError(s, i, "Nothing is paused!")
	}
	return respond(s, i, "▶️ Resumed")
}

// handleSkip handles the skip command
func (h *Handler) handleSkip(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	if err := h.playbackService.Skip(i.GuildID); err != nil {
		return respondError(s, i, "Nothing is playing!")
	}
	return respond(s, i, "⏭️ Skipped")
}

// handleStop handles the stop command
func (h *Handler) handleStop(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	if err := h.playbackService.Stop(i.GuildID); err != nil {
		return respondError(s, i, "Nothing is playing!")
	}

	tracklist := h.playbackService.GetTracklist(i.GuildID)
	if tracklist != nil {
		tracklist.Clear()
	}

	return respond(s, i, "⏹️ Stopped and cleared queue")
}

// handleQueue handles the queue command
func (h *Handler) handleQueue(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	tracklist := h.playbackService.GetTracklist(i.GuildID)
	if tracklist == nil || tracklist.Size() == 0 {
		return respond(s, i, "Queue is empty")
	}

	// Build queue display
	embed := &discordgo.MessageEmbed{
		Title: "🎵 Queue",
		Color: 0x3498db,
	}

	current := tracklist.CurrentSong()
	if current != nil && current.GetMetadata() != nil {
		embed.Fields = append(embed.Fields, &discordgo.MessageEmbedField{
			Name:   "Now Playing",
			Value:  fmt.Sprintf("**%s**", current.GetMetadata().Title),
			Inline: false,
		})
	}

	// Show next 10 songs
	upcoming := tracklist.GetUpcoming(10)
	if len(upcoming) > 0 {
		var sb strings.Builder
		for i, song := range upcoming {
			if song.GetMetadata() != nil {
				sb.WriteString(fmt.Sprintf("%d. %s\n", i+1, song.GetMetadata().Title))
			}
		}
		embed.Fields = append(embed.Fields, &discordgo.MessageEmbedField{
			Name:   "Up Next",
			Value:  sb.String(),
			Inline: false,
		})
	}

	embed.Footer = &discordgo.MessageEmbedFooter{
		Text: fmt.Sprintf("Total: %d songs | Repeat: %s", tracklist.Size(), tracklist.GetRepeatMode()),
	}

	return s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseChannelMessageWithSource,
		Data: &discordgo.InteractionResponseData{
			Embeds: []*discordgo.MessageEmbed{embed},
		},
	})
}

// handleNowPlaying handles the nowplaying command
func (h *Handler) handleNowPlaying(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	tracklist := h.playbackService.GetTracklist(i.GuildID)
	if tracklist == nil {
		return respondError(s, i, "Nothing is playing!")
	}

	current := tracklist.CurrentSong()
	if current == nil || current.GetMetadata() == nil {
		return respondError(s, i, "Nothing is playing!")
	}

	metadata := current.GetMetadata()
	embed := &discordgo.MessageEmbed{
		Title:       "🎵 Now Playing",
		Description: fmt.Sprintf("**%s**", metadata.Title),
		Color:       0x3498db,
		Thumbnail: &discordgo.MessageEmbedThumbnail{
			URL: metadata.Thumbnail,
		},
		Fields: []*discordgo.MessageEmbedField{
			{
				Name:   "Duration",
				Value:  metadata.DurationFormatted(),
				Inline: true,
			},
		},
	}

	if metadata.Uploader != "" {
		embed.Fields = append(embed.Fields, &discordgo.MessageEmbedField{
			Name:   "Uploader",
			Value:  metadata.Uploader,
			Inline: true,
		})
	}

	return s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseChannelMessageWithSource,
		Data: &discordgo.InteractionResponseData{
			Embeds: []*discordgo.MessageEmbed{embed},
		},
	})
}

// handleRepeat handles the repeat command
func (h *Handler) handleRepeat(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	tracklist := h.playbackService.GetTracklist(i.GuildID)
	if tracklist == nil {
		return respondError(s, i, "No active playback!")
	}

	options := i.ApplicationCommandData().Options
	modeStr := options[0].StringValue()

	var mode entities.RepeatMode
	switch modeStr {
	case "none":
		mode = entities.RepeatModeNone
	case "track":
		mode = entities.RepeatModeTrack
	case "queue":
		mode = entities.RepeatModeQueue
	default:
		return respondError(s, i, "Invalid repeat mode!")
	}

	tracklist.SetRepeatMode(mode)
	return respond(s, i, fmt.Sprintf("🔁 Repeat mode: **%s**", mode))
}

// handleShuffle handles the shuffle command
func (h *Handler) handleShuffle(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	tracklist := h.playbackService.GetTracklist(i.GuildID)
	if tracklist == nil || tracklist.Size() == 0 {
		return respondError(s, i, "Queue is empty!")
	}

	tracklist.Shuffle()
	return respond(s, i, fmt.Sprintf("🔀 Shuffled %d songs in queue!", tracklist.Size()))
}

// handleClear handles the clear command - resets to initial state
func (h *Handler) handleClear(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	// Stop playback
	h.playbackService.Stop(i.GuildID)

	// Clear queue
	if tracklist := h.playbackService.GetTracklist(i.GuildID); tracklist != nil {
		tracklist.Clear()
	}

	// Clear active playlist for this guild
	h.activePlaylistMu.Lock()
	delete(h.activePlaylist, i.GuildID)
	h.activePlaylistMu.Unlock()

	return respond(s, i, "🗑️ Cleared queue and reset to initial state!")
}

// handleAPlay handles the aplay command (add YouTube playlist to queue)
func (h *Handler) handleAPlay(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	// Defer response since this can take a while
	if err := s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseDeferredChannelMessageWithSource,
	}); err != nil {
		return err
	}

	options := i.ApplicationCommandData().Options
	playlistURL := options[0].StringValue()

	// Get user's voice channel
	channelID, err := h.getUserVoiceChannel(s, i.GuildID, i.Member.User.ID)
	if err != nil {
		return followUpError(s, i, "You must be in a voice channel!")
	}

	// Extract playlist
	videos, err := h.ytService.ExtractPlaylist(playlistURL)
	if err != nil {
		return followUpError(s, i, "Failed to extract playlist: "+err.Error())
	}

	if len(videos) == 0 {
		return followUpError(s, i, "Playlist is empty or invalid!")
	}

	// Add all videos to queue
	addedCount := 0
	for _, video := range videos {
		// Build YouTube URL from video ID
		videoURL := fmt.Sprintf("https://www.youtube.com/watch?v=%s", video.ID)

		song := entities.NewSong(videoURL, valueobjects.SourceTypeYouTube, i.Member.User.ID, i.GuildID)

		if err := h.playbackService.AddSong(i.GuildID, song); err != nil {
			h.logger.WithError(err).Warn("Failed to add song from playlist")
			continue
		}
		addedCount++
	}

	if addedCount == 0 {
		return followUpError(s, i, "Failed to add any songs from playlist!")
	}

	// Start playback if not playing
	if !h.playbackService.IsPlaying(i.GuildID) {
		if err := h.playbackService.Play(i.GuildID, channelID); err != nil {
			h.logger.WithError(err).Error("Failed to start playback")
		}
	}

	return followUp(s, i, fmt.Sprintf("📻 Added **%d** songs from YouTube playlist to queue!", addedCount))
}

// Helper functions

func (h *Handler) getUserVoiceChannel(s *discordgo.Session, guildID, userID string) (string, error) {
	guild, err := s.State.Guild(guildID)
	if err != nil {
		return "", err
	}

	for _, vs := range guild.VoiceStates {
		if vs.UserID == userID {
			return vs.ChannelID, nil
		}
	}

	return "", fmt.Errorf("user not in voice channel")
}

func respond(s *discordgo.Session, i *discordgo.InteractionCreate, message string) error {
	return s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseChannelMessageWithSource,
		Data: &discordgo.InteractionResponseData{
			Content: message,
		},
	})
}

func respondError(s *discordgo.Session, i *discordgo.InteractionCreate, message string) error {
	return respond(s, i, "❌ "+message)
}

func followUp(s *discordgo.Session, i *discordgo.InteractionCreate, message string) error {
	_, err := s.FollowupMessageCreate(i.Interaction, false, &discordgo.WebhookParams{
		Content: message,
	})
	return err
}

func followUpError(s *discordgo.Session, i *discordgo.InteractionCreate, message string) error {
	return followUp(s, i, "❌ "+message)
}

// handlePlaylists shows all available playlists
func (h *Handler) handlePlaylists(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	playlists, err := h.playlistService.ListPlaylists()
	if err != nil {
		return respondError(s, i, "Failed to list playlists")
	}

	if len(playlists) == 0 {
		return respond(s, i, "📋 No playlists found. Use `/playlist create <name>` to create one!")
	}

	var sb strings.Builder
	sb.WriteString("📋 **Available Playlists:**\n\n")
	for idx, name := range playlists {
		sb.WriteString(fmt.Sprintf("%d. **%s**\n", idx+1, name))
	}
	sb.WriteString("\n_Use `/use <name>` to load a playlist_")

	return respond(s, i, sb.String())
}

// handleUsePlaylist loads and plays a playlist (or sets as active if empty)
func (h *Handler) handleUsePlaylist(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	options := i.ApplicationCommandData().Options
	playlistName := options[0].StringValue()

	// Check if playlist exists
	playlist, err := h.playlistService.GetPlaylist(playlistName)
	if err != nil {
		return respondError(s, i, fmt.Sprintf("Playlist '%s' not found", playlistName))
	}

	// Set as active playlist for this guild
	h.activePlaylistMu.Lock()
	h.activePlaylist[i.GuildID] = playlistName
	h.activePlaylistMu.Unlock()

	// If playlist is empty, just set as active
	if len(playlist.Entries) == 0 {
		return respond(s, i, fmt.Sprintf("📋 Set **%s** as active playlist (empty). Use `/add <url>` or `/playlist add %s <song>` to add songs.", playlistName, playlistName))
	}

	// Defer response for loading songs
	if err := s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseDeferredChannelMessageWithSource,
	}); err != nil {
		return err
	}

	// Check voice channel
	channelID, err := h.getUserVoiceChannel(s, i.GuildID, i.Member.User.ID)
	if err != nil {
		return followUpError(s, i, "You must be in a voice channel!")
	}

	// Get playlist songs
	songs, err := h.playlistService.GetPlaylistSongs(playlistName)
	if err != nil {
		return followUpError(s, i, fmt.Sprintf("Failed to load playlist: %v", err))
	}

	// Stop current playback if any
	h.playbackService.Stop(i.GuildID)

	// Clear existing queue
	if tracklist := h.playbackService.GetTracklist(i.GuildID); tracklist != nil {
		tracklist.Clear()
	}

	// Add all songs to queue
	for _, song := range songs {
		if err := h.playbackService.AddSong(i.GuildID, song); err != nil {
			h.logger.WithError(err).Warn("Failed to add song to queue")
		}
	}

	// Start playback
	if err := h.playbackService.Play(i.GuildID, channelID); err != nil {
		return followUpError(s, i, "Failed to start playback")
	}

	return followUp(s, i, fmt.Sprintf("📻 Loaded **%s** with %d songs!", playlistName, len(songs)))
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
		name := subCmd.Options[0].StringValue()
		if err := h.playlistService.CreatePlaylist(name); err != nil {
			return respondError(s, i, err.Error())
		}
		return respond(s, i, fmt.Sprintf("✅ Created playlist **%s**", name))

	case "delete":
		name := subCmd.Options[0].StringValue()
		if err := h.playlistService.DeletePlaylist(name); err != nil {
			return respondError(s, i, err.Error())
		}
		return respond(s, i, fmt.Sprintf("🗑️ Deleted playlist **%s**", name))

	case "show":
		name := subCmd.Options[0].StringValue()
		playlist, err := h.playlistService.GetPlaylist(name)
		if err != nil {
			return respondError(s, i, err.Error())
		}

		if len(playlist.Entries) == 0 {
			return respond(s, i, fmt.Sprintf("📋 Playlist **%s** is empty", name))
		}

		var sb strings.Builder
		sb.WriteString(fmt.Sprintf("📋 **%s** (%d songs)\n\n", name, len(playlist.Entries)))
		for idx, entry := range playlist.Entries {
			if idx >= 15 { // Limit display
				sb.WriteString(fmt.Sprintf("\n_...and %d more_", len(playlist.Entries)-15))
				break
			}
			title := entry.Title
			if title == "" {
				title = entry.OriginalInput
			}
			sb.WriteString(fmt.Sprintf("%d. %s\n", idx+1, title))
		}

		return respond(s, i, sb.String())

	case "add":
		name := subCmd.Options[0].StringValue()

		// Check if song URL/query is provided
		var songQuery string
		if len(subCmd.Options) > 1 {
			songQuery = subCmd.Options[1].StringValue()
		}

		if songQuery != "" {
			// Add song by URL/query - need to defer for processing
			if err := s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
				Type: discordgo.InteractionResponseDeferredChannelMessageWithSource,
			}); err != nil {
				return err
			}

			// Extract video info
			info, err := h.ytService.ExtractInfo(songQuery)
			if err != nil {
				return followUpError(s, i, "Failed to extract song info: "+err.Error())
			}

			// Add to playlist
			err = h.playlistService.AddToPlaylist(
				name,
				info.WebpageURL,
				valueobjects.SourceTypeYouTube,
				info.Title,
			)
			if err != nil {
				return followUpError(s, i, err.Error())
			}
			return followUp(s, i, fmt.Sprintf("✅ Added **%s** to playlist **%s**", info.Title, name))
		}

		// Add current playing song
		tracklist := h.playbackService.GetTracklist(i.GuildID)
		if tracklist == nil {
			return respondError(s, i, "Nothing is playing! Use `/playlist add <name> <song>` to add by URL.")
		}

		current := tracklist.CurrentSong()
		if current == nil {
			return respondError(s, i, "No song is playing! Use `/playlist add <name> <song>` to add by URL.")
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
		return respond(s, i, fmt.Sprintf("✅ Added **%s** to playlist **%s**", current.DisplayName(), name))

	default:
		return respondError(s, i, "Unknown subcommand")
	}
}

// handleHelp shows help information
func (h *Handler) handleHelp(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	embed := &discordgo.MessageEmbed{
		Title:       "🎵 Music Bot Help",
		Description: "A Discord music bot written in Go",
		Color:       0x3498db,
		Fields: []*discordgo.MessageEmbedField{
			{
				Name: "🎵 Playback",
				Value: "`/play <query>` - Play a song\n" +
					"`/aplay <url>` - Add YouTube playlist to queue\n" +
					"`/pause` - Pause playback\n" +
					"`/resume` - Resume playback\n" +
					"`/skip` - Skip current song\n" +
					"`/stop` - Stop and clear queue\n" +
					"`/volume <0-100>` - Set volume",
				Inline: false,
			},
			{
				Name: "📋 Queue",
				Value: "`/queue` - Show queue\n" +
					"`/nowplaying` - Current song\n" +
					"`/shuffle` - Shuffle queue\n" +
					"`/clear` - Clear queue & reset state\n" +
					"`/repeat <mode>` - Set repeat mode",
				Inline: false,
			},
			{
				Name: "💾 Playlists",
				Value: "`/playlists` - List all playlists\n" +
					"`/use <name>` - Load and play a playlist\n" +
					"`/add <song>` - Quick add song to active playlist\n" +
					"`/playlist create/delete/show/add` - Manage playlists\n" +
					"`/remove <playlist> <index>` - Remove song from playlist",
				Inline: false,
			},
			{
				Name: "🔧 Utility",
				Value: "`/join` - Join voice channel\n" +
					"`/leave` - Leave voice channel\n" +
					"`/stats` - Bot statistics\n" +
					"`/help` - Show this help\n" +
					"`/sync` - [Admin] Force sync commands",
				Inline: false,
			},
		},
		Footer: &discordgo.MessageEmbedFooter{
			Text: "Discord Music Bot v2.0.0 (Go Edition)",
		},
	}

	return s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseChannelMessageWithSource,
		Data: &discordgo.InteractionResponseData{
			Embeds: []*discordgo.MessageEmbed{embed},
		},
	})
}

// handleSync handles the sync command (force re-register all commands)
func (h *Handler) handleSync(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	// Defer response since this may take a moment
	if err := s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseDeferredChannelMessageWithSource,
		Data: &discordgo.InteractionResponseData{
			Flags: discordgo.MessageFlagsEphemeral,
		},
	}); err != nil {
		return err
	}

	// Re-register all commands
	if err := h.RegisterCommands(); err != nil {
		h.logger.WithError(err).Error("Failed to sync commands")
		return followUpError(s, i, "Failed to sync commands: "+err.Error())
	}

	h.logger.WithField("user", i.Member.User.Username).Info("Commands manually synced")
	return followUp(s, i, "✅ Commands synced successfully!")
}

// handleQuickAdd quickly adds a song to the active playlist
func (h *Handler) handleQuickAdd(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	// Get active playlist for this guild
	h.activePlaylistMu.RLock()
	playlistName, hasActive := h.activePlaylist[i.GuildID]
	h.activePlaylistMu.RUnlock()

	if !hasActive || playlistName == "" {
		return respondError(s, i, "No active playlist! Use `/use <name>` first to set an active playlist.")
	}

	// Defer response for processing
	if err := s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseDeferredChannelMessageWithSource,
	}); err != nil {
		return err
	}

	options := i.ApplicationCommandData().Options
	songQuery := options[0].StringValue()

	// Extract video info
	info, err := h.ytService.ExtractInfo(songQuery)
	if err != nil {
		return followUpError(s, i, "Failed to extract song info: "+err.Error())
	}

	// Add to active playlist
	err = h.playlistService.AddToPlaylist(
		playlistName,
		info.WebpageURL,
		valueobjects.SourceTypeYouTube,
		info.Title,
	)
	if err != nil {
		return followUpError(s, i, err.Error())
	}

	return followUp(s, i, fmt.Sprintf("✅ Added **%s** to playlist **%s**", info.Title, playlistName))
}

// handleJoin handles the join command - join voice channel without playing
func (h *Handler) handleJoin(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	channelID, err := h.getUserVoiceChannel(s, i.GuildID, i.Member.User.ID)
	if err != nil {
		return respondError(s, i, "You must be in a voice channel!")
	}

	// Join the voice channel
	_, err = s.ChannelVoiceJoin(i.GuildID, channelID, false, true)
	if err != nil {
		return respondError(s, i, "Failed to join voice channel: "+err.Error())
	}

	return respond(s, i, "🔊 Joined your voice channel!")
}

// handleLeave handles the leave command - clears all state
func (h *Handler) handleLeave(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	// Stop any playback first
	h.playbackService.Stop(i.GuildID)

	// Clear queue
	if tracklist := h.playbackService.GetTracklist(i.GuildID); tracklist != nil {
		tracklist.Clear()
	}

	// Clear active playlist for this guild
	h.activePlaylistMu.Lock()
	delete(h.activePlaylist, i.GuildID)
	h.activePlaylistMu.Unlock()

	// Find and disconnect from voice
	for _, vs := range s.VoiceConnections {
		if vs.GuildID == i.GuildID {
			if err := vs.Disconnect(); err != nil {
				return respondError(s, i, "Failed to leave voice channel")
			}
			return respond(s, i, "👋 Left and cleared everything!")
		}
	}

	return respondError(s, i, "I'm not in a voice channel!")
}

// handleStats handles the stats command
func (h *Handler) handleStats(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	// Count active voice connections
	voiceCount := len(s.VoiceConnections)

	// Count guilds
	guildCount := len(s.State.Guilds)

	// Get latency
	latency := s.HeartbeatLatency().Milliseconds()

	embed := &discordgo.MessageEmbed{
		Title: "📊 Bot Statistics",
		Color: 0x3498db,
		Fields: []*discordgo.MessageEmbedField{
			{
				Name:   "🌐 Guilds",
				Value:  fmt.Sprintf("%d", guildCount),
				Inline: true,
			},
			{
				Name:   "🔊 Voice Connections",
				Value:  fmt.Sprintf("%d", voiceCount),
				Inline: true,
			},
			{
				Name:   "📶 Latency",
				Value:  fmt.Sprintf("%dms", latency),
				Inline: true,
			},
		},
		Footer: &discordgo.MessageEmbedFooter{
			Text: "Discord Music Bot v2.0.0 (Go Edition)",
		},
	}

	return s.InteractionRespond(i.Interaction, &discordgo.InteractionResponse{
		Type: discordgo.InteractionResponseChannelMessageWithSource,
		Data: &discordgo.InteractionResponseData{
			Embeds: []*discordgo.MessageEmbed{embed},
		},
	})
}

// handleVolume handles the volume command
func (h *Handler) handleVolume(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	options := i.ApplicationCommandData().Options
	level := int(options[0].IntValue())

	// Volume in Discord is 0.0 to 2.0 (100% = 1.0)
	// We'll store it and apply to FFmpeg
	if err := h.playbackService.SetVolume(i.GuildID, level); err != nil {
		return respondError(s, i, "Failed to set volume: "+err.Error())
	}

	// Visual volume bar
	bars := level / 10
	volumeBar := ""
	for j := 0; j < 10; j++ {
		if j < bars {
			volumeBar += "▓"
		} else {
			volumeBar += "░"
		}
	}

	return respond(s, i, fmt.Sprintf("🔊 Volume: %s %d%%", volumeBar, level))
}

// handleRemove handles the remove command - remove song from playlist
func (h *Handler) handleRemove(s *discordgo.Session, i *discordgo.InteractionCreate) error {
	options := i.ApplicationCommandData().Options
	playlistName := options[0].StringValue()
	index := int(options[1].IntValue())

	// Get playlist
	playlist, err := h.playlistService.GetPlaylist(playlistName)
	if err != nil {
		return respondError(s, i, err.Error())
	}

	// Validate index
	if index < 1 || index > len(playlist.Entries) {
		return respondError(s, i, fmt.Sprintf("Invalid index! Playlist has %d songs.", len(playlist.Entries)))
	}

	// Get song title before removing
	songTitle := playlist.Entries[index-1].Title
	if songTitle == "" {
		songTitle = playlist.Entries[index-1].OriginalInput
	}

	// Remove by original input
	originalInput := playlist.Entries[index-1].OriginalInput
	if err := h.playlistService.RemoveFromPlaylist(playlistName, originalInput); err != nil {
		return respondError(s, i, err.Error())
	}

	return respond(s, i, fmt.Sprintf("🗑️ Removed **%s** from playlist **%s**", songTitle, playlistName))
}
