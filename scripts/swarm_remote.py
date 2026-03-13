#!/usr/bin/env python3
"""swarm-remote — Mac-side CLI for submitting tasks to the remote swarm.

Install on Mac:
    pip install httpx rich
    chmod +x scripts/swarm_remote.py
    # or: alias swarm-remote='python3 /path/to/swarm/scripts/swarm_remote.py'

Usage:
    swarm-remote submit "Build a login page with OAuth"
    swarm-remote submit --plan plan.md "Implement the plan"
    swarm-remote dispatch "Feature request" --mode cursor
    swarm-remote run "Feature request" --retry 5
    swarm-remote update-windows [--restart-worker]
    swarm-remote status
    swarm-remote status <task-id>
    swarm-remote logs <task-id>
    swarm-remote cancel <task-id>
    swarm-remote health
    swarm-remote models
    swarm-remote gpu
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import httpx
except ImportError:
    print("Missing dependency: pip install httpx")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from swarm.config import cfg  # noqa: E402
from swarm.cursor_worker import CursorWorkerClient  # noqa: E402
from swarm.dispatch import Dispatcher  # noqa: E402
from swarm.projects import ProjectRegistry, spawn_project_from_template  # noqa: E402

SWARM_URL = os.getenv("SWARM_URL", "http://localhost:9000")
TIMEOUT = 30
PROJECTS = ProjectRegistry()


def _url(path: str) -> str:
    return f"{SWARM_URL.rstrip('/')}{path}"


def _get(path: str):
    resp = httpx.get(_url(path), timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, data: dict):
    resp = httpx.post(_url(path), json=data, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _delete(path: str):
    resp = httpx.delete(_url(path), timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _api_fallback_to_cursor(exc: Exception) -> bool:
    """Return True when cursor outbox fallback should be attempted."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 404
    return isinstance(exc, httpx.HTTPError)


def _cursor_client_or_none() -> CursorWorkerClient | None:
    dispatcher = Dispatcher(cfg)
    if not dispatcher.connection.enabled():
        return None
    return CursorWorkerClient(dispatcher.connection)


def cmd_submit(args):
    plan = ""
    if args.plan:
        with open(args.plan) as f:
            plan = f.read()

    data = {
        "feature": args.feature,
        "plan": plan,
        "builder_type": args.builder or "",
        "repo_url": args.repo or "",
    }
    result = _post("/tasks", data)
    print(f"Task submitted: {result['task_id']}")
    print(f"Status: {result['status']}")
    print("\nTrack it:")
    print(f"  swarm-remote status {result['task_id']}")
    print(f"  swarm-remote logs {result['task_id']}")


def cmd_dispatch(args):
    plan = ""
    if args.plan:
        with open(args.plan, encoding="utf-8") as f:
            plan = f.read()

    mode = (args.mode or cfg.default_execution_mode).strip().lower()
    wait_for_completion = True
    if mode == "cursor":
        # Async-first for cursor mode; use --wait to keep prior blocking behavior.
        wait_for_completion = bool(args.wait)
        if args.async_dispatch:
            print("Note: --async is accepted for compatibility. Cursor dispatch is already async by default.")
    elif args.async_dispatch:
        raise SystemExit("--async is only supported with --mode cursor")

    dispatcher = Dispatcher(cfg)
    result = dispatcher.dispatch(
        plan=plan or args.feature,
        feature_name=args.feature,
        builder_type=args.builder or "",
        repo_path=args.repo_path or "",
        repo_url=args.repo_url or "",
        execution_mode=mode,
        wait_for_completion=wait_for_completion,
    )
    print(json.dumps(result, indent=2))
    if mode == "cursor" and not wait_for_completion:
        task_id = result.get("task_id", "")
        if task_id:
            print("\nTrack it:")
            print(f"  swarm-remote status {task_id}")
            print(f"  swarm-remote logs {task_id}")
            print(f"  swarm-remote cancel {task_id}")


