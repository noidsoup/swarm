#!/usr/bin/env python3
"""Run a single dispatch on Windows and capture traceback to a file. Used for debugging."""

from __future__ import annotations

import os
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
    # Use first task in inbox
    inbox = Path.home() / ".swarm" / "inbox"
    tasks = sorted(inbox.glob("*.json")) if inbox.exists() else []
    if not tasks:
        print("No task in inbox")
        sys.exit(1)
    import json

    payload = json.loads(tasks[0].read_text(encoding="utf-8"))
    result = dispatcher.dispatch(
        plan=str(payload.get("plan", payload.get("feature_name", ""))),
        feature_name=str(payload.get("feature_name", "")),
        builder_type=str(payload.get("builder_type", "")),
        repo_path=str(payload.get("repo_path", "")),
        execution_mode="local",
    )
    print("SUCCESS:", result.get("status"))
except Exception as exc:
    traceback.print_exc(file=sys.stderr)
    sys.stderr.flush()
    sys.exit(1)
finally:
    log_file.close()
