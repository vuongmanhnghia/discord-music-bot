# 🎵 Discord Music Bot - Go Edition

> High-performance Discord music bot rewritten in Go for better performance and reliability

**Status**: 🚧 In Active Development  
**Version**: 2.0.0-alpha  
**Original**: Python 1.0.0 (Stable in production)

---

## 📊 Migration Progress

| Phase | Component           | Status         | Tests    |
| ----- | ------------------- | -------------- | -------- |
| 1     | Value Objects       | ✅ Complete    | -        |
| 1     | Domain Entities     | ✅ Complete    | 26/26 ✅ |
| 1     | Logger              | ✅ Complete    | -        |
| 1     | Config              | ✅ Complete    | -        |
| 2     | Playlist Repository | ✅ Complete    | -        |
| 3     | Bot Core            | ✅ Complete    | -        |
| 4     | Audio Service       | 🚧 In Progress | 0/10     |
| 5     | YouTube Service     | ⏳ Pending     | 0/8      |
| 6     | Playback Service    | ⏳ Pending     | 0/12     |
| 7     | Commands            | ⏳ Pending     | 0/15     |

**Overall**: 37% Complete

---

## 🎯 Why Go?

### Performance Benefits

-   **5-10x faster** startup time
-   **50-70% less memory** usage (~50MB vs ~200MB)
-   **True parallelism** with goroutines
-   **Single binary** deployment (no Python runtime needed)

### Stability Benefits

-   **Static typing** catches errors at compile time
-   **Better concurrency** primitives
-   **Easier debugging** with stack traces
-   **No GIL limitations**

### Operational Benefits

-   **Smaller Docker images** (~20MB vs ~200MB)
-   **Faster builds** (<1s vs ~30s)
-   **Cross-compilation** for ARM/x86
-   **Lower resource usage** on Raspberry Pi

---

## 🚀 Quick Start (Go Version)

### Prerequisites

```bash
# System dependencies
sudo apt install -y ffmpeg libopus-dev libsodium-dev pkg-config

# Or on macOS
brew install ffmpeg opus libsodium pkg-config

# Go 1.21+
go version  # Should be 1.21 or higher
```

### Setup

```bash
# Clone repository
git clone <repo-url>
cd discord-music-bot

# Copy environment template
cp .env.example .env

# Edit .env and add your bot token
nano .env

# Build
go build -o bin/musicbot ./cmd/bot

# Run
./bin/musicbot
```

### Development

```bash
# Install dependencies
go mod download

# Run tests
go test -v ./...

# Run with hot reload (using air)
go install github.com/cosmtrek/air@latest
air

# Format code
go fmt ./...

# Lint
golangci-lint run
```

---

## 📁 Project Structure

```
discord-music-bot/
├── cmd/
│   └── bot/
│       └── main.go                    # Entry point
├── internal/
│   ├── bot/
│   │   └── bot.go                     # Bot core
│   ├── config/
│   │   └── config.go                  # Configuration
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── song.go                # Song entity ✅
│   │   │   ├── tracklist.go           # Queue management ✅
│   │   │   ├── playlist.go            # Playlist ✅
│   │   │   └── library.go             # Library ✅
│   │   └── valueobjects/
│   │       ├── source_type.go         # Media sources ✅
│   │       ├── song_status.go         # Status enum ✅
│   │       └── song_metadata.go       # Metadata ✅
│   ├── infrastructure/
│   │   └── persistence/
│   │       └── playlist_repository.go # JSON storage ✅
│   └── services/
│       ├── audio/                     # 🚧 In Progress
│       ├── youtube/                   # ⏳ Pending
│       ├── playback/                  # ⏳ Pending
│       └── processing/                # ⏳ Pending
├── pkg/
│   └── logger/
│       └── logger.go                  # Structured logging ✅
├── go.mod                             # Dependencies ✅
└── go.sum                             # Checksums ✅
```

---

## 🔧 Architecture

### Clean Architecture

```
┌─────────────────────────────────────────┐
│     Presentation (Commands)             │
├─────────────────────────────────────────┤
│     Application (Services)              │
├─────────────────────────────────────────┤
│     Domain (Entities, Value Objects)    │
├─────────────────────────────────────────┤
│     Infrastructure (Discord, FFmpeg)    │
└─────────────────────────────────────────┘
```

### Key Components

#### 1. Domain Layer (✅ Complete)

-   **Entities**: Song, Tracklist, Playlist, Library
-   **Value Objects**: SourceType, SongStatus, Metadata
-   **Interfaces**: PlaylistRepository

#### 2. Infrastructure Layer (🚧 In Progress)

-   **Persistence**: JSON file storage with atomic writes
-   **Discord**: discordgo integration
-   **Audio**: FFmpeg + Opus + DCA pipeline

#### 3. Application Layer (⏳ Pending)

-   **AudioService**: Voice connection + playback
-   **YouTubeService**: Video info + stream extraction
-   **PlaybackService**: Complete playback flow
-   **ProcessingService**: Async song processing

#### 4. Presentation Layer (⏳ Pending)

-   **Commands**: Discord slash commands
-   **Handlers**: Command logic

---

## 🎵 Audio Pipeline (Critical Component)

