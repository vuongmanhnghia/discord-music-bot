# 🎵 Discord Music Bot

A high-performance Discord music bot built with Go, featuring YouTube playback, playlist management, PostgreSQL storage, and seamless audio streaming.

## ✨ Features

-   🎵 **YouTube Playback** - Play songs from YouTube URLs or search queries
-   📻 **Playlist Import** - Import entire YouTube playlists
-   💾 **Custom Playlists** - Create, manage, and save your own playlists
-   🗄️ **PostgreSQL Storage** - Persistent playlist storage with database
-   🔀 **Queue Management** - Shuffle, repeat, skip, and clear functionality
-   🔊 **Volume Control** - Adjust playback volume (0-100%)
-   ⚡ **High Performance** - Built with Go for minimal resource usage
-   🐳 **Docker Ready** - Easy deployment with Docker

## 🚀 Quick Start

### Prerequisites

-   Go 1.23+ (for development)
-   Docker & Docker Compose (for deployment)
-   FFmpeg
-   yt-dlp
-   Discord Bot Token
-   PostgreSQL (optional, falls back to file-based storage)

### Environment Setup

1. Copy the environment template:

    ```bash
    cp .env.example .env
    ```

2. Edit `.env` and add your Discord bot token:

    ```env
    BOT_TOKEN=your_bot_token_here
    LOG_LEVEL=info

    # Optional: PostgreSQL for playlist storage
    POSTGRES_USER=musicbot
    POSTGRES_PASSWORD=musicbot
    POSTGRES_DB=musicbot
    ```

### Running Locally

```bash
# Build
go build -o music-bot ./cmd/bot

# Run (file-based storage)
./music-bot

# Run with PostgreSQL
DATABASE_URL="postgres://user:pass@localhost:5432/musicbot?sslmode=disable" ./music-bot
```

### Running with Docker

```bash
# Build and run (with PostgreSQL)
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

## 📋 Commands

### 🎵 Playback

| Command           | Description              |
| ----------------- | ------------------------ |
| `/play <query>`   | Play a song from YouTube |
| `/pause`          | Pause playback           |
| `/resume`         | Resume playback          |
| `/skip`           | Skip current song        |
| `/stop`           | Stop and clear queue     |
| `/volume <0-100>` | Adjust volume            |

### 📋 Queue

| Command          | Description        |
| ---------------- | ------------------ |
| `/queue`         | View current queue |
| `/nowplaying`    | Show current song  |
| `/shuffle`       | Shuffle queue      |
| `/clear`         | Clear queue        |
| `/repeat <mode>` | Set repeat mode    |

### 💾 Playlists

| Command                       | Description            |
| ----------------------------- | ---------------------- |
| `/playlists`                  | List all playlists     |
| `/use <name>`                 | Load a playlist        |
| `/add <song>`                 | Add to active playlist |
| `/playlist create <name>`     | Create playlist        |
| `/playlist delete <name>`     | Delete playlist        |
| `/playlist show <name>`       | Show playlist          |
| `/playlist add <name> <song>` | Add song to playlist   |
| `/remove <playlist> <index>`  | Remove from playlist   |

### 🔧 Utility

| Command  | Description           |
| -------- | --------------------- |
| `/join`  | Join voice channel    |
| `/leave` | Leave voice channel   |
| `/stats` | Bot statistics        |
| `/help`  | Show help             |
| `/sync`  | [Admin] Sync commands |

## 🏗️ Project Structure

```
discord-music-bot/
├── cmd/
│   └── bot/              # Main entry point
├── db/
│   ├── migrations/       # Goose SQL migrations
│   └── queries/          # sqlc query definitions
├── internal/
│   ├── bot/              # Bot setup and lifecycle
│   ├── commands/         # Slash command handlers
│   │   ├── commands.go           # Command definitions
│   │   ├── handler.go            # Main router
│   │   ├── playback_handlers.go  # Play, pause, skip, etc.
│   │   ├── queue_handlers.go     # Queue management
│   │   ├── playlist_handlers.go  # Playlist operations
│   │   ├── utility_handlers.go   # Join, leave, stats, etc.
│   │   └── response.go           # Embed builder helpers
│   ├── config/           # Configuration
│   ├── database/         # Database layer (sqlc generated)
│   │   ├── migrations/   # Embedded migrations
│   │   ├── connection.go # Connection pool & migrations
│   │   └── *.sql.go      # Generated query code
│   ├── domain/           # Domain entities & repositories
│   │   ├── entities/     # Song, Playlist entities
│   │   └── repositories/ # Storage interfaces
│   ├── services/         # Business logic
│   │   ├── audio/        # Audio player & encoding
│   │   └── youtube/      # YouTube integration
│   └── utils/            # Utilities
├── pkg/
│   └── logger/           # Logging package
├── playlist/             # Saved playlists (file fallback)
├── sqlc.yaml             # sqlc configuration
├── Dockerfile
└── docker-compose.yml
```

## 🗄️ Database

The bot uses PostgreSQL for persistent playlist storage with automatic migrations.

### Schema

| Table              | Description                         |
| ------------------ | ----------------------------------- |
| `guilds`           | Discord guild information           |
| `playlists`        | Playlist metadata per guild         |
| `playlist_entries` | Individual songs in playlists       |
| `guild_settings`   | Per-guild bot settings              |
| `active_playlists` | Currently active playlist per guild |
| `play_history`     | Song play history for statistics    |

### Migrations

Migrations are embedded in the binary and run automatically on startup using [goose](https://github.com/pressly/goose).

### sqlc

Type-safe database queries are generated using [sqlc](https://sqlc.dev/). To regenerate after modifying queries:

```bash
sqlc generate
```

## 🐳 Docker Deployment

### Build Image

```bash
docker build -t discord-music-bot .
```

### Run Container

```bash
docker run -d \
  --name music-bot \
  --env-file .env \
  -v $(pwd)/playlist:/app/playlist \
  discord-music-bot
