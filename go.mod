module github.com/vuongmanhnghia/discord-music-bot

go 1.24.0

toolchain go1.24.9

require (
	github.com/bwmarrin/discordgo v0.29.0
	github.com/google/uuid v1.6.0
	github.com/joho/godotenv v1.5.1
	github.com/jonas747/dca v0.0.0-20210930103944-155f5e5f0cc7
	github.com/sirupsen/logrus v1.9.3
)

require (
	github.com/gorilla/websocket v1.5.3 // indirect
	github.com/jonas747/ogg v0.0.0-20161220051205-b4f6f4cf3757 // indirect
	golang.org/x/sys v0.39.0 // indirect
)

// Use Richy-Z fork with aead_aes256_gcm_rtpsize encryption support (master branch)
replace github.com/bwmarrin/discordgo => github.com/Richy-Z/discordgo v0.29.1-0.20251123191524-2672c0ec4dca
