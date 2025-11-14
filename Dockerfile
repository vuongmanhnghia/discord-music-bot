# Stage 1: Builder
FROM python:3.12-slim AS builder

ARG TARGETPLATFORM
ARG BUILDPLATFORM
ARG TARGETARCH

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make pkg-config \
    libopus-dev libsodium-dev libffi-dev \
    $(if [ "$TARGETARCH" = "arm64" ]; then echo "libc6-dev-arm64-cross"; fi) \
    curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .

RUN mkdir -p /build/wheels && \
    pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip wheel --no-cache-dir --wheel-dir=/build/wheels -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

ARG TARGETPLATFORM
ARG BUILDPLATFORM
ARG TARGETARCH

RUN apt-get update && apt-get install -y --no-install-recommends \
    libopus0 libsodium23 libffi8 ffmpeg ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /build/wheels /tmp/wheels
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --find-links=/tmp/wheels --no-index -r requirements.txt && \
    rm -rf /tmp/wheels /root/.cache

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONOPTIMIZE=1

RUN mkdir -p playlist logs

COPY . .

HEALTHCHECK --interval=60s --timeout=15s --start-period=45s --retries=3 \
    CMD python -c "import discord" || exit 1

CMD ["python", "-u", "run_bot.py"]
