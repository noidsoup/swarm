from __future__ import annotations

from pathlib import Path

import pytest

from swarm.run_artifacts import artifact_dir_for_task, artifact_file_map, ensure_artifact_dir


def test_artifact_dir_for_task_is_deterministic(tmp_path: Path) -> None:
    first = artifact_dir_for_task(str(tmp_path), "swarm-abc123")
    second = artifact_dir_for_task(str(tmp_path), "swarm-abc123")

    assert first == second
    assert Path(first) == tmp_path / ".swarm" / "runs" / "swarm-abc123"


def test_artifact_file_map_includes_expected_files(tmp_path: Path) -> None:
    files = artifact_file_map(str(tmp_path), "swarm-abc123")

    assert files == {
        "context": str(tmp_path / ".swarm" / "runs" / "swarm-abc123" / "context.json"),
        "retrieval": str(tmp_path / ".swarm" / "runs" / "swarm-abc123" / "retrieval.json"),
        "validation": str(tmp_path / ".swarm" / "runs" / "swarm-abc123" / "validation.json"),
        "eval": str(tmp_path / ".swarm" / "runs" / "swarm-abc123" / "eval.json"),
        "events": str(tmp_path / ".swarm" / "runs" / "swarm-abc123" / "events.jsonl"),
    }


def test_ensure_artifact_dir_creates_directory_under_root(tmp_path: Path) -> None:
    artifact_dir = Path(ensure_artifact_dir(str(tmp_path), "swarm-abc123"))

    assert artifact_dir.exists()
    assert artifact_dir.is_dir()
    assert artifact_dir.parent == tmp_path / ".swarm" / "runs"
    assert tmp_path in artifact_dir.parents


def test_artifact_helpers_reject_path_traversal_task_ids(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        artifact_dir_for_task(str(tmp_path), "../escape")
