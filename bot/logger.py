"""Centralized logging setup"""

import logging
from pathlib import Path
from .config import config


def setup_logger(name: str = "discord-music-bot") -> logging.Logger:
    """Setup logger with config-based settings"""
    logger = logging.getLogger(name)

    if logger.handlers:  # Already configured
        return logger

    # Set level
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    # Formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler if configured
    if config.LOG_FILE:
        file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger


# Global logger
logger = setup_logger()
