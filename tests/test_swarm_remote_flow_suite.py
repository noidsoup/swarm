from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

import scripts.swarm_remote as swarm_remote


def _read_error(*_args, **_kwargs):
    raise httpx.ReadError("connection reset")


def test_api_fallback_to_cursor_for_not_found_and_transport_errors() -> None:
    request = httpx.Request("GET", "http://example.local/tasks/swarm-1")
    not_found = httpx.HTTPStatusError(
        "not found",
        request=request,
        response=httpx.Response(404, request=request),
    )
    bad_gateway = httpx.HTTPStatusError(
        "bad gateway",
        request=request,
        response=httpx.Response(502, request=request),
    )

    assert swarm_remote._api_fallback_to_cursor(not_found) is True
    assert swarm_remote._api_fallback_to_cursor(httpx.ReadError("transport down")) is True
    assert swarm_remote._api_fallback_to_cursor(bad_gateway) is False
    assert swarm_remote._api_fallback_to_cursor(ValueError("nope")) is False


def test_cmd_logs_falls_back_to_cursor_tracker_on_api_transport_error(monkeypatch, capsys) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self._payloads = iter(
                [
                    {"status": "queued", "task_id": "swarm-logs", "execution_mode": "cursor"},
                    {"status": "running", "task_id": "swarm-logs", "execution_mode": "cursor"},
                    {"status": "completed", "task_id": "swarm-logs", "execution_mode": "cursor"},
                ]
            )

        def get_status(self, task_id: str) -> dict:
            payload = next(self._payloads)
            payload["task_id"] = task_id
            return payload

    monkeypatch.setattr(swarm_remote.httpx, "stream", _read_error)
    monkeypatch.setattr(swarm_remote, "_cursor_client_or_none", lambda: FakeClient())
    monkeypatch.setattr(swarm_remote.time, "sleep", lambda _seconds: None)
    args = SimpleNamespace(task_id="swarm-logs")

    swarm_remote.cmd_logs(args)
    output = capsys.readouterr().out

    assert "API logs unavailable for this task. Polling cursor worker status/outbox..." in output
    assert '"status": "queued"' in output
    assert '"status": "running"' in output
    assert '"status": "completed"' in output


def test_cmd_logs_raises_when_api_transport_fails_without_cursor_config(monkeypatch) -> None:
    monkeypatch.setattr(swarm_remote.httpx, "stream", _read_error)
    monkeypatch.setattr(swarm_remote, "_cursor_client_or_none", lambda: None)
    args = SimpleNamespace(task_id="swarm-logs-missing")

    with pytest.raises(SystemExit):
        swarm_remote.cmd_logs(args)


def test_cmd_cancel_falls_back_to_cursor_tracker_on_api_transport_error(monkeypatch, capsys) -> None:
    class FakeClient:
        def cancel(self, task_id: str) -> dict:
            return {"status": "cancelled", "task_id": task_id, "execution_mode": "cursor"}

    monkeypatch.setattr(swarm_remote, "_delete", _read_error)
    monkeypatch.setattr(swarm_remote, "_cursor_client_or_none", lambda: FakeClient())
    args = SimpleNamespace(task_id="swarm-cancel")

    swarm_remote.cmd_cancel(args)
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "cancelled"
    assert payload["task_id"] == "swarm-cancel"


def test_cmd_cancel_raises_when_transport_fails_without_cursor_config(monkeypatch) -> None:
    monkeypatch.setattr(swarm_remote, "_delete", _read_error)
    monkeypatch.setattr(swarm_remote, "_cursor_client_or_none", lambda: None)
    args = SimpleNamespace(task_id="swarm-cancel-missing")

    with pytest.raises(SystemExit):
        swarm_remote.cmd_cancel(args)

