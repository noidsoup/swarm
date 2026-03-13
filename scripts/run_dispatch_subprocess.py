#!/usr/bin/env python3
"""Run a single dispatch in isolation (subprocess) to avoid inherited stdout/stderr issues.

Used when the cursor worker runs as a daemon child on Windows - the flow runs in a fresh
process with stdout/stderr=DEVNULL, avoiding "I/O operation on closed file" from CrewAI/Rich.

Usage: python scripts/run_dispatch_subprocess.py <payload.json> <result.json>
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Redirect stdout/stderr to devnull before any swarm/CrewAI imports. The daemon child
# on Windows has inherited handles that can raise "I/O operation on closed file" when
# CrewAI/Rich write to them. Replacing them here avoids that entirely.
_devnull = open(os.devnull, "w", encoding="utf-8")
sys.stdout = _devnull
sys.stderr = _devnull

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(1)
    payload_path = Path(sys.argv[1])
    result_path = Path(sys.argv[2])
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    # Ensure skip_llm from payload is honored even if env wasn't propagated through daemon spawn
    if payload.get("skip_llm"):
        os.environ["SWARM_SMOKE_SKIP_LLM"] = "1"
    try:
        from swarm.config import cfg
        from swarm.dispatch import Dispatcher

        result = Dispatcher(cfg).dispatch(
            plan=str(payload.get("plan", "")),
            feature_name=str(payload.get("feature_name", "")),
            builder_type=str(payload.get("builder_type", "")),
            repo_path=str(payload.get("repo_path", "")),
            repo_url=str(payload.get("repo_url", "")),
            execution_mode="local",
            skip_llm=bool(payload.get("skip_llm", False)),
        )
    except Exception as exc:
        import traceback

        result = {
            "status": "error",
            "error": str(exc),
            "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            "build_summary": "",
            "review_feedback": "",
            "quality_report": "",
            "polish_report": "",
        }
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
