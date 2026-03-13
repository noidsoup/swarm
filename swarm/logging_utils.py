"""Shared logging configuration for swarm services and CLIs."""

from __future__ import annotations

import json
import logging
import os
import sys


class StructuredFormatter(logging.Formatter):
    """JSON formatter for production; human-readable for dev."""

    def __init__(self, json_mode: bool = False):
        super().__init__()
        self._json_mode = json_mode

    def format(self, record: logging.LogRecord) -> str:
        if self._json_mode:
            payload = {
                "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
            }
            extra = getattr(record, "structured_extra", None)
            if extra and isinstance(extra, dict):
                payload.update(extra)
            return json.dumps(payload, default=str)

        base = f"{self.formatTime(record, '%Y-%m-%dT%H:%M:%S')} {record.levelname} {record.name} {record.getMessage()}"
        extra = getattr(record, "structured_extra", None)
        if extra and isinstance(extra, dict):
            kv = " ".join(f"{k}={v}" for k, v in extra.items())
            base = f"{base} {kv}"
        return base


def configure_logging(level: str | None = None) -> None:
    """Configure process-wide logging once, or update the root level."""
    log_level = (level or os.getenv("SWARM_LOG_LEVEL", "INFO")).upper()
    json_mode = os.getenv("SWARM_LOG_FORMAT", "text").lower() == "json"
    root_logger = logging.getLogger()

    if root_logger.handlers:
        root_logger.setLevel(log_level)
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(StructuredFormatter(json_mode=json_mode))
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
