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

#### Auto-Deploy Script (Recommended)

```bash
# Automatically detects platform and builds optimally
./deploy.sh
```

#### Multi-platform Build (Advanced)

```bash
# Build for all platforms (amd64, arm64, armv7)
./build-multiplatform.sh

# Build for specific platform only
./build-multiplatform.sh --platforms linux/arm64

# Build and push to registry
./build-multiplatform.sh --push --tag myregistry/music-bot:latest

# See all options
./build-multiplatform.sh --help
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

| Platform            | Architecture | Docker Platform | Status       | Performance Notes        |
| ------------------- | ------------ | --------------- | ------------ | ------------------------ |
| Linux x86_64        | amd64        | linux/amd64     | ✅ Supported | Optimal performance      |
| Linux ARM64         | arm64        | linux/arm64     | ✅ Supported | Optimized for ARM64      |
| Raspberry Pi 4/5    | arm64        | linux/arm64     | ✅ Supported | Great performance        |
| Raspberry Pi 3      | armv7        | linux/arm/v7    | ✅ Supported | Good performance         |
| macOS Intel         | amd64        | linux/amd64     | ✅ Supported | Via Docker Desktop       |
| macOS Apple Silicon | arm64        | linux/arm64     | ✅ Supported | Native ARM64 performance |

### Automatic Platform Detection

The deployment script automatically detects your platform and applies optimal settings:

-   **x86_64**: Standard optimizations, full CPU utilization
-   **ARM64**: ARM-specific compiler flags, optimized thread management
-   **ARMv7**: Conservative resource limits, compatibility mode

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

### Platform-Specific Optimizations

#### x86_64 Systems

-   Full resource utilization
-   Standard Python optimizations
-   Efficient memory management

#### ARM64 Systems (Raspberry Pi 4/5)

-   ARM64-specific compiler optimizations (`-mcpu=native`)
-   Optimized thread management (`OMP_NUM_THREADS=4`)
-   Enhanced Python bytecode optimization (`PYTHONOPTIMIZE=2`)

#### ARMv7 Systems (Raspberry Pi 3)

-   Conservative resource allocation
-   Compatibility-focused build settings
-   Reduced memory footprint

### Resource Limits

Dynamic resource allocation based on detected platform:

-   **Memory**: 512M limit, 256M reservation
-   **CPU**: 1.0 limit, 0.5 reservation
-   **Optimized** for both x86_64 and ARM architectures

### Health Checks

-   Interval: 60 seconds
-   Timeout: 15 seconds
-   Retries: 3
-   Start period: 45 seconds
-   Platform-aware health reporting

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

### Multi-Stage Build Architecture

The Dockerfile uses a sophisticated multi-stage build approach for optimal image size and performance:

#### Stage 1: Builder (`python:3.12-slim AS builder`)
- **Purpose**: Compile dependencies and create wheels
- **Includes**: Full build toolchain (gcc, g++, make, pkg-config)
- **Platform optimization**: ARM64-specific cross-compilation tools
- **Output**: Pre-compiled Python wheels for all dependencies

#### Stage 2: Runtime (`python:3.12-slim AS runtime`)  
- **Purpose**: Minimal production environment
- **Includes**: Only runtime libraries (no build tools)
- **Size**: ~70% smaller than single-stage builds
- **Security**: Non-root user execution

### Build Process Benefits

1. **Faster builds**: Pre-compiled wheels eliminate compilation on target
2. **Smaller images**: No build dependencies in final image
3. **Better caching**: Separate stages for better Docker layer caching
4. **Platform agnostic**: Same build process for all architectures

### Image Specifications

- **Base**: `python:3.12-slim` (Debian-based for better compatibility)
- **Final size**: ~200MB (vs ~400MB+ single-stage)
- **Security**: Non-root user (`bot:1000`)
- **Optimization**: Platform-specific compiler flags

### Volume Mounts

-   `./playlist:/home/bot/playlist` - Persistent playlist storage
-   `./logs:/home/bot/logs` - Log file storage

## 🌐 Multi-Platform Build Guide

### Prerequisites for Multi-Platform Builds

1. **Docker Buildx** (included in Docker Desktop, manual install for Linux):

    ```bash
    # Check if buildx is available
    docker buildx version

    # If not available, enable experimental features
    export DOCKER_CLI_EXPERIMENTAL=enabled
    ```

2. **QEMU emulation** (for cross-platform builds):
    ```bash
    # Install QEMU static binaries
    docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
    ```

### Building for Multiple Platforms

#### Quick Multi-Platform Build

```bash
# Build for all supported platforms
./build-multiplatform.sh

# Build for specific platforms only
./build-multiplatform.sh --platforms linux/amd64,linux/arm64
```

#### Manual Multi-Platform Build

```bash
# Create builder instance
docker buildx create --name multiarch --use

# Build for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm64,linux/arm/v7 \
  --tag discord-music-bot:multiarch \
  --load .
```

#### Registry Push (for distribution)

```bash
# Build and push to Docker Hub
./build-multiplatform.sh --push --tag username/discord-music-bot:latest

# Or manually
docker buildx build \
  --platform linux/amd64,linux/arm64,linux/arm/v7 \
  --tag username/discord-music-bot:latest \
  --push .
```

## 🛠️ Troubleshooting

### Docker Buildx Setup

If multi-platform builds fail:

```bash
# Reset and recreate builder
docker buildx rm multiarch-builder 2>/dev/null || true
docker buildx create --name multiarch-builder --driver docker-container --bootstrap
docker buildx use multiarch-builder

# Verify platforms
docker buildx ls
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
