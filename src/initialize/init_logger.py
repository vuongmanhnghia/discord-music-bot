import logging
import os


def init_logger(name: str = "lofi-music", level: str | int = None) -> logging.Logger:
    """Create and configure a logger.

    - name: logical logger name for hierarchical control
    - level: string (e.g., "INFO") or int from logging module; defaults to LOG_LEVEL env or INFO
    """
    logger = logging.getLogger(name)

    if level is None:
        env_level = os.getenv("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, env_level, logging.INFO)

    # Avoid duplicate handlers when re-entering dev shells / hot reloads
    if logger.handlers:
        logger.setLevel(level)
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    log_file = os.getenv("LOG_FILE")
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Propagation off to avoid duplicate logs if root logger also configured
    logger.propagate = False
    return logger
