FROM golang:1.24-alpine AS builder

RUN apk add --no-cache git ca-certificates

WORKDIR /build

# Cache dependencies
COPY go.mod go.sum ./
RUN go mod download

# Build binaries
RUN go install github.com/pressly/goose/v3/cmd/goose@latest
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o music-bot ./cmd/bot

# ============================================

FROM alpine:latest

# Install runtime deps in one layer
RUN apk add --no-cache \
    ca-certificates \
    tzdata \
    ffmpeg \
    python3 \
    py3-pip \
    make \
    && pip3 install --break-system-packages --no-cache-dir --upgrade yt-dlp \
    && yt-dlp --version \
    && rm -rf /root/.cache /var/cache/apk/*

WORKDIR /app

# Copy artifacts from builder
COPY --from=builder /build/music-bot .
COPY --from=builder /go/bin/goose /usr/local/bin/
COPY --from=builder /build/db/migrations ./db/migrations
COPY Makefile .

# Setup non-root user
RUN addgroup -g 1000 bot \
    && adduser -u 1000 -G bot -h /app -D bot \
    && mkdir -p playlist logs \
    && chown -R bot:bot /app

USER bot
ENV TZ=Asia/Ho_Chi_Minh

ENTRYPOINT ["./music-bot"]