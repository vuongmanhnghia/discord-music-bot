import logging

def setup_logger():
    """Configure and return the logger for the bot"""
    logger = logging.getLogger("discord-music-bot")
    
    if not logger.handlers:
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    return logger

# Export a pre-configured logger instance
logger = setup_logger() 