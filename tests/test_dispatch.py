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
