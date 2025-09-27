# Multi-platform Discord Music Bot - Multi-stage Build
# Optimized for both x86_64 and ARM64 (Raspberry Pi)

# =============================================================================
# Stage 1: Builder - Compile dependencies and build wheels
# =============================================================================
FROM python:3.12-slim AS builder

# Set build arguments for multi-arch support
ARG TARGETPLATFORM
ARG BUILDPLATFORM
ARG TARGETARCH

# Print build information
RUN echo "=== BUILDER STAGE ===" && \
    echo "Building on: $BUILDPLATFORM" && \
    echo "Building for: $TARGETPLATFORM" && \
    echo "Target architecture: $TARGETARCH"

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build tools
    gcc \
    g++ \
    make \
    pkg-config \
    # Development headers for audio libraries
    libopus-dev \
    libsodium-dev \
    libffi-dev \
    # ARM64 specific cross-compilation tools
    $(if [ "$TARGETARCH" = "arm64" ]; then echo "libc6-dev-arm64-cross"; fi) \
    # Utilities
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set up build environment
WORKDIR /build

# Copy requirements for dependency installation
COPY requirements.txt .

# Platform-specific build optimizations
RUN if [ "$TARGETARCH" = "arm64" ]; then \
        echo "Configuring ARM64 build environment..."; \
        export MAKEFLAGS="-j$(nproc)"; \
        export CFLAGS="-O2 -mcpu=native -fPIC"; \
        export CXXFLAGS="-O2 -mcpu=native -fPIC"; \
        export LDFLAGS="-Wl,-O1"; \
    else \
        echo "Configuring x86_64 build environment..."; \
        export MAKEFLAGS="-j$(nproc)"; \
        export CFLAGS="-O2 -fPIC"; \
        export CXXFLAGS="-O2 -fPIC"; \
    fi && \
    # Create wheels directory
    mkdir -p /build/wheels && \
    # Upgrade pip and build tools
    pip install --no-cache-dir --upgrade pip setuptools wheel && \
    # Build wheels for all dependencies
    pip wheel --no-cache-dir --wheel-dir=/build/wheels -r requirements.txt

# =============================================================================
# Stage 2: Runtime - Minimal production image
# =============================================================================
FROM python:3.12-slim AS runtime

# Set build arguments for multi-arch support
ARG TARGETPLATFORM
ARG BUILDPLATFORM
ARG TARGETARCH

# Print runtime information
RUN echo "=== RUNTIME STAGE ===" && \
    echo "Building on: $BUILDPLATFORM" && \
    echo "Building for: $TARGETPLATFORM" && \
    echo "Target architecture: $TARGETARCH"

# Install only runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Runtime audio libraries (no -dev packages)
    libopus0 \
    libsodium23 \
    libffi8 \
    # Media processing
    ffmpeg \
    # Minimal utilities
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y \
    && apt-get clean

# Create non-root user
RUN groupadd -r -g 1000 bot && \
    useradd -r -u 1000 -g bot -d /home/bot -s /bin/bash -c "Discord Bot" bot && \
    mkdir -p /home/bot && \
    chown -R bot:bot /home/bot

# Set working directory
WORKDIR /home/bot

# Copy pre-built wheels from builder stage
COPY --from=builder /build/wheels /tmp/wheels

# Copy requirements file to install from wheels
COPY requirements.txt .

# Install Python dependencies from pre-built wheels (much faster!)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --find-links=/tmp/wheels --no-index -r requirements.txt && \
    # Clean up wheels and cache to reduce image size
    rm -rf /tmp/wheels /root/.cache /home/bot/.cache

# Set environment variables for optimization
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1

# Platform-specific runtime optimizations
ENV PYTHONOPTIMIZE=1
RUN if [ "$TARGETARCH" = "arm64" ]; then \
        echo "Applying ARM64 runtime optimizations..."; \
        echo "export PYTHONOPTIMIZE=2" >> /etc/environment; \
        echo "export OMP_NUM_THREADS=4" >> /etc/environment; \
    else \
        echo "Applying x86_64 runtime optimizations..."; \
    fi

# Switch to non-root user
USER bot

# Copy application code (use .dockerignore to exclude build artifacts)
COPY --chown=bot:bot . .

# Create necessary directories with proper ownership
RUN mkdir -p playlist logs && \
    # Platform-specific user environment setup
    if [ "$TARGETARCH" = "arm64" ]; then \
        echo "export PYTHONOPTIMIZE=2" >> ~/.bashrc; \
        echo "export OMP_NUM_THREADS=4" >> ~/.bashrc; \
        echo "ARM64 user optimizations applied"; \
    else \
        echo "export PYTHONOPTIMIZE=1" >> ~/.bashrc; \
        echo "x86_64 user optimizations applied"; \
    fi && \
    echo "Runtime setup complete for $TARGETPLATFORM"

# Health check with platform awareness and dependency verification
HEALTHCHECK --interval=60s --timeout=15s --start-period=45s --retries=3 \
    CMD python -c "import discord, platform, sys; print(f'Bot OK on {platform.machine()}, Python {sys.version_info.major}.{sys.version_info.minor}')" || exit 1

# Expose port for potential web interface (optional)
EXPOSE 8080

# Use exec form for better signal handling
CMD ["python", "-u", "run_bot.py"]