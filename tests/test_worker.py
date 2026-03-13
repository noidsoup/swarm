from __future__ import annotations

from types import SimpleNamespace

import swarm.worker as worker
from swarm.task_models import TaskResult, TaskStatus


class FakeStore:
    def __init__(self, task: TaskResult) -> None:
        self._task = task

    def get(self, task_id: str) -> TaskResult | None:
        if self._task.task_id == task_id:
            return self._task
        return None

    def update(self, task: TaskResult) -> None:
        self._task = task

    def append_log(self, task_id: str, message: str) -> None:
        if self._task.task_id == task_id:
            self._task.log.append(message)


def test_is_ollama_runner_startup_timeout_matches_expected_message() -> None:
    err = RuntimeError('OllamaException - {"error":"timed out waiting for llama runner to start"}')
    assert worker._is_ollama_runner_startup_timeout(err)


def test_is_transient_error_catches_connection_reset():
    assert worker._is_transient_error(RuntimeError("connection reset by peer"))


def test_is_transient_error_catches_429():
    assert worker._is_transient_error(RuntimeError("HTTP 429 Too Many Requests"))


def test_is_transient_error_catches_timeout():
    assert worker._is_transient_error(RuntimeError("request timed out"))


def test_is_transient_error_rejects_value_error():
    assert not worker._is_transient_error(ValueError("bad input"))


def test_validate_repo_url_blocks_dns_rebinding(monkeypatch):
    import socket
    import pytest
    fake_result = [(socket.AF_INET, 1, 0, "", ("127.0.0.1", 0))]
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: fake_result)
    with pytest.raises(ValueError, match="private address"):
        worker._validate_repo_url("https://evil.example.com/repo.git")


def test_worker_retries_with_fallback_model_on_runner_timeout(monkeypatch) -> None:
    task = TaskResult(
        task_id="swarm-test123",
        status=TaskStatus.QUEUED,
        feature="test fallback retry",
    )
    fake_store = FakeStore(task)
    monkeypatch.setattr(worker, "store", fake_store)
    monkeypatch.setattr(worker, "_prepare_workspace", lambda task_id, repo_url: "/tmp/swarm-test123")
    monkeypatch.setenv("WORKER_FALLBACK_MODEL", "ollama/gemma3:4b")

    from swarm import config as config_module

    fake_cfg = SimpleNamespace(
        repo_root="/tmp",
        auto_commit=False,
        worker_model="ollama/qwen2.5-coder:7b",
    )
    monkeypatch.setattr(config_module, "cfg", fake_cfg)

    class FakeFlow:
        def __init__(self) -> None:
            self.state = SimpleNamespace(
                build_summary="build ok",
                review_feedback="APPROVED",
                quality_report="quality ok",
                polish_report="polish ok",
            )

    calls = {"count": 0}

    def fake_execute_flow(task_obj, cfg_obj, context_pack_json="", retrieval_pack_json=""):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError('OllamaException - {"error":"timed out waiting for llama runner to start"}')
        return FakeFlow()

    monkeypatch.setattr(worker, "_execute_flow", fake_execute_flow)

    worker._run_swarm(task.task_id)

    result = fake_store.get(task.task_id)
    assert result is not None
    assert result.status == TaskStatus.COMPLETED
    assert calls["count"] == 2
    assert fake_cfg.worker_model == "ollama/gemma3:4b"
    assert any("retrying with fallback model" in line for line in result.log)
