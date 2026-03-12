#!/usr/bin/env python3
"""Start the background continuous improvement daemon.

This runs in the background and:
- Watches your repo for file changes
- Queues files for improvement
- Runs the swarm on queued files
- Opens PRs for approved changes

Usage:
    python daemon.py /path/to/repo

Or with systemd/supervisor for always-on CI.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

if __name__ == "__main__":
    from swarm.logging_utils import configure_logging

    configure_logging()
    logger = logging.getLogger(__name__)

    repo_path = sys.argv[1] if len(sys.argv) > 1 else "."
    repo_path = str(Path(repo_path).resolve())

    logger.info("Starting background AI CI daemon")
    logger.info("Daemon repo=%s", repo_path)
    logger.info("Press Ctrl+C to stop")

    from swarm.background_loop import start_background_daemon

    try:
        start_background_daemon(repo_path)
    except KeyboardInterrupt:
        logger.info("Daemon stopped")
        sys.exit(0)
