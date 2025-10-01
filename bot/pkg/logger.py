"""Centralized logging setup with structured logging support"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from ..config.config import config


# ANSI Color codes for terminal output
class LogColors:
    """ANSI escape codes for colored terminal output"""

    RESET = "\033[0m"
    BOLD = "\033[1m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright/Bold colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background colors
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


class ColoredFormatter(logging.Formatter):
    """Formatter with color support for different log levels"""

    # Define colors for each log level
    LEVEL_COLORS = {
        logging.DEBUG: LogColors.BRIGHT_BLACK,  # Gray for debug
        logging.INFO: LogColors.BRIGHT_CYAN,  # Cyan for info
        logging.WARNING: LogColors.BRIGHT_YELLOW,  # Yellow for warning
        logging.ERROR: LogColors.BRIGHT_RED,  # Red for error
        logging.CRITICAL: LogColors.BG_RED
        + LogColors.BRIGHT_WHITE,  # Red background for critical
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors"""
        # Get color for this level
        level_color = self.LEVEL_COLORS.get(record.levelno, LogColors.RESET)

        # Colorize level name
        original_levelname = record.levelname
        record.levelname = f"{level_color}{record.levelname}{LogColors.RESET}"

        # Colorize timestamp
        timestamp_color = LogColors.BRIGHT_BLACK

        # Colorize logger name
        name_color = LogColors.BRIGHT_BLUE

        # Format the message
        formatted = super().format(record)

        # Apply colors to different parts
        formatted = formatted.replace(
            record.asctime, f"{timestamp_color}{record.asctime}{LogColors.RESET}"
        )
        formatted = formatted.replace(
            record.name, f"{name_color}{record.name}{LogColors.RESET}"
        )

        # Restore original levelname for other handlers
        record.levelname = original_levelname

        return formatted


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Add guild_id if present (common in discord bots)
        for attr in ["guild_id", "user_id", "command", "duration"]:
            if hasattr(record, attr):
                log_data[attr] = getattr(record, attr)

        return json.dumps(log_data, ensure_ascii=False)


class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that adds contextual information"""

    def process(self, msg: str, kwargs: dict) -> tuple:
        """Add context to log message"""
        # Extract extra fields
        extra = kwargs.get("extra", {})

        # Merge with adapter context
        if self.extra:
            extra.update(self.extra)

        kwargs["extra"] = extra
        return msg, kwargs


def setup_logger(
    name: str = config.BOT_NAME, structured: bool = False, colored: bool = True
) -> logging.Logger:
    """
    Setup logger with config-based settings

    Args:
        name: Logger name
        structured: Enable JSON structured logging (useful for production)
        colored: Enable colored output for console (default: True)
    """
    logger = logging.getLogger(name)

    if logger.handlers:  # Already configured
        return logger

    # Set level
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    # Choose formatter based on environment
    use_structured = structured or config.LOG_LEVEL.upper() == "PRODUCTION"

    if use_structured:
        formatter = StructuredFormatter()
    else:
        # Human-readable formatter for development
        if colored:
            # Use colored formatter for console
            formatter = ColoredFormatter(
                fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        else:
            # Plain formatter (for file or when colors not supported)
            formatter = logging.Formatter(
                fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

    # Console handler with colors
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler if configured (always without colors)
    if config.LOG_FILE:
        file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
        file_handler.setLevel(level)

        # Always use structured format for file logs in production, or plain format otherwise
        if use_structured:
            file_handler.setFormatter(StructuredFormatter())
        else:
            # Plain formatter for file (no colors in file)
            plain_formatter = logging.Formatter(
                fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(plain_formatter)

        logger.addHandler(file_handler)

    logger.propagate = False
    return logger


def get_context_logger(name: str, **context) -> ContextLogger:
    """
    Get a logger with contextual information

    Example:
        logger = get_context_logger(__name__, guild_id=123, user_id=456)
        logger.info("User action", extra={"command": "play"})
    """
    base_logger = setup_logger(name)
    return ContextLogger(base_logger, context)


# Global logger
logger = setup_logger()
