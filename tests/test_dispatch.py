from __future__ import annotations

import os
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

from swarm.dispatch import Dispatcher


def test_dispatch_local_runs_flow_from_repo_path(tmp_path: Path, monkeypatch) -> None:
    original_cwd = Path.cwd()
    observed: dict[str, str] = {}

    class FakeFlow:
        def __init__(self, plan: str, feature_request: str, builder_type: str) -> None:
            self._builder = builder_type or "python_dev"
            self.state = SimpleNamespace(
                review_iteration=0,
                build_summary="done",
                review_feedback="",
                quality_report="",
                polish_report="",
            )

        def kickoff(self) -> None:
            observed["cwd"] = os.getcwd()

    fake_module = ModuleType("swarm.flow")
    fake_module.WorkerSwarmFlow = FakeFlow
    monkeypatch.setitem(sys.modules, "swarm.flow", fake_module)

    cfg = SimpleNamespace(
        default_execution_mode="local",
        repo_root=str(original_cwd),
        auto_commit=True,
    )
    dispatcher = Dispatcher(cfg)

    result = dispatcher.dispatch(
        plan="Test plan",
        feature_name="demo",
        builder_type="python_dev",
        repo_path=str(tmp_path),
        execution_mode="local",
    )

    assert result["status"] == "complete"
    assert observed["cwd"] == str(tmp_path)
    assert Path.cwd() == original_cwd


def test_dispatch_local_uses_lightweight_profile_for_smoke_tasks(tmp_path: Path, monkeypatch) -> None:
    observed: dict[str, object] = {}

    class FakeFlow:
        def __init__(self, plan: str, feature_request: str, builder_type: str) -> None:
            observed["plan"] = plan
            observed["worker_model_at_init"] = cfg.worker_model
            observed["max_reviews_at_init"] = cfg.max_review_loops
            self._builder = builder_type or "python_dev"
            self.state = SimpleNamespace(
                review_iteration=0,
                build_summary="smoke-done",
                review_feedback="",
                quality_report="",
                polish_report="",
            )

        def kickoff(self) -> None:
            observed["kickoff_called"] = True

        def run_selected_phases(self, selected_phases: list[str]) -> str:
            observed["selected_phases"] = list(selected_phases)
            return "ok"

    from swarm.config import cfg

    fake_module = ModuleType("swarm.flow")
    fake_module.WorkerSwarmFlow = FakeFlow
    monkeypatch.setitem(sys.modules, "swarm.flow", fake_module)
    monkeypatch.setenv("WORKER_FALLBACK_MODEL", "ollama/gemma3:4b")
    monkeypatch.setenv("SWARM_SMOKE_SKIP_LLM", "0")

    original_worker_model = cfg.worker_model
    original_max_reviews = cfg.max_review_loops
    cfg.worker_model = "ollama/qwen2.5-coder:7b"
    cfg.max_review_loops = 3

    dispatcher = Dispatcher(cfg)
    result = dispatcher.dispatch(
        plan="cursor smoke test",
        feature_name="cursor smoke test",
        builder_type="python_dev",
        repo_path=str(tmp_path),
        execution_mode="local",
    )

    assert result["status"] == "complete"
    assert observed["worker_model_at_init"] == "ollama/gemma3:4b"
    assert observed["max_reviews_at_init"] == 1
    assert observed["selected_phases"] == ["build"]
    assert "SMOKE TASK (FAST PATH)" in str(observed["plan"])
    assert "Do not modify files." in str(observed["plan"])
    assert "kickoff_called" not in observed
    assert cfg.worker_model == "ollama/qwen2.5-coder:7b"
    assert cfg.max_review_loops == 3

    cfg.worker_model = original_worker_model
    cfg.max_review_loops = original_max_reviews


