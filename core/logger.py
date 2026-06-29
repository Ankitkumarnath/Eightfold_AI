import logging
import sys
from logging.handlers import RotatingFileHandler
from core.config import settings

def setup_logger(name: str = "resolution_engine") -> logging.Logger:
    """
    Configure and return a structured logger with both console and file handlers.
    """
    logger = logging.getLogger(name)
    
    # Prevent adding handlers multiple times if instantiated multiple times
    if logger.hasHandlers():
        return logger

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    # Professional formatter
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler (Rotating)
    file_handler = RotatingFileHandler(
        settings.LOG_FILE, maxBytes=5*1024*1024, backupCount=2
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

logger = setup_logger()
