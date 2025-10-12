#!/usr/bin/env python3
"""Main entry point for Discord Music Bot"""

import os
import sys
import discord
import glob
import platform
from bot.music_bot import MusicBot
from bot.pkg.logger import setup_logger

logger = setup_logger(__name__)


class OpusLoader:
    """Handles Opus library loading with platform detection"""
    
    @staticmethod
    def get_opus_paths(arch: str) -> list[str]:
        """Get Opus paths based on architecture"""
        # Universal paths
        paths = [
            "libopus.so.0",
            "libopus.so",
            "/usr/lib/libopus.so.0",
            "/usr/lib/libopus.so",
        ]
        
        # Platform-specific paths
        platform_paths = {
            'aarch64': ["/usr/lib/aarch64-linux-gnu/libopus.so.0", "/lib/aarch64-linux-gnu/libopus.so.0"],
            'arm64': ["/usr/lib/aarch64-linux-gnu/libopus.so.0", "/lib/aarch64-linux-gnu/libopus.so.0"],
            'x86_64': ["/usr/lib/x86_64-linux-gnu/libopus.so.0"],
            'amd64': ["/usr/lib/x86_64-linux-gnu/libopus.so.0"],
        }
        
        if arch in platform_paths:
            paths.extend(platform_paths[arch])
        elif arch.startswith('arm'):
            paths.extend(["/usr/lib/arm-linux-gnueabihf/libopus.so.0"])
        
        # Environment override
        if "OPUS_PATH" in os.environ:
            paths.insert(0, os.environ["OPUS_PATH"])
        
        # Nix support
        if "NIX_STORE" in os.environ:
            try:
                nix_paths = glob.glob("/nix/store/*/lib/libopus.so*")
                if nix_paths:
                    paths.extend(nix_paths)
            except Exception:
                pass
        
        return paths
    
    @staticmethod
    def load() -> bool:
        """Load Opus library with automatic platform detection"""
        arch = platform.machine()
        logger.info(f"🔍 Detected architecture: {arch}")
        
        opus_paths = OpusLoader.get_opus_paths(arch)
        
        for path in opus_paths:
            try:
                discord.opus.load_opus(path)
                logger.info(f"✅ Loaded Opus from: {path}")
                logger.info("🎵 Opus library loaded successfully!")
                return True
            except (discord.opus.OpusNotLoaded, OSError):
                continue
        
        logger.error("❌ Could not load Opus library from any path!")
        logger.info(f"🔍 Architecture: {arch}")
        logger.info(f"📁 Tried paths: {opus_paths}")
        logger.info("💡 Install libopus0: apt-get install libopus0")
        return False


def validate_token(token: str) -> bool:
    """Validate Discord bot token"""
    if not token:
        logger.error("❌ BOT_TOKEN environment variable not set!")
        logger.info("💡 Set your token: export BOT_TOKEN='your_bot_token_here'")
        return False
    
    if len(token) < 50:
        logger.error("❌ Invalid BOT_TOKEN format (too short)")
        return False
    
    return True


def main():
    """Run the bot with proper initialization"""
    logger.info("🎵 Starting Discord Music Bot...")
    logger.info("🏗️  Clean Architecture with yt-dlp")
    logger.info("🔧 Features: YouTube, Spotify metadata, Search, Queue management")
    
    # Validate token
    token = os.getenv('BOT_TOKEN')
    if not validate_token(token):
        sys.exit(1)
    
    # Setup Opus library
    if not OpusLoader.load():
        logger.warning("⚠️ Opus loading failed, audio may not work properly")
    
    # Create and run bot
    bot = MusicBot()
    
    try:
        bot.run(token)
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except discord.LoginFailure:
        logger.error("❌ Invalid bot token! Please check your BOT_TOKEN")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
