from __future__ import annotations

import json

from fastapi.testclient import TestClient

import swarm.mcp_server as mcp_server
from swarm.api import app
from swarm.task_store import TaskStore


def test_api_task_responses_include_learning_summaries(monkeypatch) -> None:
    store = TaskStore()
    task = store.create(feature="demo task")
    task.context_summary = "Context summary"
    task.retrieval_summary = "Retrieval summary"
    task.validation_summary = "Validation summary"
    task.eval_summary = "Eval summary"
    task.adaptation_summary = "Adaptation summary"
    task.artifacts_dir = "/tmp/.swarm/runs/swarm-demo"
    store.update(task)
    monkeypatch.setattr("swarm.api.store", store)

    client = TestClient(app)

    list_response = client.get("/tasks")
    detail_response = client.get(f"/tasks/{task.task_id}")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200

    list_payload = list_response.json()
    detail_payload = detail_response.json()

    assert list_payload[0]["context_summary"] == "Context summary"
    assert list_payload[0]["retrieval_summary"] == "Retrieval summary"
    assert list_payload[0]["validation_summary"] == "Validation summary"
    assert list_payload[0]["eval_summary"] == "Eval summary"
    assert list_payload[0]["adaptation_summary"] == "Adaptation summary"
    assert list_payload[0]["artifacts_dir"] == "/tmp/.swarm/runs/swarm-demo"

    assert detail_payload["context_summary"] == "Context summary"
    assert detail_payload["retrieval_summary"] == "Retrieval summary"
    assert detail_payload["validation_summary"] == "Validation summary"
    assert detail_payload["eval_summary"] == "Eval summary"
    assert detail_payload["adaptation_summary"] == "Adaptation summary"
    assert detail_payload["artifacts_dir"] == "/tmp/.swarm/runs/swarm-demo"


def test_mcp_swarm_status_exposes_learning_summaries(monkeypatch) -> None:
    run_id = "swarm-demo"
    monkeypatch.setattr(mcp_server, "_last_run_id", run_id)
    monkeypatch.setattr(
        mcp_server,
        "_runs",
        {
            run_id: {
                "status": "complete",
                "task_id": run_id,
                "context_summary": "Context summary",
                "retrieval_summary": "Retrieval summary",
                "validation_summary": "Validation summary",
                "eval_summary": "Eval summary",
                "adaptation_summary": "Adaptation summary",
                "artifacts_dir": "/tmp/.swarm/runs/swarm-demo",
            }
        },
    )

    payload = json.loads(mcp_server.swarm_status())

    assert payload["context_summary"] == "Context summary"
    assert payload["retrieval_summary"] == "Retrieval summary"
    assert payload["validation_summary"] == "Validation summary"
    assert payload["eval_summary"] == "Eval summary"
    assert payload["adaptation_summary"] == "Adaptation summary"
    assert payload["artifacts_dir"] == "/tmp/.swarm/runs/swarm-demo"
