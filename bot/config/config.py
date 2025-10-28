"""Configuration management with validation and singleton pattern"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Centralized configuration with validation using singleton pattern"""

    _instance: Optional["Config"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize configuration only once"""
        if hasattr(self, "_initialized") and self._initialized:
            return

        # Required environment variables
        self.BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is required")

        # Optional with defaults
        self.BOT_NAME: str = os.getenv("BOT_NAME", "Discord Music Bot")
        self.VERSION: str = os.getenv("VERSION", "1.0.0")
        self.COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "!")
        self.PLAYLIST_DIR: str = os.getenv("PLAYLIST_DIR", "./playlist")
        self.STAY_CONNECTED_24_7: bool = os.getenv("STAY_CONNECTED_24_7", "true").lower() in ["true", "1", "yes"]
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FILE: str = os.getenv("LOG_FILE", "")

        # Validate and initialize
        self._validate()
        self._setup_directories()
        self._initialized = True

    def _validate(self):
        """Validate required configuration"""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is required")

        if len(self.BOT_TOKEN) < 50:
            raise ValueError("Invalid BOT_TOKEN format (too short)")

        # Create masked version for safe logging
        self._masked_token = f"{self.BOT_TOKEN[:10]}...{self.BOT_TOKEN[-4:]}"

    def _setup_directories(self):
        """Ensure required directories exist"""
        Path(self.PLAYLIST_DIR).mkdir(parents=True, exist_ok=True)
        Path("./cache/songs").mkdir(parents=True, exist_ok=True)

    def get_safe_token(self) -> str:
        """Return masked token for safe logging"""
        return self._masked_token

    @property
    def playlist_path(self) -> Path:
        """Get playlist directory path"""
        return Path(self.PLAYLIST_DIR)


# Global config instance
config = Config()
