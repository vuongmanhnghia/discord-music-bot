module github.com/vuongmanhnghia/discord-music-bot

go 1.24.0

toolchain go1.24.9

require (
	github.com/bwmarrin/discordgo v0.29.0
	github.com/google/uuid v1.6.0
	github.com/jackc/pgx/v5 v5.7.6
	github.com/joho/godotenv v1.5.1
	github.com/jonas747/ogg v0.0.0-20161220051205-b4f6f4cf3757
	github.com/pressly/goose/v3 v3.26.0
	github.com/sirupsen/logrus v1.9.3
)

require (
	github.com/gorilla/websocket v1.5.3 // indirect
	github.com/jackc/pgpassfile v1.0.0 // indirect
	github.com/jackc/pgservicefile v0.0.0-20240606120523-5a60cdf6a761 // indirect
	github.com/jackc/puddle/v2 v2.2.2 // indirect
	github.com/mfridman/interpolate v0.0.2 // indirect
	github.com/sethvargo/go-retry v0.3.0 // indirect
	go.uber.org/multierr v1.11.0 // indirect
	golang.org/x/crypto v0.40.0 // indirect
	golang.org/x/sync v0.16.0 // indirect
	golang.org/x/sys v0.39.0 // indirect
	golang.org/x/text v0.27.0 // indirect
)

// Use Richy-Z fork with aead_aes256_gcm_rtpsize encryption support (master branch)
replace github.com/bwmarrin/discordgo => github.com/Richy-Z/discordgo v0.29.1-0.20251123191524-2672c0ec4dca
