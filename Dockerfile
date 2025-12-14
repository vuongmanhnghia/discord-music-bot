# =============================================================================
# Discord Music Bot - Multi-stage Dockerfile
# =============================================================================
# Build: docker build -t discord-music-bot .
# Run:   docker run -d --env-file .env -v $(pwd)/playlist:/app/playlist discord-music-bot
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Build
# -----------------------------------------------------------------------------
FROM golang:1.23-alpine AS builder

# Build arguments
ARG VERSION=2.0.0
ARG BUILD_TIME

# Install build dependencies
RUN apk add --no-cache git ca-certificates tzdata

WORKDIR /build

# Copy go modules first for better caching
COPY go.mod go.sum ./
RUN go mod download && go mod verify

# Copy source code
COPY . .

# Build the binary
RUN CGO_ENABLED=0 GOOS=linux go build \
    -ldflags="-w -s -X main.Version=${VERSION} -X main.BuildTime=${BUILD_TIME}" \
    -o music-bot \
    ./cmd/bot

# -----------------------------------------------------------------------------
# Stage 2: Runtime
# -----------------------------------------------------------------------------
FROM alpine:3.20 AS runtime

# Install runtime dependencies
RUN apk add --no-cache \
    ca-certificates \
    tzdata \
    ffmpeg \
    python3 \
    py3-pip \
    && pip3 install --break-system-packages --no-cache-dir yt-dlp \
    && rm -rf /root/.cache

# Create non-root user for security
RUN addgroup -g 1000 bot && \
    adduser -u 1000 -G bot -h /app -D bot

WORKDIR /app

# Copy binary from builder
COPY --from=builder /build/music-bot .

# Create directories
RUN mkdir -p playlist logs && \
    chown -R bot:bot /app

# Copy config files if any
COPY --chown=bot:bot playlist/ ./playlist/

# Switch to non-root user
USER bot

# Environment variables
ENV TZ=Asia/Ho_Chi_Minh
ENV LOG_LEVEL=info

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD pgrep music-bot || exit 1

# Expose no ports (Discord bot uses outbound connections only)

# Labels
LABEL org.opencontainers.image.title="Discord Music Bot"
LABEL org.opencontainers.image.description="High-performance Discord music bot built with Go"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.source="https://github.com/vuongmanhnghia/discord-music-bot"

# Run the bot
ENTRYPOINT ["./music-bot"]
