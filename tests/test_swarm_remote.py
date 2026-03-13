from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

import scripts.swarm_remote as swarm_remote


def test_cmd_dispatch_cursor_defaults_to_async(monkeypatch, capsys) -> None:
    seen: dict[str, object] = {}

    class FakeDispatcher:
        def __init__(self, cfg) -> None:
            self.cfg = cfg

        def dispatch(self, **kwargs):
            seen.update(kwargs)
            return {"status": "queued", "task_id": "swarm-123", "execution_mode": "cursor"}

    monkeypatch.setattr(swarm_remote, "Dispatcher", FakeDispatcher)
    monkeypatch.setattr(swarm_remote.cfg, "default_execution_mode", "cursor")
    args = SimpleNamespace(
        feature="demo",
        plan=None,
        builder=None,
        repo_path="",
        repo_url="",
        mode="cursor",
        wait=False,
        async_dispatch=False,
    )

    swarm_remote.cmd_dispatch(args)
    output = capsys.readouterr().out

    assert seen["wait_for_completion"] is False
    assert "swarm-remote status swarm-123" in output
    assert "swarm-remote cancel swarm-123" in output


def test_cmd_dispatch_cursor_wait_overrides_async_default(monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeDispatcher:
        def __init__(self, cfg) -> None:
            self.cfg = cfg

        def dispatch(self, **kwargs):
            seen.update(kwargs)
            return {"status": "complete", "task_id": "swarm-123", "execution_mode": "cursor"}

    monkeypatch.setattr(swarm_remote, "Dispatcher", FakeDispatcher)
    monkeypatch.setattr(swarm_remote.cfg, "default_execution_mode", "cursor")
    args = SimpleNamespace(
        feature="demo",
        plan=None,
        builder=None,
        repo_path="",
        repo_url="",
        mode="cursor",
        wait=True,
        async_dispatch=False,
    )

    swarm_remote.cmd_dispatch(args)
    assert seen["wait_for_completion"] is True


def test_cmd_dispatch_async_non_cursor_exits(monkeypatch) -> None:
    monkeypatch.setattr(swarm_remote.cfg, "default_execution_mode", "local")
    args = SimpleNamespace(
        feature="demo",
        plan=None,
        builder=None,
        repo_path="",
        repo_url="",
        mode="local",
        wait=False,
        async_dispatch=True,
    )
    with pytest.raises(SystemExit):
        swarm_remote.cmd_dispatch(args)


def test_cmd_status_falls_back_to_cursor_tracker_on_api_404(monkeypatch, capsys) -> None:
    def raise_404(path: str):
        request = httpx.Request("GET", "http://example/tasks/swarm-1")
        response = httpx.Response(404, request=request)
        raise httpx.HTTPStatusError("not found", request=request, response=response)

    class FakeClient:
        def get_status(self, task_id: str) -> dict:
            return {"status": "running", "task_id": task_id, "execution_mode": "cursor"}

    monkeypatch.setattr(swarm_remote, "_get", raise_404)
    monkeypatch.setattr(swarm_remote, "_cursor_client_or_none", lambda: FakeClient())
    args = SimpleNamespace(task_id="swarm-1")

    swarm_remote.cmd_status(args)
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "running"
    assert payload["task_id"] == "swarm-1"


def test_cmd_cancel_falls_back_to_cursor_tracker_on_api_404(monkeypatch, capsys) -> None:
    def raise_404(path: str):
        request = httpx.Request("DELETE", "http://example/tasks/swarm-2")
        response = httpx.Response(404, request=request)
        raise httpx.HTTPStatusError("not found", request=request, response=response)

    class FakeClient:
        def cancel(self, task_id: str) -> dict:
            return {"status": "cancelled", "task_id": task_id, "execution_mode": "cursor"}

    monkeypatch.setattr(swarm_remote, "_delete", raise_404)
    monkeypatch.setattr(swarm_remote, "_cursor_client_or_none", lambda: FakeClient())
    args = SimpleNamespace(task_id="swarm-2")

    swarm_remote.cmd_cancel(args)
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "cancelled"
    assert payload["task_id"] == "swarm-2"
