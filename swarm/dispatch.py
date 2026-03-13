"""Execution dispatcher for local, Docker API, and Cursor-worker modes."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
import time
from typing import Any

import requests

from swarm.cursor_worker import CursorWorkerClient
from swarm.errors import DispatchError
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
        wait_for_completion: bool = True,
    ) -> dict[str, Any]:
        mode = (execution_mode or getattr(self.cfg, "default_execution_mode", "local")).strip().lower()
        if mode not in {"local", "ollama", "cursor"}:
            raise DispatchError(f"Unsupported execution mode: {mode}")

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
            wait_for_completion=wait_for_completion,
        )

    def _dispatch_local(
        self,
        plan: str,
        feature_name: str,
        builder_type: str,
        repo_path: str,
    ) -> dict[str, Any]:
        from swarm.flow import WorkerSwarmFlow

        task_cfg = self.cfg.copy() if hasattr(self.cfg, "copy") else self.cfg
        if repo_path:
            task_cfg.repo_root = repo_path
        task_cfg.auto_commit = False

        smoke_profile = _is_smoke_task(plan=plan, feature_name=feature_name)
        with (
            _working_directory(repo_path or task_cfg.repo_root),
            _with_local_cfg_overrides(task_cfg),
            _local_execution_profile(task_cfg, smoke_profile=smoke_profile),
        ):
            task_id = new_task_id()
            artifact_dir = ensure_artifact_dir(repo_path or task_cfg.repo_root, task_id)
            effective_plan = _smoke_task_plan(plan=plan, feature_name=feature_name) if smoke_profile else plan
            flow = WorkerSwarmFlow(
                plan=effective_plan,
                feature_request=feature_name,
                builder_type=builder_type,
            )
            flow.state.run_artifacts_dir = artifact_dir

            def _run_flow() -> None:
                if smoke_profile:
                    if os.getenv("SWARM_SMOKE_SKIP_LLM", "").lower() in ("1", "true", "yes"):
                        flow.state.build_summary = (
                            "STATUS: SMOKE_OK\nNOTE: Pipeline check only (SWARM_SMOKE_SKIP_LLM=1)."
                        )
                    else:
                        flow.run_selected_phases(["build"])
                else:
                    flow.kickoff()

            try:
                _run_flow()
            except (ValueError, OSError) as exc:
                if "closed" in str(exc).lower() and task_cfg.verbose:
                    # Retry with verbose=False to avoid CrewAI/Rich writing to closed streams
                    task_cfg.verbose = False
                    flow = WorkerSwarmFlow(
                        plan=effective_plan,
                        feature_request=feature_name,
                        builder_type=builder_type,
                    )
                    flow.state.run_artifacts_dir = artifact_dir
                    _run_flow()
                else:
                    raise

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
            raise DispatchError("WINDOWS_SWARM_API is required for ollama mode")

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
        wait_for_completion: bool = True,
    ) -> dict[str, Any]:
        if not self.connection.enabled():
            raise DispatchError("WINDOWS_HOST and WINDOWS_USER are required for cursor mode")
        client = CursorWorkerClient(self.connection)
        task_payload = {
            "plan": plan,
            "feature_name": feature_name,
            "builder_type": builder_type,
            "repo_path": repo_path,
            "repo_url": repo_url,
        }
        if wait_for_completion:
            return client.submit_and_wait(task_payload)
        task_id = client.submit(task_payload)
        return {
            "status": "queued",
            "task_id": task_id,
            "execution_mode": "cursor",
            "feature_name": feature_name,
            "builder_type": builder_type or "auto",
            "submitted_at": utcnow_iso(),
        }


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


@contextmanager
def _with_local_cfg_overrides(task_cfg: Any):
    """Temporarily bind flow/agent module-level cfg references to task cfg.

    Flow and agent modules import cfg as a module global, so local dispatch uses
    this context to route per-run config changes (e.g., smoke model overrides)
    without mutating the process-wide singleton.
    """
    if not hasattr(task_cfg, "llm_for_role"):
        yield
        return

    flow_module = None
    agents_module = None
    original_flow_cfg = None
    original_agents_cfg = None
    try:
        import swarm.flow as flow_module  # local import avoids import-time side effects
        original_flow_cfg = getattr(flow_module, "cfg", None)
        flow_module.cfg = task_cfg
    except Exception:
        flow_module = None

    try:
        import swarm.agents as agents_module
        original_agents_cfg = getattr(agents_module, "cfg", None)
        agents_module.cfg = task_cfg
    except Exception:
        agents_module = None

    try:
        yield
    finally:
        if flow_module is not None and original_flow_cfg is not None:
            flow_module.cfg = original_flow_cfg
        if agents_module is not None and original_agents_cfg is not None:
            agents_module.cfg = original_agents_cfg


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


def _smoke_task_plan(*, plan: str, feature_name: str) -> str:
    summary = (feature_name or plan or "cursor smoke test").strip()
    return (
        "SMOKE TASK (FAST PATH):\n"
        f"- Scope: {summary}\n"
        "- Do not modify files.\n"
        "- Read at most one small repo file (prefer app.py, then README.md) to verify tool access.\n"
        "- Avoid long analysis, full-project scans, or multi-step refactors.\n"
        "- Return exactly 2 lines:\n"
        "  1) STATUS: SMOKE_OK or SMOKE_BLOCKED\n"
        "  2) NOTE: one short sentence with the checked file path or blocker."
    )
