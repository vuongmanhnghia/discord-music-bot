#!/bin/bash
# Multi-platform build script for Discord Music Bot
# Supports x86_64, ARM64, and ARM v7

set -e

echo "🎵 Discord Music Bot - Multi-Platform Builder"
echo "============================================="

# Parse command line arguments
PLATFORMS="linux/amd64,linux/arm64,linux/arm/v7"
PUSH=false
TAG="discord-music-bot:latest"

while [[ $# -gt 0 ]]; do
    case $1 in
        --platforms)
            PLATFORMS="$2"
            shift 2
            ;;
        --push)
            PUSH=true
            shift
            ;;
        --tag)
            TAG="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "OPTIONS:"
            echo "  --platforms PLATFORMS    Comma-separated list of platforms (default: linux/amd64,linux/arm64,linux/arm/v7)"
            echo "  --push                   Push to registry after build"
            echo "  --tag TAG                Image tag (default: discord-music-bot:latest)"
            echo "  --help                   Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                          # Build for all platforms locally"
            echo "  $0 --platforms linux/arm64                  # Build only for ARM64"
            echo "  $0 --push --tag myregistry/music-bot:latest # Build and push to registry"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "🎯 Target platforms: $PLATFORMS"
echo "📦 Image tag: $TAG"
echo "📤 Push to registry: $PUSH"
echo ""

# Check if Docker buildx is available
if ! docker buildx version &> /dev/null; then
    echo "❌ Docker buildx not found. Please install Docker Desktop or enable buildx"
    exit 1
fi

# Create or use existing builder
echo "🛠️  Setting up Docker buildx builder..."
docker buildx create --name multiarch-builder --use 2>/dev/null || docker buildx use multiarch-builder

# Enable experimental features for multi-platform
export DOCKER_CLI_EXPERIMENTAL=enabled

# Build command
BUILD_CMD="docker buildx build"
BUILD_CMD="$BUILD_CMD --platform $PLATFORMS"
BUILD_CMD="$BUILD_CMD --tag $TAG"

if [ "$PUSH" = true ]; then
    BUILD_CMD="$BUILD_CMD --push"
else
    BUILD_CMD="$BUILD_CMD --load"
fi

BUILD_CMD="$BUILD_CMD ."

echo "🚀 Building multi-platform image..."
echo "📋 Command: $BUILD_CMD"
echo ""

# Execute build
eval $BUILD_CMD

echo ""
if [ "$PUSH" = true ]; then
    echo "✅ Multi-platform image built and pushed successfully!"
else
    echo "✅ Multi-platform image built successfully!"
fi

echo ""
echo "📊 Build summary:"
echo "   Platforms: $PLATFORMS"
echo "   Tag: $TAG"
echo "   Pushed: $PUSH"
echo ""

# Show available images
echo "📋 Available images:"
docker images | grep -E "(${TAG}|REPOSITORY)" || echo "No local images found (pushed to registry)"

echo ""
echo "🔧 Next steps:"
if [ "$PUSH" = false ]; then
    echo "   • Run with: docker run --rm -it $TAG"
    echo "   • Or use docker-compose: docker-compose up"
else
    echo "   • Pull on target platform: docker pull $TAG"
    echo "   • Run on any supported platform: docker run --rm -it $TAG"
fi
echo "   • Test on different architectures using: docker run --platform <platform> $TAG"
