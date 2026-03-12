"""Shared logging configuration for swarm services and CLIs."""

from __future__ import annotations

import logging
import os


def configure_logging(level: str | None = None) -> None:
    """Configure process-wide logging once, or update the root level."""
    log_level = (level or os.getenv("SWARM_LOG_LEVEL", "INFO")).upper()
    root_logger = logging.getLogger()

    if root_logger.handlers:
        root_logger.setLevel(log_level)
        return

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
