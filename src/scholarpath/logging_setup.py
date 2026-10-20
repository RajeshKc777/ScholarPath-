"""Logging setup: console + rotating file, no sensitive payloads.

Log records include event names and identifiers, never message bodies,
documents, or credentials.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "scholarpath"
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"


def log_dir() -> Path:
    from scholarpath.config import app_data_dir

    return app_data_dir() / "logs"


def setup_logging(level: str = "INFO", directory: Path | None = None) -> Path:
    """Configure the ``scholarpath`` logger. Returns the log file path."""
    target_dir = directory or log_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / "scholarpath.log"

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    rotating = RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    rotating.setFormatter(formatter)
    logger.addHandler(rotating)

    return log_file
