# Multi-platform Discord Music Bot
# Optimized for both x86_64 and ARM64 (Raspberry Pi)
FROM python:3.12-slim

# Set build arguments for multi-arch support
ARG TARGETPLATFORM
ARG BUILDPLATFORM
ARG TARGETARCH

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Audio libraries
    libopus0 \
    libopus-dev \
    libsodium23 \
    libsodium-dev \
    libffi8 \
    libffi-dev \
    # Media processing
    ffmpeg \
    # Build tools (temporary)
    gcc \
    g++ \
    make \
    pkg-config \
    # Utilities
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r -g 1000 bot && \
    useradd -r -u 1000 -g bot -d /home/bot -s /bin/bash -c "Discord Bot" bot && \
    mkdir -p /home/bot && \
    chown -R bot:bot /home/bot

# Set working directory
WORKDIR /home/bot

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    # Clean up build dependencies to reduce image size
    apt-get purge -y gcc g++ make pkg-config && \
    apt-get autoremove -y && \
    apt-get clean

# Switch to non-root user
USER bot

# Copy application code
COPY --chown=bot:bot . .

# Create necessary directories
RUN mkdir -p playlist logs

# Set environment variables for optimization
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1

# Platform-specific optimizations
RUN echo "Building for platform: $TARGETPLATFORM ($TARGETARCH)"

# Health check with platform awareness
HEALTHCHECK --interval=60s --timeout=15s --start-period=30s --retries=3 \
    CMD python -c "import discord, platform; print(f'Bot OK on {platform.machine()}')" || exit 1

# Run the bot
CMD ["python", "run_bot.py"]