#!/usr/bin/env bash
set -e

# Get image tag from .env or use 'latest'
IMAGE_TAG=${IMAGE_TAG:-latest}
IMAGE_NAME="nooblearn2code/discord-music-bot:${IMAGE_TAG}"

echo "🔨 Building Docker image: ${IMAGE_NAME}"
echo "⚠️  Using --no-cache to ensure fresh build..."

# Build with no cache to ensure all changes are included
docker build --no-cache --pull -t "${IMAGE_NAME}" .

echo ""
echo "✅ Build complete!"
echo "📦 Image: ${IMAGE_NAME}"
echo ""
echo "To push to Docker Hub:"
echo "  docker push ${IMAGE_NAME}"
echo ""
echo "To deploy on server:"
echo "  docker pull ${IMAGE_NAME}"
echo "  docker-compose down"
echo "  docker-compose up -d"
