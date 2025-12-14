package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"

	"github.com/vuongmanhnghia/discord-music-bot/internal/bot"
	"github.com/vuongmanhnghia/discord-music-bot/internal/config"
	"github.com/vuongmanhnghia/discord-music-bot/pkg/logger"
)

func main() {
	// Initialize logger
	log := logger.New(logger.Config{
		Level:  "info",
		Format: "text",
	})

	log.Info("Starting Discord Music Bot v2.0.0 (Go Edition)")

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	log.Infof("Bot Name: %s", cfg.BotName)
	log.Infof("Stay Connected 24/7: %v", cfg.StayConnected247)

	// Initialize bot
	musicBot, err := bot.New(cfg, log)
	if err != nil {
		log.Fatalf("Failed to create bot: %v", err)
	}

	// Start bot
	ctx := context.Background()
	if err := musicBot.Start(ctx); err != nil {
		log.Fatalf("Failed to start bot: %v", err)
	}

	log.Info("✅ Bot is now running. Press CTRL-C to exit.")

	// Wait for interrupt signal
	sc := make(chan os.Signal, 1)
	signal.Notify(sc, syscall.SIGINT, syscall.SIGTERM, os.Interrupt)
	<-sc

	// Cleanup
	log.Info("Shutting down gracefully...")
	musicBot.Stop()
	log.Info("Bot stopped successfully")
}
