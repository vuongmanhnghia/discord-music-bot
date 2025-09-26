"""Configuration management with validation"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Centralized configuration with validation"""

    # Required environment variables
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    MUSIC_DIR: str = os.getenv("MUSIC_DIR")

    # Optional with defaults
    BOT_NAME: str = os.getenv("BOT_NAME", "Music Bot")
    COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "!")
    PLAYLIST_DIR: str = os.getenv("PLAYLIST_DIR", ".")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "")

    def __post_init__(self):
        """Validate required configuration"""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is required")
        if not self.MUSIC_DIR:
            raise ValueError("MUSIC_DIR environment variable is required")

        # Ensure directories exist
        Path(self.MUSIC_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.PLAYLIST_DIR).mkdir(parents=True, exist_ok=True)

    @property
    def music_path(self) -> Path:
        return Path(self.MUSIC_DIR)

    @property
    def playlist_path(self) -> Path:
        return Path(self.PLAYLIST_DIR)


# Global config instance
config = Config()
config.__post_init__()
