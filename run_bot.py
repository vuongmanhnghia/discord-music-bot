#!/usr/bin/env python3
import os
import discord
import glob
from bot.music_bot import MusicBot
from bot.logger import setup_logger

logger = setup_logger(__name__)


def setup_opus():
    """Setup Opus library with automatic platform detection and optimization"""
    import platform
    
    arch = platform.machine()
    logger.info(f"🔍 Detected architecture: {arch}")
    
    # Universal paths that work on most systems
    opus_paths = [
        "libopus.so.0",
        "libopus.so",
        "/usr/lib/libopus.so.0",
        "/usr/lib/libopus.so",
    ]
    
    # Add platform-specific paths
    if arch in ['aarch64', 'arm64']:
        logger.info("🍓 Optimizing for ARM64/Raspberry Pi")
        opus_paths.extend([
            "/usr/lib/aarch64-linux-gnu/libopus.so.0",
            "/lib/aarch64-linux-gnu/libopus.so.0",
        ])
    elif arch in ['x86_64', 'amd64']:
        logger.info("💻 Optimizing for x86_64")
        opus_paths.extend([
            "/usr/lib/x86_64-linux-gnu/libopus.so.0",
        ])
    elif arch.startswith('arm'):
        logger.info("🔧 Optimizing for ARM32")
        opus_paths.extend([
            "/usr/lib/arm-linux-gnueabihf/libopus.so.0",
        ])
    
    # Environment override
    if "OPUS_PATH" in os.environ:
        opus_paths.insert(0, os.environ["OPUS_PATH"])
        logger.info(f"🎯 Using OPUS_PATH override: {os.environ['OPUS_PATH']}")
    
    # Nix support
    if "NIX_STORE" in os.environ:
        try:
            nix_opus = glob.glob("/nix/store/*/lib/libopus.so*")
            if nix_opus:
                opus_paths.extend(nix_opus)
                logger.info(f"📦 Added {len(nix_opus)} Nix Opus paths")
        except Exception as e:
            logger.debug(f"Nix path detection failed: {e}")

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
        logger.error("❌ Could not load Opus library from any path!")
        logger.info(f"🔍 Architecture: {arch}")
        logger.info(f"� Tried paths: {opus_paths}")
        logger.info("💡 Install libopus0: apt-get install libopus0")
        return False
    
    logger.info("🎵 Opus library loaded successfully!")
    return opus_loaded


def main():
    """Run the bot with proper token handling"""
    
    # Check for Discord token
    token = os.getenv('BOT_TOKEN')
    if not token:
        logger.error("❌ BOT_TOKEN environment variable not set!")
        logger.info("💡 Set your token: export BOT_TOKEN='your_bot_token_here'")
        return
    
    logger.info("🎵 Starting Discord Music Bot...")
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
