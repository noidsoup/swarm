from __future__ import annotations

import json
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace

import pytest

from swarm.cursor_worker import (
    CursorWorkerClient,
    CursorWorkerService,
    build_cursor_worker_daemon_command,
)


class DummyDispatcher:
    def __init__(self, result: dict | None = None, error: Exception | None = None) -> None:
        self.result = result or {"status": "complete", "build_summary": "done"}
        self.error = error
        self.calls: list[dict] = []

    def dispatch(
        self,
        *,
        plan: str,
        feature_name: str = "",
        builder_type: str = "",
        repo_path: str = "",
        repo_url: str = "",
        execution_mode: str = "",
    ) -> dict:
        self.calls.append(
            {
                "plan": plan,
                "feature_name": feature_name,
                "builder_type": builder_type,
                "repo_path": repo_path,
                "repo_url": repo_url,
                "execution_mode": execution_mode,
            }
        )
        if self.error:
            raise self.error
        return dict(self.result)


class SlowDispatcher(DummyDispatcher):
    def __init__(self, delay_seconds: float) -> None:
        super().__init__()
        self.delay_seconds = delay_seconds

    def dispatch(self, **kwargs) -> dict:
        time.sleep(self.delay_seconds)
        return super().dispatch(**kwargs)


def test_cursor_worker_service_processes_inbox_task_and_writes_outbox(tmp_path: Path) -> None:
    dispatcher = DummyDispatcher(
        result={
            "status": "complete",
            "build_summary": "implemented",
            "review_feedback": "",
            "quality_report": "",
            "polish_report": "",
        }
    )
    service = CursorWorkerService(root=tmp_path, dispatcher=dispatcher)
    inbox_file = tmp_path / "inbox" / "swarm-abc123.json"
    inbox_file.parent.mkdir(parents=True, exist_ok=True)
    inbox_file.write_text(
        json.dumps(
            {
                "task_id": "swarm-abc123",
                "plan": "Implement feature",
                "feature_name": "demo",
                "builder_type": "python_dev",
                "repo_path": str(tmp_path / "repo"),
                "repo_url": "",
            }
        ),
        encoding="utf-8",
    )

    processed = service.process_once()

    assert processed is True
    outbox_file = tmp_path / "outbox" / "swarm-abc123.json"
    assert outbox_file.exists()
    payload = json.loads(outbox_file.read_text(encoding="utf-8"))
    assert payload["task_id"] == "swarm-abc123"
    assert payload["status"] == "complete"
    assert payload["build_summary"] == "implemented"
    assert payload["execution_mode"] == "cursor"
    assert not inbox_file.exists()
    assert dispatcher.calls == [
        {
            "plan": "Implement feature",
            "feature_name": "demo",
            "builder_type": "python_dev",
            "repo_path": str(tmp_path / "repo"),
            "repo_url": "",
            "execution_mode": "local",
        }
    ]


def test_cursor_worker_service_writes_error_result_when_dispatch_fails(tmp_path: Path) -> None:
    dispatcher = DummyDispatcher(error=RuntimeError("boom"))
    service = CursorWorkerService(root=tmp_path, dispatcher=dispatcher)
    inbox_file = tmp_path / "inbox" / "swarm-err.json"
    inbox_file.parent.mkdir(parents=True, exist_ok=True)
    inbox_file.write_text(
        json.dumps(
            {
                "task_id": "swarm-err",
                "plan": "Broken task",
                "feature_name": "demo",
            }
        ),
        encoding="utf-8",
    )

    processed = service.process_once()

    assert processed is True
    payload = json.loads((tmp_path / "outbox" / "swarm-err.json").read_text(encoding="utf-8"))
    assert payload["task_id"] == "swarm-err"
    assert payload["status"] == "error"
    assert "boom" in payload["error"]
    assert payload["execution_mode"] == "cursor"
    assert not inbox_file.exists()


