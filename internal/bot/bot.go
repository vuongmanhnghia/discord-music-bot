package bot

import (
	"context"
	"fmt"

	"github.com/bwmarrin/discordgo"
	"github.com/vuongmanhnghia/discord-music-bot/internal/commands"
	"github.com/vuongmanhnghia/discord-music-bot/internal/config"
	"github.com/vuongmanhnghia/discord-music-bot/internal/services"
	"github.com/vuongmanhnghia/discord-music-bot/internal/services/audio"
	"github.com/vuongmanhnghia/discord-music-bot/internal/services/youtube"
	"github.com/vuongmanhnghia/discord-music-bot/pkg/logger"
)

// MusicBot represents the Discord music bot
type MusicBot struct {
	config            *config.Config
	logger            *logger.Logger
	session           *discordgo.Session
	ytService         *youtube.Service
	audioService      *audio.AudioService
	processingService *services.ProcessingService
	playbackService   *services.PlaybackService
	playlistService   *services.PlaylistService
	cmdHandler        *commands.Handler
}

// New creates a new MusicBot instance
func New(cfg *config.Config, log *logger.Logger) (*MusicBot, error) {
	// Create Discord session
	session, err := discordgo.New("Bot " + cfg.BotToken)
	if err != nil {
		return nil, fmt.Errorf("failed to create Discord session: %w", err)
	}

	// Setup intents
	session.Identify.Intents = discordgo.IntentsGuilds |
		discordgo.IntentsGuildMessages |
		discordgo.IntentsGuildVoiceStates |
		discordgo.IntentsMessageContent

	// Set voice encryption mode
	session.StateEnabled = true

	// Initialize YouTube service
	ytService, err := youtube.NewService(log)
	if err != nil {
		return nil, fmt.Errorf("failed to create YouTube service: %w", err)
	}

	// Initialize audio service
	audioService := audio.NewAudioService(session, log)

	// Initialize processing service (4 workers, queue size 100)
	processingService := services.NewProcessingService(ytService, 4, 100, log)

	// Initialize playback service
	playbackService := services.NewPlaybackService(session, audioService, processingService, log)

	// Initialize playlist service
	playlistService := services.NewPlaylistService("playlist", log)

	// Initialize command handler
	cmdHandler := commands.NewHandler(session, playbackService, playlistService, ytService, log)

	bot := &MusicBot{
		config:            cfg,
		logger:            log,
		session:           session,
		ytService:         ytService,
		audioService:      audioService,
		processingService: processingService,
		playbackService:   playbackService,
		playlistService:   playlistService,
		cmdHandler:        cmdHandler,
	}

	// Register event handlers
	session.AddHandler(bot.onReady)
	session.AddHandler(cmdHandler.HandleInteraction)

	return bot, nil
}

// Start starts the bot
func (b *MusicBot) Start(ctx context.Context) error {
	b.logger.Info("Starting services...")

	// Start processing service
	b.processingService.Start()

	b.logger.Info("Opening Discord connection...")
	if err := b.session.Open(); err != nil {
		return fmt.Errorf("failed to open Discord connection: %w", err)
	}

	// Register commands
	b.logger.Info("Registering slash commands...")
	if err := b.cmdHandler.RegisterCommands(); err != nil {
		return fmt.Errorf("failed to register commands: %w", err)
	}

	return nil
}

// Stop stops the bot gracefully
func (b *MusicBot) Stop() {
	b.logger.Info("Shutting down services...")

	// Stop processing service
	b.processingService.Stop()

	// Cleanup all audio resources
	b.audioService.CleanupAll()

	// Close Discord connection
	b.logger.Info("Closing Discord connection...")
	if err := b.session.Close(); err != nil {
		b.logger.WithError(err).Error("Failed to close Discord session")
	}
}

// onReady is called when the bot is ready
func (b *MusicBot) onReady(s *discordgo.Session, event *discordgo.Ready) {
	b.logger.Infof("✅ Bot is ready! Logged in as %s#%s", event.User.Username, event.User.Discriminator)
	b.logger.Infof("📊 Connected to %d guilds", len(event.Guilds))

	// Set bot status
	if err := s.UpdateGameStatus(0, "🎵 /play to start"); err != nil {
		b.logger.WithError(err).Warn("Failed to update status")
	}
}
