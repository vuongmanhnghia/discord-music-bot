#!/bin/bash
# Universal deployment script for Discord Music Bot
# Works on both x86_64 and ARM64 (Raspberry Pi) with multi-platform build support

set -e

echo "🎵 Discord Music Bot - Universal Deployment"
echo "==========================================="

# Detect architecture
ARCH=$(uname -m)
echo "📊 Detected architecture: $ARCH"

# Determine Docker platform
case $ARCH in
    x86_64)
        DOCKER_PLATFORM="linux/amd64"
        ;;
    aarch64)
        DOCKER_PLATFORM="linux/arm64"
        ;;
    armv7l)
        DOCKER_PLATFORM="linux/arm/v7"
        ;;
    *)
        echo "⚠️  Unknown architecture: $ARCH, defaulting to linux/amd64"
        DOCKER_PLATFORM="linux/amd64"
        ;;
esac

echo "🐳 Docker platform: $DOCKER_PLATFORM"

# Check .env file
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Creating from template..."
    cp .env.example .env
    echo "📝 Please edit .env file with your actual Discord bot token"
    exit 1
fi

echo "Building universal Docker image..."
echo "This will work on $ARCH architecture"
echo "Platform: $DOCKER_PLATFORM"

# Build with platform specification
echo "🚀 Building for platform: $DOCKER_PLATFORM"
DOCKER_PLATFORM=$DOCKER_PLATFORM TARGETPLATFORM=$DOCKER_PLATFORM TARGETARCH=$ARCH DOCKER_BUILDKIT=1 docker-compose up --build --force-recreate -d

echo ""
echo "✅ Discord Music Bot built successfully!"
echo ""
echo "📊 Platform: $ARCH ($DOCKER_PLATFORM)"
echo "🔍 Status: $(docker-compose ps --services --filter status=running | wc -l)/1 services running"
echo ""
echo "📋 Useful commands:"
echo "   View logs:     docker-compose logs -f"
echo "   Stop bot:      docker-compose down"
echo "   Restart bot:   docker-compose restart"
echo "   Update bot:    git pull && ./deploy.sh"
echo ""