def cmd_status(args):
    if args.task_id:
        try:
            task = _get(f"/tasks/{args.task_id}")
            print(json.dumps(task, indent=2))
            return
        except Exception as exc:
            if not _api_fallback_to_cursor(exc):
                raise
        client = _cursor_client_or_none()
        if client is None:
            raise SystemExit("Task not found via API and cursor host/user are not configured.")
        print(json.dumps(client.get_status(args.task_id), indent=2))
    else:
        tasks = _get("/tasks")
        if not tasks:
            print("No tasks.")
            return
        if HAS_RICH:
            console = Console()
            table = Table(title="Swarm Tasks")
            table.add_column("ID", style="cyan")
            table.add_column("Status", style="bold")
            table.add_column("Feature", max_width=50)
            table.add_column("Created")
            for t in tasks:
                status_style = {
                    "queued": "yellow",
                    "running": "blue",
                    "completed": "green",
                    "failed": "red",
                    "cancelled": "dim",
                }.get(t["status"], "")
                table.add_row(
                    t["task_id"],
                    f"[{status_style}]{t['status']}[/]",
                    t["feature"][:50],
                    t.get("created_at", "")[:19],
                )
            console.print(table)
        else:
            for t in tasks:
                print(f"  {t['task_id']}  {t['status']:12s}  {t['feature'][:60]}")


def cmd_logs(args):
    """Stream logs via SSE."""
    url = _url(f"/tasks/{args.task_id}/log")
    print(f"Streaming logs for {args.task_id}...\n")
    try:
        with httpx.stream("GET", url, timeout=None) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    try:
                        parsed = json.loads(data)
                        if isinstance(parsed, dict) and "status" in parsed:
                            print(f"\n=== Task {parsed['status']} ===")
                            break
                    except json.JSONDecodeError:
                        pass
                    print(data)
    except Exception as exc:
        if not _api_fallback_to_cursor(exc):
            raise
        client = _cursor_client_or_none()
        if client is None:
            raise SystemExit("Task not found via API and cursor host/user are not configured.")
        print("API logs unavailable for this task. Polling cursor worker status/outbox...\n")
        timeout_seconds = int(os.getenv("WINDOWS_CURSOR_TIMEOUT", "7200"))
        deadline = time.time() + timeout_seconds
        last_status = ""
        while time.time() < deadline:
            payload = client.get_status(args.task_id)
            status = str(payload.get("status", "")).lower()
            if status != last_status:
                print(json.dumps(payload, indent=2))
                last_status = status
            if status in {"complete", "completed", "error", "failed", "cancelled", "not_found"}:
                break
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nStopped streaming.")


def _get_task_status(task_id: str) -> dict:
    """Return task payload from API or cursor outbox. Raises on unrecoverable error."""
    try:
        return _get(f"/tasks/{task_id}")
    except Exception as exc:
        if not _api_fallback_to_cursor(exc):
            raise
    client = _cursor_client_or_none()
    if client is None:
        raise SystemExit("Task not found via API and cursor host/user are not configured.")
    return client.get_status(task_id)


def cmd_run(args):
    """Dispatch task, poll until terminal state, retry on failure (cursor mode)."""
    mode = (args.mode or cfg.default_execution_mode).strip().lower()
    if mode != "cursor":
        raise SystemExit("run (poll + retry) is only supported with --mode cursor.")

    plan = ""
    if args.plan:
        with open(args.plan, encoding="utf-8") as f:
            plan = f.read()

    dispatcher = Dispatcher(cfg)
    poll_interval = getattr(args, "poll_interval", 5)
    max_attempts = 1 + getattr(args, "retry", 0)
    terminal_ok = {"completed", "complete"}
    terminal_fail = {"failed", "error", "cancelled", "not_found"}

    for attempt in range(1, max_attempts + 1):
        result = dispatcher.dispatch(
            plan=plan or args.feature,
            feature_name=args.feature,
            builder_type=args.builder or "",
            repo_path=args.repo_path or "",
            repo_url=args.repo_url or "",
            execution_mode=mode,
            wait_for_completion=False,
        )
        task_id = result.get("task_id", "")
        if not task_id:
            print("Dispatch did not return task_id.", file=sys.stderr)
            sys.exit(1)
        print(f"Attempt {attempt}/{max_attempts}  task_id={task_id}  (poll every {poll_interval}s)")

        while True:
            time.sleep(poll_interval)
            payload = _get_task_status(task_id)
            status = (payload.get("status") or "").lower()
            if status in terminal_ok:
                print(f"Completed: {task_id}")
                return
            if status in terminal_fail:
                print(f"Terminal state: {status}  task_id={task_id}")
                break

        if attempt < max_attempts:
            print("Retrying...")

    print("All attempts failed.", file=sys.stderr)
    sys.exit(1)


def cmd_cancel(args):
    try:
        result = _delete(f"/tasks/{args.task_id}")
        print(result.get("message", result))
        return
    except Exception as exc:
        if not _api_fallback_to_cursor(exc):
            raise
    client = _cursor_client_or_none()
    if client is None:
        raise SystemExit("Task not found via API and cursor host/user are not configured.")
    result = client.cancel(args.task_id)
    print(json.dumps(result, indent=2))


