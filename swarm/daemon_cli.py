"""CLI entry point for swarm-daemon command."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def main() -> None:
    """CLI entry point: swarm-daemon [repo_path]."""
    from swarm.logging_utils import configure_logging

    configure_logging()
    logger = logging.getLogger(__name__)

    repo_path = sys.argv[1] if len(sys.argv) > 1 else "."

    # Add swarm root to path
    swarm_root = Path(__file__).parent.parent
    if str(swarm_root) not in sys.path:
        sys.path.insert(0, str(swarm_root))

    from swarm.background_loop import start_background_daemon

    logger.info("Starting AI Dev Swarm daemon repo=%s", repo_path)
    logger.info("Press Ctrl+C to stop")

    try:
        start_background_daemon(repo_path)
    except KeyboardInterrupt:
        logger.info("Daemon stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
