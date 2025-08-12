import os
from dotenv import load_dotenv

load_dotenv()

# Bot configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LAVALINK_HOST = os.getenv("LAVALINK_HOST", "lavalink")
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", 2333))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")

# Bot settings
COMMAND_PREFIX = "!"
DEFAULT_VOICE_CHANNEL_ID = None  # Set this to your voice channel ID
DEFAULT_TEXT_CHANNEL_ID = None   # Set this to your text channel ID

# Playlist settings
DEFAULT_PLAYLIST_URL = ""  # Set your default YouTube playlist URL here
AUTO_RECONNECT = True
VOLUME_DEFAULT = 100