def cmd_health(_args):
    health = _get("/health")
    print(json.dumps(health, indent=2))


def cmd_models(_args):
    models = _get("/models")
    if "models" in models:
        print("Available models:")
        for m in models["models"]:
            size_gb = m.get("size", 0) / (1024**3)
            print(f"  {m['name']:<35s} {size_gb:.1f} GB")
    else:
        print(json.dumps(models, indent=2))


def cmd_gpu(_args):
    gpu = _get("/gpu")
    if "gpus" in gpu:
        for g in gpu["gpus"]:
            print(f"GPU {g['index']}: {g['name']}")
            print(f"  Temp:     {g['temperature_c']}°C")
            print(f"  GPU util: {g['gpu_utilization_pct']}%")
            print(f"  VRAM:     {g['memory_used_mb']}/{g['memory_total_mb']} MB "
                  f"({g['memory_utilization_pct']}%)")
    else:
        print(json.dumps(gpu, indent=2))


def cmd_projects(_args):
    projects = PROJECTS.list_projects()
    if not projects:
        print("No projects registered.")
        return
    print(json.dumps(projects, indent=2))


def cmd_spawn(args):
    created_path = spawn_project_from_template(
        name=args.name,
        description=args.description or "",
        template=args.template,
        repo_path=args.repo_path or "",
    )
    record = PROJECTS.add_project(
        name=args.name,
        repo_path=created_path,
        execution_mode=args.mode or cfg.default_execution_mode,
        builder_type=args.builder or "",
        active=True,
    )
    print(json.dumps({"status": "created", "path": created_path, "project": record.__dict__}, indent=2))


def cmd_wake(args):
    script_path = Path(__file__).resolve().parent / "wake-on-lan.py"
    cmd = [sys.executable, str(script_path), args.mac]
    if args.ip:
        cmd.extend(["--ip", args.ip])
    if args.port:
        cmd.extend(["--port", str(args.port)])
    subprocess.run(cmd, check=True)


def cmd_update_windows(args):
    """Run git pull on the Windows swarm repo via SSH; optionally restart cursor worker."""
    host = cfg.windows_host or os.getenv("WINDOWS_HOST", "")
    user = cfg.windows_user or os.getenv("WINDOWS_USER", "")
    if not host or not user:
        raise SystemExit("WINDOWS_HOST and WINDOWS_USER are required (set in env or .env).")
    key = (cfg.windows_ssh_key or os.getenv("WINDOWS_SSH_KEY", "")).strip()
    repo_path = (getattr(args, "repo_path", None) or "").strip() or f"C:\\Users\\{user}\\repos\\swarm"
    # Run in cmd.exe so && works (default SSH shell on Windows may be PowerShell)
    remote_cmd = f'cmd /c "cd /d {repo_path} && git checkout main && git pull'
    if getattr(args, "restart_worker", False):
        remote_cmd += " && powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\cursor-worker.ps1 stop && powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\cursor-worker.ps1 start"
    remote_cmd += '"'
    ssh_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15"]
    if key:
        ssh_cmd.extend(["-i", key])
    ssh_cmd.extend([f"{user}@{host}", remote_cmd])
    print(f"Running on Windows ({user}@{host}): git checkout main && git pull ...")
    subprocess.run(ssh_cmd, check=True)
    print("Done.")


