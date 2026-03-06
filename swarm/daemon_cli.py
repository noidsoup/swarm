"""CLI entry point for swarm-daemon command."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    """CLI entry point: swarm-daemon [repo_path]."""
    repo_path = sys.argv[1] if len(sys.argv) > 1 else "."

    # Add swarm root to path
    swarm_root = Path(__file__).parent.parent
    if str(swarm_root) not in sys.path:
        sys.path.insert(0, str(swarm_root))

    from swarm.background_loop import start_background_daemon

    print(f"Starting AI Dev Swarm daemon for {repo_path}")
    print("Press Ctrl+C to stop\n")

    try:
        start_background_daemon(repo_path)
    except KeyboardInterrupt:
        print("\nDaemon stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
