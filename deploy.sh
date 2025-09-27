#!/bin/bash
# Universal deployment script for Discord Music Bot
# Works on both x86_64 and ARM64 (Raspberry Pi)

set -e

echo "🎵 Discord Music Bot - Universal Deployment"
echo "==========================================="

# Detect architecture
ARCH=$(uname -m)
echo "📊 Detected architecture: $ARCH"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Installing..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    echo "✅ Docker installed. Please logout and login again."
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found. Installing..."
    if [[ "$ARCH" == "aarch64" || "$ARCH" == "armv7l" ]]; then
        # ARM installation
        sudo apt-get update && sudo apt-get install -y docker-compose
    else
        # x86_64 installation
        sudo curl -L "https://github.com/docker/compose/releases/download/v2.23.3/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
    fi
fi

# Check .env file
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Creating from template..."
    cp env.example .env
    echo ""
    echo "📝 Please edit .env file with your Discord bot token:"
    echo "   nano .env"
    echo "   Set: BOT_TOKEN=your_discord_bot_token_here"
    echo ""
    exit 1
fi

# Verify BOT_TOKEN
if ! grep -q "BOT_TOKEN=.*[^[:space:]]" .env || grep -q "BOT_TOKEN=your_discord_bot_token_here" .env; then
    echo "❌ BOT_TOKEN not properly set in .env file"
    echo "📝 Please edit .env file with your actual Discord bot token"
    exit 1
fi

echo "🔧 Building universal Docker image..."
echo "    This will work on $ARCH architecture"

# Build and start
docker-compose build --no-cache
docker-compose up -d

echo ""
echo "✅ Discord Music Bot deployed successfully!"
echo ""
echo "📊 Platform: $ARCH"
echo "🔍 Status: $(docker-compose ps --services --filter status=running | wc -l)/1 services running"
echo ""
echo "📋 Useful commands:"
echo "   View logs:     docker-compose logs -f"
echo "   Stop bot:      docker-compose down"
echo "   Restart bot:   docker-compose restart"
echo "   Update bot:    git pull && ./deploy.sh"
echo ""

# Show initial logs
echo "📱 Bot startup logs:"
docker-compose logs --tail=20
