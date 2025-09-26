#!/usr/bin/env python3
"""
LoFi Music Bot - Optimized entry point
"""

import asyncio
import discord
import glob
import os
from lofi_bot.bot import LoFiBot
from lofi_bot.config import config
from lofi_bot.logger import logger


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


async def main():
    """Main entry point"""
    try:
        logger.info(f"🚀 Starting {config.BOT_NAME}...")
        logger.info(f"🔗 Command prefix: {config.COMMAND_PREFIX}...")

        # Setup Opus before starting bot
        setup_opus()

        bot = LoFiBot()
        await bot.start(config.BOT_TOKEN)

    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Bot failed to start: {e}")
        raise
    finally:
        logger.info("Bot shutdown")


if __name__ == "__main__":
    asyncio.run(main())
