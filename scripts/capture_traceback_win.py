#!/usr/bin/env python3
"""Run a single dispatch on Windows and capture traceback to a file. Used for debugging."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Simulate daemon child: redirect stdout/stderr to a log file (same as cursor worker)
OUTPUT = ROOT / ".swarm" / "traceback_debug.txt"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
log_file = open(OUTPUT, "w", encoding="utf-8")
sys.stdout = log_file
sys.stderr = log_file

try:
    from swarm.config import cfg
    from swarm.dispatch import Dispatcher

    dispatcher = Dispatcher(cfg)
    repo = Path.home() / "repos" / "swarm"
    result = dispatcher.dispatch(
        plan="Add one line to README",
        feature_name="Traceback capture test",
        builder_type="",
        repo_path=str(repo),
        execution_mode="local",
    )
    print("SUCCESS:", result.get("status"))
except Exception:
    traceback.print_exc(file=sys.stderr)
    sys.stderr.flush()
    sys.exit(1)
finally:
    log_file.close()
