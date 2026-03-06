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

import sys
from pathlib import Path

if __name__ == "__main__":
    repo_path = sys.argv[1] if len(sys.argv) > 1 else "."
    repo_path = str(Path(repo_path).resolve())

    print(f"Starting background AI CI daemon...")
    print(f"Repo: {repo_path}")
    print(f"Press Ctrl+C to stop\n")

    from swarm.background_loop import start_background_daemon

    try:
        start_background_daemon(repo_path)
    except KeyboardInterrupt:
        print("\nDaemon stopped.")
        sys.exit(0)
