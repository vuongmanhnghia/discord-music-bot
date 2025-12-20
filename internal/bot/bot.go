package bot

import (
	"context"
	"fmt"

	"github.com/bwmarrin/discordgo"
	"github.com/vuongmanhnghia/discord-music-bot/internal/commands"
	"github.com/vuongmanhnghia/discord-music-bot/internal/config"
	"github.com/vuongmanhnghia/discord-music-bot/internal/database"
	"github.com/vuongmanhnghia/discord-music-bot/internal/services"
	"github.com/vuongmanhnghia/discord-music-bot/internal/services/audio"
	"github.com/vuongmanhnghia/discord-music-bot/internal/services/spotify"
	"github.com/vuongmanhnghia/discord-music-bot/internal/services/youtube"
	"github.com/vuongmanhnghia/discord-music-bot/pkg/logger"
)

// MusicBot represents the Discord music bot
type MusicBot struct {
	config            *config.Config
	logger            *logger.Logger
	session           *discordgo.Session
	db                *database.DB
	ytService         *youtube.Service
	spotifyService    *spotify.Service
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

	// Initialize database if configured
	var db *database.DB
	if cfg.UseDatabase {
		ctx := context.Background()
		dbCfg := database.DefaultConfig(cfg.DatabaseURL)
		db, err = database.Connect(ctx, dbCfg)
		if err != nil {
			return nil, fmt.Errorf("failed to connect to database: %w", err)
		}

		// Run migrations
		if err := db.RunMigrations(ctx); err != nil {
			db.Close()
			return nil, fmt.Errorf("failed to run database migrations: %w", err)
		}
	}

	// Initialize YouTube service
	ytService, err := youtube.NewService(log)
	if err != nil {
		if db != nil {
			db.Close()
		}
		return nil, fmt.Errorf("failed to create YouTube service: %w", err)
	}

	// Initialize Spotify service (optional)
	var spotifyService *spotify.Service
	if cfg.SpotifyClientID != "" && cfg.SpotifyClientSecret != "" {
		spotifyService, err = spotify.NewService(cfg.SpotifyClientID, cfg.SpotifyClientSecret, log)
		if err != nil {
			log.WithError(err).Warn("Failed to initialize Spotify service - Spotify links will not work")
		} else {
			log.Info("Spotify service initialized")
		}
	} else {
		log.Info("Spotify credentials not provided - Spotify links will not work")
	}

	// Initialize audio service
	audioService := audio.NewAudioService(session, log)

	// Initialize processing service with config values
	processingService := services.NewProcessingService(ytService, cfg.WorkerCount, cfg.MaxQueueSize, log)

	// Initialize playback service
	playbackService := services.NewPlaybackService(session, audioService, processingService, log)

	// Initialize playlist service (with or without database)
	var playlistService *services.PlaylistService
	if cfg.UseDatabase && db != nil {
		playlistService = services.NewPlaylistServiceWithDB(db, log)
		log.Info("Using database for playlist storage")
	} else {
		playlistService = services.NewPlaylistService(cfg.PlaylistDir, log)
		log.Info("Using file-based playlist storage")
	}

	// Initialize command handler
	cmdHandler := commands.NewHandler(session, playbackService, playlistService, ytService, spotifyService, log, cfg)

	bot := &MusicBot{
		config:            cfg,
		logger:            log,
		session:           session,
		db:                db,
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
	session.AddHandler(bot.onVoiceStateUpdate)

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

	// Close database connection
	if b.db != nil {
		b.db.Close()
	}

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
	b.logger.Infof("🔧 24/7 Mode: %v", b.config.StayConnected247)

	// Set bot status
	if err := s.UpdateGameStatus(0, "🎵 Music Bot - /help"); err != nil {
		b.logger.WithError(err).Warn("Failed to update status")
	}
}

// onVoiceStateUpdate handles voice state updates (user joins/leaves voice channels)
func (b *MusicBot) onVoiceStateUpdate(s *discordgo.Session, event *discordgo.VoiceStateUpdate) {
	// Skip if 24/7 mode is enabled - never auto-disconnect
	if b.config.StayConnected247 {
		return
	}

	// Skip if the event is about the bot itself
	if event.UserID == s.State.User.ID {
		return
	}

	guildID := event.GuildID

	// Check if bot is connected to any voice channel in this guild
	botChannelID := b.audioService.GetVoiceChannelID(guildID)
	if botChannelID == "" {
		// Bot is not connected in this guild
		return
	}

	// Check if the user left the bot's channel
	// event.BeforeUpdate contains the previous voice state
	if event.BeforeUpdate == nil {
		// User joined a channel, not left
		return
	}

	// Only care if user was in the bot's channel before
	if event.BeforeUpdate.ChannelID != botChannelID {
		return
	}

	// Now check how many users are still in the bot's channel
	voiceChannel, err := s.State.Channel(botChannelID)
	if err != nil {
		b.logger.WithError(err).Warn("Failed to get voice channel state")
		return
	}

	// Count users in the voice channel (excluding bots)
	userCount := 0
	guild, err := s.State.Guild(guildID)
	if err != nil {
		b.logger.WithError(err).Warn("Failed to get guild state")
		return
	}

	for _, vs := range guild.VoiceStates {
		if vs.ChannelID == botChannelID && vs.UserID != s.State.User.ID {
			// Check if user is not a bot
			member, err := s.GuildMember(guildID, vs.UserID)
			if err != nil {
				continue
			}
			if member.User != nil && !member.User.Bot {
				userCount++
			}
		}
	}

	b.logger.WithFields(map[string]interface{}{
		"guild":     guildID,
		"channel":   voiceChannel.Name,
		"userCount": userCount,
	}).Debug("Voice state update - checking user count")

	// If no users left in the channel, disconnect
	if userCount == 0 {
		b.logger.WithFields(map[string]interface{}{
			"guild":   guildID,
			"channel": voiceChannel.Name,
		}).Info("No users in voice channel, disconnecting...")

		if err := b.audioService.DisconnectFromGuild(guildID); err != nil {
			b.logger.WithError(err).Warn("Failed to disconnect from guild")
		}
	}
}
