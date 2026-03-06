"""CLI entry point for swarm-run command."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    """CLI entry point: swarm-run [options] "feature description"."""
    # Add swarm root to path so imports work
    swarm_root = Path(__file__).parent
    if str(swarm_root) not in sys.path:
        sys.path.insert(0, str(swarm_root))

    from run import main as run_main

    run_main()


if __name__ == "__main__":
    main()
