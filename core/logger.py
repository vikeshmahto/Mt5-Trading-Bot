"""
core/logger.py
──────────────
Structured, colored logging for the entire system.

Usage:
    from core.logger import get_logger
    log = get_logger(__name__)
    log.info("Signal generated", extra={"symbol": "XAUUSD"})
"""

from __future__ import annotations

import io
import logging
import sys
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

# colorlog is in requirements.txt — graceful fallback if not yet installed
try:
    import colorlog
    _HAS_COLOR = True
except ImportError:
    _HAS_COLOR = False


_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
)
_COLOR_FORMAT = (
    "%(log_color)s%(asctime)s | %(levelname)-8s%(reset)s | "
    "%(name)-30s | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_COLOR_MAP = {
    "DEBUG":    "cyan",
    "INFO":     "green",
    "WARNING":  "yellow",
    "ERROR":    "red",
    "CRITICAL": "bold_red",
}

_root_configured = False


def _configure_root(level: str = "INFO", log_file: Optional[str] = None) -> None:
    global _root_configured
    if _root_configured:
        return
    _root_configured = True

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Force UTF-8 on Windows (avoids cp1252 UnicodeEncodeError with emoji/arrows)
    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    handler = logging.StreamHandler(utf8_stdout)
    handler.setLevel(logging.DEBUG)

    if _HAS_COLOR:
        formatter = colorlog.ColoredFormatter(
            _COLOR_FORMAT,
            datefmt=_DATE_FORMAT,
            log_colors=_COLOR_MAP,
        )
    else:
        formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    handler.setFormatter(formatter)
    root.addHandler(handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            str(log_path),
            maxBytes=10 * 1024 * 1024, # 10 MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        file_formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
        file_handler.setFormatter(file_formatter)
        root.addHandler(file_handler)


def get_logger(name: Optional[str] = None, level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """
    Return a named logger.  Configures the root logger on first call.

    Args:
        name:  Typically __name__ of the calling module.
        level: Minimum log level string (INFO, DEBUG, WARNING, …).
        log_file: Optional path to a file where logs should be rotated and saved.
    """
    _configure_root(level, log_file)
    logger = logging.getLogger(name or "mt5-system")
    return logger
