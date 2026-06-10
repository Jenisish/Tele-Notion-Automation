"""Structured logging with rotation."""
import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.config import LOG_DIR, LOG_MAX_BYTES, LOG_BACKUP_COUNT


class StructuredFormatter(logging.Formatter):
    """JSON log lines for machine parsing."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = self.formatException(record.exc_info)
        # Extra fields
        for key in ("channel", "message_id", "action", "status"):
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        return json.dumps(entry, ensure_ascii=False)


def get_logger(name: str = "sync") -> logging.Logger:
    """Return a configured logger with rotation."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)

    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

    # Rotating file handler
    fh = RotatingFileHandler(
        os.path.join(LOG_DIR, "sync.log"),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(StructuredFormatter())

    # Console handler (human-readable)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    )

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger
