#!/usr/bin/env python3
"""
Simple test script for the LoFi Music Bot
"""

import asyncio
from lofi_bot.config import config
from lofi_bot.bot import LoFiBot
from lofi_bot.logger import logger


async def test_bot():
    """Test bot functionality"""
    print("🧪 Testing LoFi Music Bot...")

    # Test configuration
    print(f"✅ Bot Token: {'Set' if config.BOT_TOKEN else 'Missing'}")
    print(f"✅ Command Prefix: {config.COMMAND_PREFIX}")
    print(f"✅ Music Folder: {config.MUSIC_FOLDER}")

    # Test bot creation
    try:
        bot = LoFiBot()
        print(f"✅ Bot created successfully")
        print(f"✅ Commands registered: {len(bot.commands)}")

        # List commands
        for cmd in bot.commands:
            print(f"   - {config.COMMAND_PREFIX}{cmd.name}: {cmd.help}")

        print("\n🚀 Bot is ready to start!")
        print(f"📋 Use these commands in Discord:")
        print(f"   - {config.COMMAND_PREFIX}help - Show all commands")
        print(f"   - {config.COMMAND_PREFIX}playlists - List playlists")
        print(f"   - {config.COMMAND_PREFIX}use main_playlist - Select playlist")
        print(f"   - {config.COMMAND_PREFIX}play - Play music")

    except Exception as e:
        print(f"❌ Bot creation failed: {e}")
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(test_bot())
    if success:
        print("\n✅ All tests passed! Run 'python main.py' to start the bot.")
    else:
        print("\n❌ Tests failed. Please check the configuration.")
