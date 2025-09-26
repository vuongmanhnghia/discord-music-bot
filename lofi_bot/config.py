"""Configuration management with validation"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Centralized configuration with validation"""

    # Required environment variables
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    MUSIC_FOLDER: str = os.getenv("MUSIC_FOLDER")

    # Optional with defaults
    BOT_NAME: str = os.getenv("BOT_NAME", "LoFi Bot")
    COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "!")
    SPOTDL_DIR: str = os.getenv("SPOTDL_DIR", ".")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "")

    def __post_init__(self):
        """Validate required configuration"""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is required")
        if not self.MUSIC_FOLDER:
            raise ValueError("MUSIC_FOLDER environment variable is required")

        # Ensure directories exist
        Path(self.MUSIC_FOLDER).mkdir(parents=True, exist_ok=True)
        Path(self.SPOTDL_DIR).mkdir(parents=True, exist_ok=True)

    @property
    def music_path(self) -> Path:
        return Path(self.MUSIC_FOLDER)

    @property
    def spotdl_path(self) -> Path:
        return Path(self.SPOTDL_DIR)


# Global config instance
config = Config()
config.__post_init__()
