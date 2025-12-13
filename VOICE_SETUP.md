# Voice Setup Guide

## Issue: "Unknown encryption mode" Error

This error occurs when Discord voice encryption libraries are missing.

## Required Dependencies

### 1. libsodium (Required for voice encryption)

```bash
# NixOS
nix-shell -p libsodium

# Or add to your system packages
# configuration.nix:
# environment.systemPackages = with pkgs; [ libsodium opus ffmpeg yt-dlp ];

# Ubuntu/Debian
sudo apt-get install libsodium-dev

# macOS
brew install libsodium

# Arch Linux
sudo pacman -S libsodium
```

### 2. Opus (For audio encoding)

```bash
# NixOS
nix-shell -p opus

# Ubuntu/Debian
sudo apt-get install libopus-dev

# macOS
brew install opus

# Arch Linux
sudo pacman -S opus
```

### 3. FFmpeg (Already installed)

```bash
# Verify
ffmpeg -version
```

## Rebuild After Installing

After installing libsodium and opus:

```bash
# Clean and rebuild
go clean -cache
go build -o bin/bot ./cmd/bot/

# Run bot
./bin/bot
```

## Verify Installation

```bash
# Check if libraries are found
pkg-config --exists libsodium && echo "✅ libsodium OK" || echo "❌ libsodium missing"
pkg-config --exists opus && echo "✅ opus OK" || echo "❌ opus missing"
which ffmpeg && echo "✅ ffmpeg OK" || echo "❌ ffmpeg missing"
which yt-dlp && echo "✅ yt-dlp OK" || echo "❌ yt-dlp missing"
```

## Alternative: Use DCA without Opus

If opus causes issues, you can use pure DCA encoding (already working in the bot).

## Current Status

-   ✅ FFmpeg: Installed
-   ✅ yt-dlp: Installed
-   ✅ Go dependencies: Installed
-   ❌ libsodium: **MISSING** (causes encryption error)
-   ❌ opus: Missing (optional but recommended)

## Quick Fix for NixOS

```bash
# Enter shell with all dependencies
nix-shell -p libsodium opus ffmpeg yt-dlp go

# Then run bot
cd /home/nagih/Workspaces/noob/bot/discord-music-bot
go run cmd/bot/main.go
```

Or create `shell.nix`:

```nix
{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    go
    libsodium
    opus
    ffmpeg
    yt-dlp
  ];
}
```

Then: `nix-shell` and `go run cmd/bot/main.go`
