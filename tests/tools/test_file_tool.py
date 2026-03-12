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


def test_write_tool_blocks_no_overlap_overwrite(tmp_path) -> None:
    cfg.repo_root = str(tmp_path)
    writer = FileWriteTool()
    reader = FileReadTool()

    writer._run("app.py", "def main():\n    return 'hello'\n")
    result = writer._run("app.py", "# offload validation complete.\n")

    assert "[ERROR]" in result
    assert "no-overlap overwrite" in result
    assert reader._run("app.py") == "def main():\n    return 'hello'\n"


def test_write_tool_allows_no_overlap_overwrite_with_env(tmp_path, monkeypatch) -> None:
    cfg.repo_root = str(tmp_path)
    writer = FileWriteTool()
    reader = FileReadTool()

    writer._run("app.py", "def main():\n    return 'hello'\n")
    monkeypatch.setenv("SWARM_ALLOW_NO_OVERLAP_REWRITE", "true")
    result = writer._run("app.py", "# offload validation complete.\n")

    assert "Wrote" in result
    assert reader._run("app.py") == "# offload validation complete.\n"
