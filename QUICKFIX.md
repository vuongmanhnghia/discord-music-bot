# 🚨 Quick Fix: Voice Connection Error

## Problem

```
websocket: close 4016: Unknown encryption mode
```

## Root Cause

**Missing `libsodium`** - required library for Discord voice encryption.

## ✅ Quick Solution (NixOS)

```bash
# Option 1: Use nix-shell (recommended)
cd /home/nagih/Workspaces/noob/bot/discord-music-bot
nix-shell
go run cmd/bot/main.go

# Option 2: One-line fix
nix-shell -p libsodium opus --run "go run cmd/bot/main.go"
```

## ✅ Permanent Fix

Add to your NixOS configuration:

```nix
environment.systemPackages = with pkgs; [
  libsodium
  opus
  # ... other packages
];
```

Then: `sudo nixos-rebuild switch`

## Verify Fix

```bash
pkg-config --exists libsodium && echo "✅ Ready!" || echo "❌ Still missing"
```

## What's Fixed

-   ✅ Infinite retry loop (stops when connection fails)
-   ✅ Voice connection timeout (10s max wait)
-   ✅ Better error messages
-   ⏳ Voice encryption (needs libsodium)

## Current Build

-   Bot: **Working** ✅
-   Commands: **Working** ✅
-   YouTube extraction: **Working** ✅
-   Processing: **Working** ✅
-   Voice playback: **Needs libsodium** ⏳

Run `nix-shell` then test!