```

### Docker Compose

```bash
# Start
docker compose up -d

# Rebuild and start
docker compose up -d --build

# View logs
docker compose logs -f discord-music-bot

# Stop
docker compose down
```

## ⚙️ Configuration

| Environment Variable  | Description                              | Default                  |
| --------------------- | ---------------------------------------- | ------------------------ |
| `BOT_TOKEN`           | Discord bot token                        | Required                 |
| `DATABASE_URL`        | PostgreSQL connection URL                | Optional (file fallback) |
| `POSTGRES_USER`       | PostgreSQL username (Docker)             | `musicbot`               |
| `POSTGRES_PASSWORD`   | PostgreSQL password (Docker)             | `musicbot`               |
| `POSTGRES_DB`         | PostgreSQL database (Docker)             | `musicbot`               |
| `PLAYLIST_DIR`        | Playlist directory (file storage)        | `./playlist`             |
| `LOG_LEVEL`           | Logging level (debug, info, warn, error) | `info`                   |
| `WORKER_COUNT`        | Processing worker threads                | `3`                      |
| `MAX_QUEUE_SIZE`      | Maximum queue size                       | `100`                    |
| `STAY_CONNECTED_24_7` | Stay in voice channel                    | `true`                   |
| `TZ`                  | Timezone                                 | `Asia/Ho_Chi_Minh`       |

## 📊 Resource Usage

The Go implementation is significantly more efficient than the Python version:

| Metric           | Python | Go    |
| ---------------- | ------ | ----- |
| Memory (idle)    | ~150MB | ~20MB |
| Memory (playing) | ~300MB | ~50MB |
| CPU (playing)    | ~10%   | ~2%   |
| Startup time     | ~5s    | ~0.5s |
| Binary size      | N/A    | ~15MB |

## 🔧 Development

### Requirements

-   Go 1.23+
-   FFmpeg
-   yt-dlp
-   sqlc (for code generation)
-   PostgreSQL (optional)

### Build

```bash
go build -o music-bot ./cmd/bot
```

### Database Development

```bash
# Generate sqlc code after modifying queries
sqlc generate

# Run migrations manually (optional, runs automatically)
# Migrations are embedded and run on startup
```

### Run Tests

```bash
go test ./...
```

### Lint

```bash
golangci-lint run
```

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

---

Built with ❤️ using Go and [discordgo](https://github.com/bwmarrin/discordgo)
