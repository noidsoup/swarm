#!/usr/bin/env python3
"""Run the local cursor worker inbox/outbox consumer."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swarm.cursor_worker import CursorWorkerService, spawn_cursor_worker_daemon


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run the cursor worker inbox consumer.")
    parser.add_argument("--root", default="", help="Queue root directory (defaults to ~/.swarm)")
    parser.add_argument("--once", action="store_true", help="Process at most one queued task and exit")
    parser.add_argument("--daemon", action="store_true", help="Start the worker in the background and exit")
    parser.add_argument("--daemon-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--task-timeout",
        type=float,
        default=float(os.getenv("WINDOWS_CURSOR_TASK_TIMEOUT", "3600")),
        help="Seconds before an in-flight worker task is marked as timed out",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds to wait between inbox polls in continuous mode",
    )
    parser.add_argument("--log-file", default="", help="Optional log file path for daemon mode")
    parser.add_argument("--pid-file", default="", help="Optional pid file path for daemon mode")
    args = parser.parse_args()

    root = Path(args.root).expanduser() if args.root else None
    if args.daemon:
        pid = spawn_cursor_worker_daemon(
            script_path=Path(__file__),
            root=root,
            poll_interval=args.poll_interval,
            task_timeout_seconds=args.task_timeout,
            log_file=Path(args.log_file).expanduser() if args.log_file else None,
            pid_file=Path(args.pid_file).expanduser() if args.pid_file else None,
        )
        print(pid)
        return

    if args.pid_file:
        pid_path = Path(args.pid_file).expanduser()
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(os.getpid()), encoding="utf-8")

    service = CursorWorkerService(root=root, task_timeout_seconds=args.task_timeout)
    if args.once:
        service.process_once()
        return
    service.run_forever(poll_interval=args.poll_interval)


if __name__ == "__main__":
    main()
