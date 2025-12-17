package commands

import (
	"fmt"
	"sync"

	"github.com/bwmarrin/discordgo"
	"github.com/vuongmanhnghia/discord-music-bot/internal/config"
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
	config          *config.Config

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
	config *config.Config,
) *Handler {
	return &Handler{
		session:         session,
		playbackService: playbackSvc,
		playlistService: playlistSvc,
		ytService:       ytSvc,
		logger:          log,
		config:          config,
		activePlaylist:  make(map[string]string),
	}
}

// RegisterCommands registers all slash commands with Discord
func (h *Handler) RegisterCommands() error {
	commands := GetCommands()

	_, err := h.session.ApplicationCommandBulkOverwrite(h.session.State.User.ID, "", commands)
	if err != nil {
		return fmt.Errorf("failed to register commands: %w", err)
	}

	h.logger.WithField("count", len(commands)).Info("✅ All commands registered")
	return nil
}

// HandleInteraction routes incoming interactions to appropriate handlers
func (h *Handler) HandleInteraction(s *discordgo.Session, i *discordgo.InteractionCreate) {
	// Panic recovery
	defer func() {
		if r := recover(); r != nil {
			h.logger.WithField("panic", r).Error("Recovered from panic in command handler")
			_ = respondError(s, i, "An internal error occurred")
		}
	}()

	// Handle button interactions (pagination)
	if i.Type == discordgo.InteractionMessageComponent {
		h.handleButtonInteraction(s, i)
		return
	}

	if i.Type != discordgo.InteractionApplicationCommand {
		return
	}

	data := i.ApplicationCommandData()

	h.logger.WithFields(map[string]interface{}{
		"command": data.Name,
		"guild":   i.GuildID,
		"user":    i.Member.User.Username,
	}).Info("Command received")

	var err error
	switch data.Name {
	// Playback commands
	case "play":
		err = h.handlePlay(s, i)
	case "aplay":
		err = h.handleAPlay(s, i)
	case "pause":
		err = h.handlePause(s, i)
	case "resume":
		err = h.handleResume(s, i)
	case "skip":
		err = h.handleSkip(s, i)
	case "stop":
		err = h.handleStop(s, i)
	case "volume":
		err = h.handleVolume(s, i)

	// Queue commands
	case "queue":
		err = h.handleQueue(s, i)
	case "nowplaying":
		err = h.handleNowPlaying(s, i)
	case "shuffle":
		err = h.handleShuffle(s, i)
	case "clear":
		err = h.handleClear(s, i)
	case "repeat":
		err = h.handleRepeat(s, i)

	// Playlist commands
	case "playlists":
		err = h.handlePlaylists(s, i)
	case "use":
		err = h.handleUsePlaylist(s, i)
	case "add":
		err = h.handleQuickAdd(s, i)
	case "remove":
		err = h.handleRemove(s, i)
	case "playlist":
		err = h.handlePlaylistSubcommand(s, i)

	// Utility commands
	case "join":
		err = h.handleJoin(s, i)
	case "leave":
		err = h.handleLeave(s, i)
	case "stats":
		err = h.handleStats(s, i)
	case "help":
		err = h.handleHelp(s, i)
	case "sync":
		err = h.handleSync(s, i)

	default:
		err = respondError(s, i, "Unknown command")
	}

	if err != nil {
		h.logger.WithError(err).WithField("command", data.Name).Error("Command handler failed")
	}
}

// getUserVoiceChannel gets the user's current voice channel
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