### Challenge

Python's discord.py has built-in audio support. Go's discordgo requires manual implementation.

### Python (discord.py)

```python
# Simple!
audio_source = FFmpegPCMAudio(stream_url)
voice_client.play(audio_source)
```

### Go (discordgo) - Our Implementation

```go
// Complex but efficient
1. Start FFmpeg: ffmpeg -i <url> -f s16le -ar 48000 -ac 2 pipe:1
2. Read PCM data from FFmpeg stdout
3. Encode PCM → Opus frames (gopus)
4. Wrap Opus → DCA format
5. Send DCA frames to voice connection
```

### Dependencies

```go
github.com/bwmarrin/discordgo    // Discord API
layeh.com/gopus                  // Opus codec
github.com/jonas747/dca          // DCA encoder
// + FFmpeg (system dependency)
```

---

## 🧪 Testing

### Unit Tests

```bash
# Run all tests
go test -v ./...

# Run with coverage
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out

# Run specific package
go test -v ./internal/domain/entities/...
```

### Current Test Status

-   ✅ Song entity: 13/13 tests passing
-   ✅ Tracklist entity: 13/13 tests passing
-   ⏳ Audio service: 0/10 tests
-   ⏳ YouTube service: 0/8 tests
-   ⏳ Playback service: 0/12 tests

### Integration Tests (Planned)

-   [ ] Connect to voice channel
-   [ ] Play 10-second audio clip
-   [ ] Pause/resume playback
-   [ ] Skip navigation
-   [ ] Playlist loading

---

## 📚 Documentation

-   [GO_MIGRATION_PROGRESS.md](GO_MIGRATION_PROGRESS.md) - Detailed migration progress
-   [MODULES.md](MODULES.md) - Complete architecture analysis
-   [Python README](README.md) - Original Python bot documentation

---

## 🛠️ Development Tools

### Recommended VSCode Extensions

-   Go (golang.go)
-   Go Test Explorer
-   Error Lens
-   GitLens

### Useful Commands

```bash
# Generate mocks
go install github.com/golang/mock/mockgen@latest
mockgen -source=internal/domain/entities/library.go -destination=mocks/mock_repository.go

# Benchmark
go test -bench=. -benchmem ./...

# Profile
go test -cpuprofile=cpu.prof -memprofile=mem.prof -bench=.
go tool pprof cpu.prof
```

---

## 🐳 Docker (Planned)

```dockerfile
# Multi-stage build
FROM golang:1.21-alpine AS builder
RUN apk add --no-cache git ffmpeg opus libsodium
WORKDIR /app
COPY . .
RUN go build -o musicbot ./cmd/bot

FROM alpine:latest
RUN apk add --no-cache ffmpeg opus libsodium ca-certificates
COPY --from=builder /app/musicbot /musicbot
CMD ["/musicbot"]
```

---

## ⚠️ Known Issues

### Current Limitations (Work in Progress)

-   [ ] Audio playback not implemented yet
-   [ ] YouTube extraction incomplete
-   [ ] Commands not registered
-   [ ] No slash commands yet

### Python Bot Comparison

| Feature          | Python | Go  |
| ---------------- | ------ | --- |
| Play song        | ✅     | 🚧  |
| Queue management | ✅     | ✅  |
| Playlists        | ✅     | ✅  |
| Skip/pause       | ✅     | 🚧  |
| 24/7 mode        | ✅     | ⏳  |
| Auto-repeat      | ✅     | ✅  |

---

## 🎯 Roadmap

### Phase 4: Audio Service (Current Focus)

-   [ ] Voice connection management
-   [ ] FFmpeg integration
-   [ ] Opus encoding
-   [ ] DCA formatting
-   [ ] Audio player implementation

### Phase 5: YouTube & Processing

-   [ ] YouTube info extraction
-   [ ] Smart caching (LRU + TTL)
-   [ ] Worker pool for async processing
-   [ ] Stream URL refresh

### Phase 6: Playback Service

-   [ ] Complete playback loop
-   [ ] Auto-play next song
-   [ ] Playlist loading
-   [ ] Error handling

### Phase 7: Commands & UI

-   [ ] Discord slash commands
-   [ ] Command handlers
-   [ ] Embed messages
-   [ ] Progress updates

### Phase 8: Testing & Polish

-   [ ] Integration tests
-   [ ] Load testing
-   [ ] Memory profiling
-   [ ] Documentation

---

## 🤝 Contributing

This is currently in active migration. If you want to help:

1. Check [GO_MIGRATION_PROGRESS.md](GO_MIGRATION_PROGRESS.md) for current status
2. Pick an incomplete component
3. Write tests first (TDD approach)
4. Implement the component
5. Ensure all tests pass
6. Submit PR

---

## 📝 License

Same as original Python bot

---

## 🙏 Acknowledgments

-   Original Python bot by [vuongmanhnghia](https://github.com/vuongmanhnghia)
-   discordgo library by [bwmarrin](https://github.com/bwmarrin)
-   Opus encoder by [layeh](https://github.com/layeh)

---

**Status**: Foundation complete, audio implementation next  
**ETA**: Audio service complete by end of week  
**Target**: Feature parity with Python bot by end of month
