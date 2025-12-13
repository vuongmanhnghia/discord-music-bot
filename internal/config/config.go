package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"

	"github.com/joho/godotenv"
)

// Config holds all application configuration
type Config struct {
	// Bot Settings
	BotToken         string
	BotName          string
	Version          string
	CommandPrefix    string
	StayConnected247 bool

	// Directories
	PlaylistDir string
	CacheDir    string

	// Logging
	LogLevel string
	LogFile  string

	// Performance
	WorkerCount          int
	MaxQueueSize         int
	CacheSizeMB          int
	CacheDurationMinutes int
}

// Load reads configuration from environment variables
func Load() (*Config, error) {
	// Try to load .env file (ignore error if not exists)
	_ = godotenv.Load()

	// Validate required variables
	botToken := os.Getenv("BOT_TOKEN")
	if botToken == "" {
		return nil, fmt.Errorf("BOT_TOKEN environment variable is required")
	}

	if len(botToken) < 50 {
		return nil, fmt.Errorf("invalid BOT_TOKEN format (too short)")
	}

	cfg := &Config{
		// Bot Settings
		BotToken:         botToken,
		BotName:          getEnvOrDefault("BOT_NAME", "Discord Music Bot"),
		Version:          getEnvOrDefault("VERSION", "2.0.0"),
		CommandPrefix:    getEnvOrDefault("COMMAND_PREFIX", "!"),
		StayConnected247: getEnvBool("STAY_CONNECTED_24_7", true),

		// Directories
		PlaylistDir: getEnvOrDefault("PLAYLIST_DIR", "./playlist"),
		CacheDir:    getEnvOrDefault("CACHE_DIR", "./cache"),

		// Logging
		LogLevel: getEnvOrDefault("LOG_LEVEL", "INFO"),
		LogFile:  getEnvOrDefault("LOG_FILE", ""),

		// Performance
		WorkerCount:          getEnvInt("WORKER_COUNT", 3),
		MaxQueueSize:         getEnvInt("MAX_QUEUE_SIZE", 100),
		CacheSizeMB:          getEnvInt("CACHE_SIZE_MB", 100),
		CacheDurationMinutes: getEnvInt("CACHE_DURATION_MINUTES", 360),
	}

	// Create directories if they don't exist
	if err := os.MkdirAll(cfg.PlaylistDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create playlist directory: %w", err)
	}

	if err := os.MkdirAll(filepath.Join(cfg.CacheDir, "songs"), 0755); err != nil {
		return nil, fmt.Errorf("failed to create cache directory: %w", err)
	}

	return cfg, nil
}

// GetSafeToken returns a masked version of the token for logging
func (c *Config) GetSafeToken() string {
	if len(c.BotToken) < 15 {
		return "***"
	}
	return c.BotToken[:10] + "..." + c.BotToken[len(c.BotToken)-4:]
}

// Helper functions

func getEnvOrDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

func getEnvBool(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		switch value {
		case "true", "1", "yes", "True", "TRUE", "YES":
			return true
		case "false", "0", "no", "False", "FALSE", "NO":
			return false
		}
	}
	return defaultValue
}
