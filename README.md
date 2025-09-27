# 🎵 Discord Music Bot - Universal Edition

**Một bot nhạc Discord tối ưu cho cả x86_64 và ARM64 (Raspberry Pi) với tự động optimization**

## 🚀 Quick Start

### Prerequisites

-   Docker and Docker Compose
-   Discord Bot Token

### Environment Setup

1. Copy the environment template:

    ```bash
    cp env.example .env
    ```

2. Edit `.env` and add your Discord bot token:
    ```
    BOT_TOKEN=your_bot_token_here
    ```

### Running with Docker Compose (Recommended)

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down
```

## 🏗️ Building

### Recommended: Docker Compose Build

```bash
# Build for current platform (automatically detects x86_64 or ARM64)
docker-compose build

# Run after building
docker-compose up -d
```

### Alternative Build Methods

#### Local Build (Auto-detect platform)

```bash
./build-local.sh [tag]
```

#### Multi-platform Build (Local - no push)

```bash
./build-simple.sh [tag]
```

#### Multi-platform Build (With registry push)

```bash
# Build only
./build-multiplatform.sh [tag]

# Build and push to Docker Hub (requires login)
./build-multiplatform.sh [tag] --push
```

#### Manual Build

```bash
# For current platform
docker build -t discord-music-bot .

# For specific platform
docker build --platform linux/amd64 -t discord-music-bot .
docker build --platform linux/arm64 -t discord-music-bot .
```

## 🖥️ Platform Support

| Platform         | Architecture | Status       |
| ---------------- | ------------ | ------------ |
| Linux x86_64     | amd64        | ✅ Supported |
| Linux ARM64      | arm64        | ✅ Supported |
| Raspberry Pi 4/5 | arm64        | ✅ Supported |
| Raspberry Pi 3   | armv7        | ❓ Untested  |

## 📁 Directory Structure

```
discord-music-bot/
├── bot/                    # Bot source code
│   ├── core/              # Core functionality
│   ├── domain/            # Domain models
│   └── services/          # Audio services
├── playlist/              # Playlist storage
├── logs/                  # Log files
├── Dockerfile             # Multi-platform Docker image
├── docker-compose.yml     # Docker Compose configuration
├── build-local.sh         # Local build script
└── build-multiplatform.sh # Multi-platform build script
```

## 🔧 Configuration

### Resource Limits (Raspberry Pi)

The docker-compose.yml includes optimized resource limits for Raspberry Pi:

-   Memory: 256M limit, 128M reservation
-   CPU: 0.5 limit, 0.25 reservation

### Health Checks

-   Interval: 30 seconds
-   Timeout: 10 seconds
-   Retries: 3
-   Start period: 40 seconds

## 📋 Development

### Requirements

-   Python 3.12+
-   discord.py
-   PyNaCl (for audio)
-   FFmpeg

### Installing Dependencies

```bash
pip install -r requirements.txt
```

### Running Locally

```bash
python run_bot.py
```

## 🐳 Docker Details

### Base Image

-   **Base**: `python:3.12-alpine`
-   **Size**: Optimized for minimal footprint
-   **Security**: Non-root user execution

### Multi-stage Build

1. **Builder stage**: Compiles dependencies
2. **Production stage**: Runtime environment only

### Volume Mounts

-   `./playlist:/home/bot/playlist` - Persistent playlist storage
-   `./logs:/home/bot/logs` - Log file storage

## 🛠️ Troubleshooting

### Docker Buildx Setup

If multi-platform builds fail:

```bash
# Install buildx (if not available)
docker buildx create --name multiplatform-builder --driver docker-container --bootstrap
docker buildx use multiplatform-builder
```

### Raspberry Pi Specific Issues

-   Ensure you're using ARM64 version of Ubuntu/Raspberry Pi OS
-   Increase swap space if memory is limited:
    ```bash
    sudo dphys-swapfile swapoff
    sudo nano /etc/dphys-swapfile  # Set CONF_SWAPSIZE=1024
    sudo dphys-swapfile setup
    sudo dphys-swapfile swapon
    ```

### Common Issues

-   **Out of memory**: Reduce resource limits in docker-compose.yml
-   **FFmpeg not found**: Rebuild the Docker image
-   **Audio issues**: Check Discord bot permissions

## 📝 License

This project is open source. Please check the license file for details.
