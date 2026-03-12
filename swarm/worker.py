"""Background worker — pulls tasks from the Redis queue and runs the swarm.

Runs as: python -m swarm.worker
"""

from __future__ import annotations

import ipaddress
import logging
import os
import subprocess
import time
import traceback
from urllib.parse import urlparse

from swarm.logging_utils import configure_logging
from swarm.task_models import TaskStatus, utcnow_iso
from swarm.task_store import store


POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL", "5"))
WORKSPACE = os.getenv("REPO_ROOT", "/workspace")
logger = logging.getLogger(__name__)


def _log(task_id: str, msg: str) -> None:
    ts = utcnow_iso()
    line = f"[{ts}] {msg}"
    logger.info("task_id=%s %s", task_id, msg)
    store.append_log(task_id, line)


def _prepare_workspace(task_id: str, repo_url: str) -> str:
    """Clone or create a workspace directory for the task."""
    task_dir = os.path.join(WORKSPACE, task_id)
    os.makedirs(task_dir, exist_ok=True)

    if repo_url:
        _validate_repo_url(repo_url)
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


def _validate_repo_url(repo_url: str) -> None:
    """Reject local/private clone targets and unsupported schemes."""
    ssh_host = None
    if repo_url.startswith("git@"):
        ssh_host = repo_url.split("@", 1)[1].split(":", 1)[0]
        scheme = "ssh"
        host = ssh_host
    else:
        parsed = urlparse(repo_url)
        scheme = parsed.scheme
        host = parsed.hostname

    if scheme not in {"https", "http", "ssh", "git"}:
        raise ValueError(f"Unsupported repo URL scheme: {repo_url}")
    if not host:
        raise ValueError(f"Invalid repo URL: {repo_url}")

    blocked_hosts = {"localhost", "127.0.0.1", "::1"}
    if host.lower() in blocked_hosts or host.lower().endswith(".local"):
        raise ValueError(f"Refusing local repo URL: {repo_url}")

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return

    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
    ):
        raise ValueError(f"Refusing private repo URL: {repo_url}")


def _is_ollama_runner_startup_timeout(exc: Exception) -> bool:
    """Detect Ollama runner startup timeout failures that can be retried."""
    msg = str(exc).lower()
    return (
        "timed out waiting for llama runner to start" in msg
        or ("ollamaexception" in msg and "runner" in msg and "timed out" in msg)
    )


def _fallback_worker_model() -> str:
    """Fallback model for unstable local Ollama runners."""
    return os.getenv("WORKER_FALLBACK_MODEL", "ollama/gemma3:4b")


def _execute_flow(task, cfg):
    """Build and execute a worker flow for a queued task."""
    _log(task.task_id, "Importing WorkerSwarmFlow...")
    from swarm.flow import WorkerSwarmFlow

    flow = WorkerSwarmFlow(
        plan=task.plan or task.feature,
        feature_request=task.feature,
        builder_type=task.builder_type,
    )

    _log(task.task_id, "Running agent pipeline...")
    flow.kickoff()
    return flow


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

        try:
            flow = _execute_flow(task, cfg)
        except Exception as first_error:
            if _is_ollama_runner_startup_timeout(first_error):
                fallback_model = _fallback_worker_model()
                if fallback_model and fallback_model != cfg.worker_model:
                    _log(
                        task_id,
                        f"Ollama runner startup timed out on {cfg.worker_model}; "
                        f"retrying with fallback model {fallback_model}.",
                    )
                    cfg.worker_model = fallback_model
                    flow = _execute_flow(task, cfg)
                    _log(task_id, f"Fallback model {fallback_model} succeeded.")
                else:
                    raise
            else:
                raise

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
    configure_logging()
    logger.info("Swarm worker started poll_interval=%s", POLL_INTERVAL)
    logger.info("Swarm worker workspace=%s", WORKSPACE)
    os.makedirs(WORKSPACE, exist_ok=True)

    while True:
        task_id = store.next_queued()
        if task_id:
            _run_swarm(task_id)
        else:
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
