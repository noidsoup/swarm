#!/usr/bin/env python3
"""Run a swarm task via Cursor Agent CLI (uses Cursor subscription, no API key).

Invokes `agent -p --force --workspace <repo_path> "<prompt>"` so Cursor's built-in
AI does the work. Requires Cursor CLI installed and `agent login` completed.

Usage: python scripts/run_cursor_agent.py <payload.json> <result.json>

Env: SWARM_USE_CURSOR_AGENT=1 to enable this path (worker checks this).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _find_agent_cli() -> list[str]:
    """Find the Cursor agent CLI. Returns [executable, ...] for subprocess."""
    for name in ("agent", "cursor"):
        path = shutil.which(name)
        if path:
            return [path, "agent"] if name == "cursor" else [path]
    return ["agent"]  # assume in PATH


def _build_prompt(payload: dict, task_file: Path, outbox_path: Path) -> str:
    """Short prompt that references the task file (avoids Windows cmd length limits)."""
    task_id = str(payload.get("task_id", ""))
    return (
        f"Read the swarm task from {task_file}. Implement it in this workspace. "
        f"When done, write a JSON file to {outbox_path} with: status (complete or error), "
        f"build_summary (what you did, under 2000 chars), task_id={task_id}, "
        "completed_at (ISO timestamp), execution_mode=cursor. If error, include an 'error' field."
    )


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(1)
    payload_path = Path(sys.argv[1])
    result_path = Path(sys.argv[2])
    payload = json.loads(payload_path.read_text(encoding="utf-8"))

    task_id = str(payload.get("task_id", "unknown"))
    repo_path = str(payload.get("repo_path", "")).strip() or str(ROOT)
    outbox_path = Path.home() / ".swarm" / "outbox" / f"{task_id}.json"

    # Write task to a file so the agent can read it (avoids Windows cmd length limits)
    task_dir = ROOT / ".swarm" / "worker"
    task_dir.mkdir(parents=True, exist_ok=True)
    task_file = task_dir / f"task-{task_id}.json"
    task_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    try:
        prompt = _build_prompt(payload, task_file, outbox_path)
        agent_argv = _find_agent_cli()

        # agent -p --force --workspace <dir> "prompt"
        # --trust: trust workspace without prompting (headless)
        cmd = agent_argv + ["-p", "--force", "--trust", "--workspace", repo_path, prompt]

        proc = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=int(os.getenv("WINDOWS_CURSOR_TASK_TIMEOUT", "3600")),
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""

        # Check if agent wrote the outbox file
        outbox_file = Path.home() / ".swarm" / "outbox" / f"{task_id}.json"
        if outbox_file.exists():
            result = json.loads(outbox_file.read_text(encoding="utf-8"))
            result.setdefault("execution_mode", "cursor")
        else:
            # Agent didn't write outbox; build result from exit code and output
            build_summary = (stdout + "\n" + stderr).strip()[:2000] if (stdout or stderr) else ""
            result = {
                "status": "complete" if proc.returncode == 0 else "error",
                "task_id": task_id,
                "build_summary": build_summary or ("Completed" if proc.returncode == 0 else "Agent exited with error"),
                "review_feedback": "",
                "quality_report": "",
                "polish_report": "",
                "error": "" if proc.returncode == 0 else f"Agent exited with code {proc.returncode}",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "execution_mode": "cursor",
            }

    except subprocess.TimeoutExpired:
        result = {
            "status": "error",
            "task_id": task_id,
            "error": "Cursor agent timed out",
            "build_summary": "",
            "review_feedback": "",
            "quality_report": "",
            "polish_report": "",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "execution_mode": "cursor",
        }
    except FileNotFoundError:
        result = {
            "status": "error",
            "task_id": task_id,
            "error": "Cursor agent CLI not found. Install with: irm 'https://cursor.com/install?win32=true' | iex ; agent login",
            "build_summary": "",
            "review_feedback": "",
            "quality_report": "",
            "polish_report": "",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "execution_mode": "cursor",
        }
    except Exception as exc:
        result = {
            "status": "error",
            "task_id": task_id,
            "error": str(exc),
            "build_summary": "",
            "review_feedback": "",
            "quality_report": "",
            "polish_report": "",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "execution_mode": "cursor",
        }
    finally:
        try:
            task_file.unlink(missing_ok=True)
        except OSError:
            pass

    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
