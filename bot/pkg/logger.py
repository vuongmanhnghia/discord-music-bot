"""Centralized logging setup with structured logging support"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from ..config.config import config


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


def setup_logger(name: str = config.BOT_NAME, structured: bool = False) -> logging.Logger:
    """
    Setup logger with config-based settings
    
    Args:
        name: Logger name
        structured: Enable JSON structured logging (useful for production)
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
        
        # Always use structured format for file logs in production
        if use_structured:
            file_handler.setFormatter(StructuredFormatter())
        else:
            file_handler.setFormatter(formatter)
            
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

