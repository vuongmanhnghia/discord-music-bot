"""Configuration management with validation"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Centralized configuration with validation"""

    # Required environment variables
    BOT_TOKEN: str = os.getenv("BOT_TOKEN") or ""

    # Optional with defaults
    BOT_NAME: str = os.getenv("BOT_NAME", "Discord Music Bot")
    COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "!")
    PLAYLIST_DIR: str = os.getenv("PLAYLIST_DIR", "./playlist")
    STAY_CONNECTED_24_7: bool = os.getenv("STAY_CONNECTED_24_7", "true").lower() in [
        "true",
        "1",
        "yes",
    ]
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "")

    def __post_init__(self):
        """Validate required configuration"""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN or BOT_TOKEN environment variable is required")

        # Ensure directories exist
        Path(self.PLAYLIST_DIR).mkdir(parents=True, exist_ok=True)

    @property
    def playlist_path(self) -> Path:
        return Path(self.PLAYLIST_DIR)


# Global config instance
config = Config()
config.__post_init__()
