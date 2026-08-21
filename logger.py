"""
logger.py - Centralized logging configuration for NeuroShield Eye.

Sets up a rotating file handler + console handler with structured formatting.
All modules obtain their logger via: logging.getLogger("neuroshield.<module>")
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_log_path() -> Path:
    """Return the platform-appropriate log directory, creating it if needed."""
    app_data = os.environ.get("APPDATA", Path.home())
    log_dir = Path(app_data) / "NeuroShieldEye" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "neuroshield.log"


def setup_logging(level: int = logging.DEBUG) -> None:
    """
    Configure the root 'neuroshield' logger with:
    - RotatingFileHandler (5 MB max, 3 backups)
    - StreamHandler for console output
    Should be called once at application startup.
    """
    logger = logging.getLogger("neuroshield")
    logger.setLevel(level)

    if logger.handlers:
        # Prevent duplicate handlers if setup_logging is called more than once
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- Rotating file handler ---
    try:
        file_handler = RotatingFileHandler(
            filename=get_log_path(),
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as e:
        print(f"[NeuroShield] WARNING: Could not create log file: {e}")

    # --- Console handler ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.info("Logging initialized → %s", get_log_path())


def get_logger(name: str) -> logging.Logger:
    """
    Convenience factory. Usage:
        from utils.logger import get_logger
        log = get_logger(__name__)
    """
    return logging.getLogger(f"neuroshield.{name}")
