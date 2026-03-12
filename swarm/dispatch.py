"""Execution dispatcher for local, Docker API, and Cursor-worker modes."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
import time
from typing import Any

import requests

from swarm.cursor_worker import CursorWorkerClient
from swarm.run_artifacts import ensure_artifact_dir
from swarm.task_models import new_task_id
from swarm.task_models import utcnow_iso


@dataclass
class WindowsConnection:
    host: str = ""
    user: str = ""
    ssh_key_path: str = ""
    swarm_api_url: str = "http://localhost:9000"
    cursor_workspace: str = ""

    def enabled(self) -> bool:
        return bool(self.host and self.user)


class Dispatcher:
    """Route a swarm task to the configured execution backend."""

    def __init__(self, cfg: Any) -> None:
        self.cfg = cfg
        self.connection = WindowsConnection(
            host=getattr(cfg, "windows_host", ""),
            user=getattr(cfg, "windows_user", ""),
            ssh_key_path=getattr(cfg, "windows_ssh_key", ""),
            swarm_api_url=getattr(cfg, "windows_swarm_api", "http://localhost:9000"),
            cursor_workspace=getattr(cfg, "windows_cursor_workspace", ""),
        )

    def dispatch(
        self,
        plan: str,
        feature_name: str = "",
        builder_type: str = "",
        repo_path: str = "",
        repo_url: str = "",
        execution_mode: str = "",
    ) -> dict[str, Any]:
        mode = (execution_mode or getattr(self.cfg, "default_execution_mode", "local")).strip().lower()
        if mode not in {"local", "ollama", "cursor"}:
            raise ValueError(f"Unsupported execution mode: {mode}")

        if mode == "local":
            return self._dispatch_local(
                plan=plan,
                feature_name=feature_name,
                builder_type=builder_type,
                repo_path=repo_path,
            )
        if mode == "ollama":
            return self._dispatch_ollama(
                plan=plan,
                feature_name=feature_name,
                builder_type=builder_type,
                repo_url=repo_url,
            )
        return self._dispatch_cursor(
            plan=plan,
            feature_name=feature_name,
            builder_type=builder_type,
            repo_path=repo_path,
            repo_url=repo_url,
        )

    def _dispatch_local(
        self,
        plan: str,
        feature_name: str,
        builder_type: str,
        repo_path: str,
    ) -> dict[str, Any]:
        from swarm.flow import WorkerSwarmFlow

        if repo_path:
            self.cfg.repo_root = repo_path
        self.cfg.auto_commit = False

        smoke_profile = _is_smoke_task(plan=plan, feature_name=feature_name)
        with _working_directory(repo_path or self.cfg.repo_root), _local_execution_profile(
            self.cfg,
            smoke_profile=smoke_profile,
        ):
            task_id = new_task_id()
            artifact_dir = ensure_artifact_dir(repo_path or self.cfg.repo_root, task_id)
            flow = WorkerSwarmFlow(
                plan=plan,
                feature_request=feature_name,
                builder_type=builder_type,
            )
            flow.state.run_artifacts_dir = artifact_dir
            if smoke_profile:
                flow.run_selected_phases(["build"])
            else:
                flow.kickoff()
        return {
            "status": "complete",
            "builder": flow._builder,
            "review_iterations": flow.state.review_iteration,
            "build_summary": flow.state.build_summary[:3000],
            "review_feedback": flow.state.review_feedback[:1500],
            "quality_report": flow.state.quality_report[:3000],
            "polish_report": flow.state.polish_report[:1500],
            "completed_at": utcnow_iso(),
            "execution_mode": "local",
        }

    def _dispatch_ollama(
        self,
        plan: str,
        feature_name: str,
        builder_type: str,
        repo_url: str,
    ) -> dict[str, Any]:
        if not self.connection.swarm_api_url:
            raise ValueError("WINDOWS_SWARM_API is required for ollama mode")

        payload = {
            "feature": feature_name or "Swarm task",
            "plan": plan,
            "builder_type": builder_type or "",
            "repo_url": repo_url or "",
        }
        create_resp = requests.post(
            f"{self.connection.swarm_api_url.rstrip('/')}/tasks",
            json=payload,
            timeout=30,
        )
        create_resp.raise_for_status()
        body = create_resp.json()
        task_id = body["task_id"]

        deadline_seconds = int(os.getenv("SWARM_REMOTE_TIMEOUT", "3600"))
        start_ts = time.time()
        while True:
            status_resp = requests.get(
                f"{self.connection.swarm_api_url.rstrip('/')}/tasks/{task_id}",
                timeout=30,
            )
            status_resp.raise_for_status()
            task = status_resp.json()
            status = task.get("status", "")
            if status in {"completed", "failed", "cancelled"}:
                return {
                    "status": "complete" if status == "completed" else "error",
                    "task_id": task_id,
                    "builder": task.get("builder_type") or builder_type or "auto",
                    "review_iterations": task.get("review_iterations", 0),
                    "build_summary": task.get("build_summary", "")[:3000],
                    "review_feedback": task.get("review_feedback", "")[:1500],
                    "quality_report": task.get("quality_report", "")[:3000],
                    "polish_report": task.get("polish_report", "")[:1500],
                    "error": task.get("error", "")[:2000],
                    "completed_at": task.get("completed_at") or utcnow_iso(),
                    "execution_mode": "ollama",
                }
            if time.time() - start_ts > deadline_seconds:
                raise TimeoutError(f"Remote task timed out after {deadline_seconds}s: {task_id}")
            time.sleep(3)

    def _dispatch_cursor(
        self,
        plan: str,
        feature_name: str,
        builder_type: str,
        repo_path: str,
        repo_url: str,
    ) -> dict[str, Any]:
        if not self.connection.enabled():
            raise ValueError("WINDOWS_HOST and WINDOWS_USER are required for cursor mode")
        client = CursorWorkerClient(self.connection)
        task_payload = {
            "plan": plan,
            "feature_name": feature_name,
            "builder_type": builder_type,
            "repo_path": repo_path,
            "repo_url": repo_url,
        }
        return client.submit_and_wait(task_payload)


@contextmanager
def _working_directory(path: str):
    current = os.getcwd()
    target = path or current
    os.chdir(target)
    try:
        yield
    finally:
        os.chdir(current)


@contextmanager
def _local_execution_profile(cfg: Any, *, smoke_profile: bool):
    original_worker_model = getattr(cfg, "worker_model", "")
    original_max_review_loops = getattr(cfg, "max_review_loops", 3)
    if smoke_profile:
        cfg.worker_model = os.getenv(
            "WORKER_SMOKE_MODEL",
            os.getenv("WORKER_FALLBACK_MODEL", "ollama/gemma3:4b"),
        )
        cfg.max_review_loops = 1
    try:
        yield
    finally:
        cfg.worker_model = original_worker_model
        cfg.max_review_loops = original_max_review_loops


def _is_smoke_task(*, plan: str, feature_name: str) -> bool:
    text = f"{feature_name}\n{plan}".lower()
    smoke_markers = (
        "smoke test",
        "cursor smoke",
        "e2e smoke",
        "health check",
        "sanity check",
    )
    return any(marker in text for marker in smoke_markers)
