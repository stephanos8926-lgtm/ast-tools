"""Structured logging with rotation."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ast_tools.config.loader import get_config_dir


def setup_logging(level: str = "INFO", log_dir: Path | None = None) -> None:
    """Configure ast-tools logging with rotating file handler.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
        log_dir: Custom log directory. Defaults to config_dir/logs.
    """
    if log_dir is None:
        log_dir = get_config_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("ast_tools")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers on repeated calls
    if not root.handlers:
        # Rotating file handler: 100MB per file, keep 5
        fh = RotatingFileHandler(
            log_dir / "ast-tools.log",
            maxBytes=104857600,
            backupCount=5,
        )
        fh.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root.addHandler(fh)

        # Stderr handler for CLI
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        root.addHandler(sh)


def get_logger(name: str) -> logging.Logger:
    """Get a namespaced logger under ast_tools.*."""
    return logging.getLogger(f"ast_tools.{name}")
