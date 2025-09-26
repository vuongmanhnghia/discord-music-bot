#!/usr/bin/env python3
"""
Lofi Music Bot - Production Runne    # Setup Opus library before starting bot
    setup_opus()n Architecture Implementation with yt-dlp
"""

import asyncio
import os
import discord
import glob
from bot.music_bot import MusicBot
from bot.logger import setup_logger

logger = setup_logger(__name__)


def setup_opus():
    """Setup Opus library for voice support"""
    opus_paths = [
        "libopus.so",
        "libopus.so.0",
        "/usr/lib/x86_64-linux-gnu/libopus.so.0",
        "/usr/lib/libopus.so.0",
    ]

    # Add Nix store paths if available
    if "NIX_STORE" in os.environ:
        nix_opus = glob.glob("/nix/store/*/lib/libopus.so*")
        opus_paths.extend(nix_opus)

    opus_loaded = False
    for path in opus_paths:
        try:
            discord.opus.load_opus(path)
            logger.info(f"✅ Loaded Opus from: {path}")
            opus_loaded = True
            break
        except (discord.opus.OpusNotLoaded, OSError):
            continue

    if not opus_loaded:
        logger.warning("⚠️ Could not load Opus library. Voice features may not work.")
    
    return opus_loaded


def main():
    """Run the bot with proper token handling"""
    
    # Check for Discord token
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("❌ DISCORD_TOKEN environment variable not set!")
        logger.info("💡 Set your token: export DISCORD_TOKEN='your_bot_token_here'")
        return
    
    logger.info("🎵 Starting Lofi Music Bot...")
    logger.info("🏗️  Clean Architecture with yt-dlp")
    logger.info("🔧 Features: YouTube, Spotify metadata, Search, Queue management")
    
    # Setup Opus library before starting bot
    setup_opus()
    
    # Create and run bot
    bot = MusicBot()
    
    try:
        bot.run(token)
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Bot crashed: {e}")

if __name__ == "__main__":
    main()
