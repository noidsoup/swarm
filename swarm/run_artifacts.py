"""Helpers for storing per-run artifact files under a safe root."""

from __future__ import annotations

from pathlib import Path


_ALLOWED_TASK_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")


def _validate_task_id(task_id: str) -> str:
    if not task_id:
        raise ValueError("Task ID must not be empty")
    if any(char not in _ALLOWED_TASK_ID_CHARS for char in task_id):
        raise ValueError(f"Unsafe task ID: {task_id}")
    return task_id


def artifact_dir_for_task(root: str, task_id: str) -> str:
    safe_task_id = _validate_task_id(task_id)
    root_path = Path(root).resolve()
    artifact_path = (root_path / ".swarm" / "runs" / safe_task_id).resolve()
    artifact_path.relative_to(root_path)
    return str(artifact_path)


def ensure_artifact_dir(root: str, task_id: str) -> str:
    artifact_dir = Path(artifact_dir_for_task(root, task_id))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return str(artifact_dir)


def artifact_file_map(root: str, task_id: str) -> dict[str, str]:
    artifact_dir = Path(artifact_dir_for_task(root, task_id))
    return {
        "context": str(artifact_dir / "context.json"),
        "retrieval": str(artifact_dir / "retrieval.json"),
        "validation": str(artifact_dir / "validation.json"),
        "eval": str(artifact_dir / "eval.json"),
        "events": str(artifact_dir / "events.jsonl"),
    }