def test_cursor_worker_service_returns_false_when_no_tasks_are_waiting(tmp_path: Path) -> None:
    service = CursorWorkerService(root=tmp_path, dispatcher=DummyDispatcher())

    processed = service.process_once()

    assert processed is False


def test_cursor_worker_service_times_out_and_writes_timeout_result(tmp_path: Path) -> None:
    service = CursorWorkerService(
        root=tmp_path,
        dispatcher=SlowDispatcher(delay_seconds=0.05),
        task_timeout_seconds=0.01,
        heartbeat_interval=0.005,
    )
    inbox_file = tmp_path / "inbox" / "swarm-timeout.json"
    inbox_file.parent.mkdir(parents=True, exist_ok=True)
    inbox_file.write_text(
        json.dumps(
            {
                "task_id": "swarm-timeout",
                "plan": "Long task",
                "feature_name": "demo",
            }
        ),
        encoding="utf-8",
    )

    processed = service.process_once()

    assert processed is True
    payload = json.loads((tmp_path / "outbox" / "swarm-timeout.json").read_text(encoding="utf-8"))
    assert payload["task_id"] == "swarm-timeout"
    assert payload["status"] == "error"
    assert "timed out" in payload["error"].lower()
    assert payload["execution_mode"] == "cursor"


def test_cursor_worker_client_waits_for_terminal_result(monkeypatch) -> None:
    client = CursorWorkerClient(SimpleNamespace(user="nicho", host="127.0.0.1", ssh_key_path=""))
    responses = iter(
        [
            subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps({"status": "running"}) + "\n", stderr=""),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps({"status": "complete", "task_id": "swarm-abc123", "build_summary": "done"}) + "\n",
                stderr="",
            ),
        ]
    )

    monkeypatch.setattr(client, "_run_ssh", lambda remote_cmd, timeout=30: next(responses))
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    monkeypatch.setenv("WINDOWS_CURSOR_TIMEOUT", "1")

    result = client._poll_result("swarm-abc123")

    assert result["status"] == "complete"
    assert result["build_summary"] == "done"
    assert result["execution_mode"] == "cursor"


def test_build_cursor_worker_daemon_command_includes_runtime_options(tmp_path: Path) -> None:
    command = build_cursor_worker_daemon_command(
        script_path=tmp_path / "scripts" / "cursor_worker.py",
        root=tmp_path / "queue",
        poll_interval=0.5,
        task_timeout_seconds=120,
        log_file=tmp_path / "worker.log",
        pid_file=tmp_path / "worker.pid",
    )

    joined = " ".join(str(part) for part in command)
    assert "--daemon-child" in joined
    assert "--root" in joined
    assert "--poll-interval" in joined
    assert "--task-timeout" in joined


def test_cursor_worker_service_returns_false_when_result_write_fails(tmp_path: Path, monkeypatch) -> None:
    service = CursorWorkerService(root=tmp_path, dispatcher=DummyDispatcher())
    inbox_file = tmp_path / "inbox" / "swarm-writefail.json"
    inbox_file.parent.mkdir(parents=True, exist_ok=True)
    inbox_file.write_text(
        json.dumps(
            {
                "task_id": "swarm-writefail",
                "plan": "Write fails",
                "feature_name": "demo",
            }
        ),
        encoding="utf-8",
    )

    def fail_finalize(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(service, "_finalize_result", fail_finalize)

    processed = service.process_once()

    assert processed is False
    assert inbox_file.exists()


def test_cursor_worker_service_run_forever_continues_after_loop_exception(monkeypatch, tmp_path: Path) -> None:
    service = CursorWorkerService(root=tmp_path, dispatcher=DummyDispatcher())
    calls: list[str] = []

    def fake_process_once() -> bool:
        calls.append("call")
        if len(calls) == 1:
            raise OSError("disk full")
        raise KeyboardInterrupt

    monkeypatch.setattr(service, "process_once", fake_process_once)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    with pytest.raises(KeyboardInterrupt):
        service.run_forever(poll_interval=0)

    assert len(calls) == 2