def test_dispatch_local_smoke_skip_llm_returns_immediately(tmp_path: Path, monkeypatch) -> None:
    """With SWARM_SMOKE_SKIP_LLM=1, smoke task skips LLM and returns fixed build_summary."""
    monkeypatch.setenv("SWARM_SMOKE_SKIP_LLM", "1")
    cfg = SimpleNamespace(
        default_execution_mode="local",
        repo_root=str(tmp_path),
        auto_commit=True,
    )
    dispatcher = Dispatcher(cfg)
    result = dispatcher.dispatch(
        plan="cursor smoke test",
        feature_name="cursor smoke test",
        builder_type="python_dev",
        repo_path=str(tmp_path),
        execution_mode="local",
    )
    assert result["status"] == "complete"
    assert "SMOKE_OK" in result["build_summary"]
    assert "SWARM_SMOKE_SKIP_LLM" in result["build_summary"]


def test_dispatch_local_sets_run_artifacts_dir_under_repo(tmp_path: Path, monkeypatch) -> None:
    observed: dict[str, str] = {}

    class FakeFlow:
        def __init__(self, plan: str, feature_request: str, builder_type: str) -> None:
            self._builder = builder_type or "python_dev"
            self.state = SimpleNamespace(
                review_iteration=0,
                build_summary="done",
                review_feedback="",
                quality_report="",
                polish_report="",
                run_artifacts_dir="",
            )

        def kickoff(self) -> None:
            observed["run_artifacts_dir"] = self.state.run_artifacts_dir

    fake_module = ModuleType("swarm.flow")
    fake_module.WorkerSwarmFlow = FakeFlow
    monkeypatch.setitem(sys.modules, "swarm.flow", fake_module)

    cfg = SimpleNamespace(
        default_execution_mode="local",
        repo_root=str(tmp_path),
        auto_commit=True,
    )
    dispatcher = Dispatcher(cfg)

    result = dispatcher.dispatch(
        plan="Test plan",
        feature_name="demo",
        builder_type="python_dev",
        repo_path=str(tmp_path),
        execution_mode="local",
    )

    assert result["status"] == "complete"
    assert observed["run_artifacts_dir"]
    assert Path(observed["run_artifacts_dir"]).is_dir()
    assert Path(observed["run_artifacts_dir"]).parent == tmp_path / ".swarm" / "runs"


def test_dispatch_cursor_wait_false_returns_queued_payload(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, connection) -> None:
            self.connection = connection

        def submit(self, payload: dict) -> str:
            assert payload["feature_name"] == "demo"
            return "swarm-queued123"

    monkeypatch.setattr("swarm.dispatch.CursorWorkerClient", FakeClient)
    cfg = SimpleNamespace(
        default_execution_mode="cursor",
        windows_host="192.168.0.2",
        windows_user="nicho",
        windows_ssh_key="",
        windows_swarm_api="http://localhost:9000",
        windows_cursor_workspace="",
    )
    dispatcher = Dispatcher(cfg)

    result = dispatcher.dispatch(
        plan="Do thing",
        feature_name="demo",
        builder_type="python_dev",
        execution_mode="cursor",
        wait_for_completion=False,
    )

    assert result["status"] == "queued"
    assert result["task_id"] == "swarm-queued123"
    assert result["execution_mode"] == "cursor"


def test_dispatch_cursor_wait_true_uses_blocking_submit_and_wait(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, connection) -> None:
            self.connection = connection

        def submit_and_wait(self, payload: dict) -> dict:
            assert payload["feature_name"] == "demo"
            return {"status": "complete", "task_id": "swarm-done", "execution_mode": "cursor"}

    monkeypatch.setattr("swarm.dispatch.CursorWorkerClient", FakeClient)
    cfg = SimpleNamespace(
        default_execution_mode="cursor",
        windows_host="192.168.0.2",
        windows_user="nicho",
        windows_ssh_key="",
        windows_swarm_api="http://localhost:9000",
        windows_cursor_workspace="",
    )
    dispatcher = Dispatcher(cfg)

    result = dispatcher.dispatch(
        plan="Do thing",
        feature_name="demo",
        builder_type="python_dev",
        execution_mode="cursor",
        wait_for_completion=True,
    )

    assert result["status"] == "complete"
    assert result["task_id"] == "swarm-done"