def main():
    global SWARM_URL
    parser = argparse.ArgumentParser(
        prog="swarm-remote",
        description="Remote CLI for the AI Dev Swarm",
    )
    parser.add_argument("--url", default=SWARM_URL,
                        help="Swarm API URL (default: $SWARM_URL or http://localhost:9000)")
    sub = parser.add_subparsers(dest="command", required=True)

    # submit
    p_submit = sub.add_parser("submit", help="Submit a task to the swarm")
    p_submit.add_argument("feature", help="Feature request description")
    p_submit.add_argument("--plan", help="Path to a plan file (markdown)")
    p_submit.add_argument("--builder", help="Force builder type")
    p_submit.add_argument("--repo", help="Git repo URL to clone")
    p_submit.set_defaults(func=cmd_submit)

    # dispatch
    p_dispatch = sub.add_parser("dispatch", help="Dispatch a task via configured mode")
    p_dispatch.add_argument("feature", help="Feature request description")
    p_dispatch.add_argument("--plan", help="Path to a plan file (markdown)")
    p_dispatch.add_argument("--builder", help="Force builder type")
    p_dispatch.add_argument("--repo-path", help="Local repo path for local/cursor mode")
    p_dispatch.add_argument("--repo-url", help="Git repo URL for remote ollama mode")
    p_dispatch.add_argument("--mode", choices=["local", "ollama", "cursor"], help="Execution mode")
    p_dispatch.add_argument("--wait", action="store_true", help="Wait for completion in cursor mode")
    p_dispatch.add_argument(
        "--async",
        dest="async_dispatch",
        action="store_true",
        help="Compatibility alias for cursor async dispatch (async is default in cursor mode).",
    )
    p_dispatch.set_defaults(func=cmd_dispatch)

    # run (dispatch + poll until done, retry on failure; cursor only)
    p_run = sub.add_parser(
        "run",
        help="Dispatch with cursor mode, poll until done, retry on failure (over and over until success)",
    )
    p_run.add_argument("feature", help="Feature request description")
    p_run.add_argument("--plan", help="Path to a plan file (markdown)")
    p_run.add_argument("--builder", help="Force builder type")
    p_run.add_argument("--repo-path", help="Local repo path for cursor mode")
    p_run.add_argument("--repo-url", help="Git repo URL (cursor mode)")
    p_run.add_argument("--mode", choices=["cursor"], default="cursor", help="Must be cursor")
    p_run.add_argument("--retry", type=int, default=0, help="Number of retries after failure (default 0)")
    p_run.add_argument("--poll-interval", type=float, default=5, help="Seconds between status polls (default 5)")
    p_run.set_defaults(func=cmd_run)

    # update-windows
    p_update_win = sub.add_parser(
        "update-windows",
        help="SSH to Windows and run git pull in the swarm repo; optionally restart cursor worker",
    )
    p_update_win.add_argument(
        "--repo-path",
        default="",
        help="Windows repo path (default: C:\\Users\\<WINDOWS_USER>\\repos\\swarm)",
    )
    p_update_win.add_argument(
        "--restart-worker",
        action="store_true",
        help="After pull, run cursor-worker.ps1 stop then start",
    )
    p_update_win.set_defaults(func=cmd_update_windows)

    # status
    p_status = sub.add_parser("status", help="Check task status")
    p_status.add_argument("task_id", nargs="?", help="Task ID (omit for all)")
    p_status.set_defaults(func=cmd_status)

    # logs
    p_logs = sub.add_parser("logs", help="Stream task logs")
    p_logs.add_argument("task_id", help="Task ID")
    p_logs.set_defaults(func=cmd_logs)

    # cancel
    p_cancel = sub.add_parser("cancel", help="Cancel a task")
    p_cancel.add_argument("task_id", help="Task ID")
    p_cancel.set_defaults(func=cmd_cancel)

    # health
    sub.add_parser("health", help="Service health check").set_defaults(func=cmd_health)

    # models
    sub.add_parser("models", help="List Ollama models").set_defaults(func=cmd_models)

    # gpu
    sub.add_parser("gpu", help="GPU utilization").set_defaults(func=cmd_gpu)

    # projects
    sub.add_parser("projects", help="List registered projects").set_defaults(func=cmd_projects)

    # spawn
    p_spawn = sub.add_parser("spawn", help="Create a project from template")
    p_spawn.add_argument("name", help="Project name")
    p_spawn.add_argument(
        "--template",
        default="empty",
        choices=["empty", "python-cli", "nextjs-app", "wordpress-plugin", "shopify-theme"],
        help="Template to scaffold",
    )
    p_spawn.add_argument("--description", help="Short project description")
    p_spawn.add_argument("--repo-path", help="Parent path where project should be created")
    p_spawn.add_argument("--mode", choices=["local", "ollama", "cursor"], help="Default execution mode")
    p_spawn.add_argument("--builder", help="Default builder type")
    p_spawn.set_defaults(func=cmd_spawn)

    # wake
    p_wake = sub.add_parser("wake", help="Wake Windows machine via WoL")
    p_wake.add_argument("mac", help="Target MAC address")
    p_wake.add_argument("--ip", help="Broadcast IP")
    p_wake.add_argument("--port", type=int, help="UDP port")
    p_wake.set_defaults(func=cmd_wake)

    args = parser.parse_args()
    SWARM_URL = args.url
    args.func(args)


if __name__ == "__main__":
    main()
