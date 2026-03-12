from __future__ import annotations

import pytest

from swarm.config import cfg
from swarm.tools.file_tool import FileReadTool, FileWriteTool, _resolve_repo_path


def test_resolve_repo_path_rejects_escape(tmp_path) -> None:
    cfg.repo_root = str(tmp_path)

    with pytest.raises(ValueError, match="escapes repo root"):
        _resolve_repo_path("../outside.txt")


def test_file_tools_round_trip_inside_repo(tmp_path) -> None:
    cfg.repo_root = str(tmp_path)
    writer = FileWriteTool()
    reader = FileReadTool()

    result = writer._run("nested/example.txt", "hello swarm")

    assert "Wrote" in result
    assert reader._run("nested/example.txt") == "hello swarm"
