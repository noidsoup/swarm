#!/usr/bin/env python3
"""swarm-remote — Mac-side CLI for submitting tasks to the remote swarm.

Install on Mac:
    pip install httpx rich
    chmod +x scripts/swarm_remote.py
    # or: alias swarm-remote='python3 /path/to/swarm/scripts/swarm_remote.py'

Usage:
    swarm-remote submit "Build a login page with OAuth"
    swarm-remote submit --plan plan.md "Implement the plan"
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
    from rich import print as rprint
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from swarm.config import cfg
from swarm.dispatch import Dispatcher
from swarm.projects import ProjectRegistry, spawn_project_from_template

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
    print(f"\nTrack it:")
    print(f"  swarm-remote status {result['task_id']}")
    print(f"  swarm-remote logs {result['task_id']}")


def cmd_dispatch(args):
    plan = ""
    if args.plan:
        with open(args.plan, encoding="utf-8") as f:
            plan = f.read()

    dispatcher = Dispatcher(cfg)
    result = dispatcher.dispatch(
        plan=plan or args.feature,
        feature_name=args.feature,
        builder_type=args.builder or "",
        repo_path=args.repo_path or "",
        repo_url=args.repo_url or "",
        execution_mode=args.mode or "",
    )
    print(json.dumps(result, indent=2))


def cmd_status(args):
    if args.task_id:
        task = _get(f"/tasks/{args.task_id}")
        print(json.dumps(task, indent=2))
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
    except KeyboardInterrupt:
        print("\nStopped streaming.")


def cmd_cancel(args):
    result = _delete(f"/tasks/{args.task_id}")
    print(result.get("message", result))


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
    p_dispatch.set_defaults(func=cmd_dispatch)

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
