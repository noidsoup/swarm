"""Background worker — pulls tasks from the Redis queue and runs the swarm.

Runs as: python -m swarm.worker
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import traceback

from swarm.task_models import TaskStatus, utcnow_iso
from swarm.task_store import store


POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL", "5"))
WORKSPACE = os.getenv("REPO_ROOT", "/workspace")


def _log(task_id: str, msg: str) -> None:
    ts = utcnow_iso()
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    store.append_log(task_id, line)


def _prepare_workspace(task_id: str, repo_url: str) -> str:
    """Clone or create a workspace directory for the task."""
    task_dir = os.path.join(WORKSPACE, task_id)
    os.makedirs(task_dir, exist_ok=True)

    if repo_url:
        _log(task_id, f"Cloning {repo_url}...")
        subprocess.run(
            ["git", "clone", "--depth=1", repo_url, task_dir],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        _log(task_id, "Clone complete.")
    return task_dir


def _run_swarm(task_id: str) -> None:
    task = store.get(task_id)
    if not task:
        return

    task.status = TaskStatus.RUNNING
    task.started_at = utcnow_iso()
    store.update(task)

    _log(task_id, f"Starting swarm for: {task.feature}")

    try:
        task_dir = _prepare_workspace(task_id, task.repo_url)

        from swarm.config import cfg
        cfg.repo_root = task_dir
        cfg.auto_commit = False

        _log(task_id, "Importing WorkerSwarmFlow...")
        from swarm.flow import WorkerSwarmFlow

        flow = WorkerSwarmFlow(
            plan=task.plan or task.feature,
            feature_request=task.feature,
            builder_type=task.builder_type,
        )

        _log(task_id, "Running agent pipeline...")
        flow.kickoff()

        task = store.get(task_id)
        task.status = TaskStatus.COMPLETED
        task.completed_at = utcnow_iso()
        task.build_summary = flow.state.build_summary[:5000]
        task.review_feedback = flow.state.review_feedback[:3000]
        task.quality_report = flow.state.quality_report[:5000]
        task.polish_report = flow.state.polish_report[:3000]
        store.update(task)

        _log(task_id, "Swarm completed successfully.")

    except Exception as e:
        task = store.get(task_id)
        task.status = TaskStatus.FAILED
        task.completed_at = utcnow_iso()
        task.error = f"{e}\n{traceback.format_exc()[-2000:]}"
        store.update(task)
        _log(task_id, f"Swarm failed: {e}")


def main() -> None:
    print(f"Swarm worker started. Polling every {POLL_INTERVAL}s.", flush=True)
    print(f"Workspace: {WORKSPACE}", flush=True)
    os.makedirs(WORKSPACE, exist_ok=True)

    while True:
        task_id = store.next_queued()
        if task_id:
            _run_swarm(task_id)
        else:
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
