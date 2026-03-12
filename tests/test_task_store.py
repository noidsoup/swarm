from __future__ import annotations

from swarm.task_models import TaskStatus
from swarm.task_store import TaskStore


def test_create_and_get_task_in_memory_store(monkeypatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    store = TaskStore()

    task = store.create(feature="demo")

    loaded = store.get(task.task_id)

    assert loaded is not None
    assert loaded.task_id == task.task_id
    assert loaded.status == TaskStatus.QUEUED


def test_next_queued_accepts_serialized_status_value(monkeypatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    store = TaskStore()
    task = store.create(feature="demo")
    store._memory[task.task_id]["status"] = TaskStatus.QUEUED.value

    assert store.next_queued() == task.task_id


def test_append_log_persists_log_lines(monkeypatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    store = TaskStore()
    task = store.create(feature="demo")

    store.append_log(task.task_id, "started")

    assert store.get(task.task_id).log == ["started"]
