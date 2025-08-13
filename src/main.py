import discord
import asyncio
import logging
from discord.ext import commands
import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord-music-bot")

def setup_bot():
    """Initialize and set up the Discord bot"""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True
    
    bot = commands.Bot(command_prefix=config.COMMAND_PREFIX, intents=intents)
    return bot

async def main():
    """Main entry point for the bot"""
    bot = setup_bot()
    
    # Import here to avoid circular imports
    from cogs.music import MusicCog
    
    async with bot:
        await bot.add_cog(MusicCog(bot))
        logger.info("Starting Discord Music Bot...")
        await bot.start(config.DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main()) 