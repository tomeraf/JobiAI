import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Log file path
LOG_FILE = Path(__file__).parent.parent.parent / "backend.log"

# Log rotation settings
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB per file
BACKUP_COUNT = 3  # Keep 3 backup files (backend.log.1, .2, .3)

# Configure logging with rotating file handler
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        ),
    ],
)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)
