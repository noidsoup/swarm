"""Tests for LintTool and RunTestsTool path injection prevention."""

from __future__ import annotations

import subprocess

from swarm.config import cfg
from swarm.tools.lint_tool import LintTool
from swarm.tools.test_tool import RunTestsTool


# ---------------------------------------------------------------------------
# LintTool
# ---------------------------------------------------------------------------


def test_lint_tool_rejects_path_traversal(tmp_path) -> None:
    cfg.repo_root = str(tmp_path)
    tool = LintTool()
    result = tool._run(path="../outside")
    assert "[ERROR]" in result
    assert "escapes repo root" in result


def test_lint_tool_resolve_path_rejects_escape(tmp_path) -> None:
    cfg.repo_root = str(tmp_path)
    tool = LintTool()
    assert tool._resolve_path("../etc/passwd") is None


def test_lint_tool_resolve_path_accepts_valid(tmp_path) -> None:
    cfg.repo_root = str(tmp_path)
    tool = LintTool()
    resolved = tool._resolve_path("src/main.py")
    assert resolved is not None
    assert resolved.startswith(str(tmp_path.resolve()))


def test_lint_tool_uses_list_based_subprocess(tmp_path, monkeypatch) -> None:
    """Ensure subprocess is called with a list (shell=False) to prevent injection."""
    cfg.repo_root = str(tmp_path)

    calls: list[dict] = []

    def fake_run(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    tool = LintTool()
    # Patch _detect_linters to return a known linter
    monkeypatch.setattr(tool, "_detect_linters", lambda: [("ruff", ["ruff", "check"])])

    tool._run(path=".")

    assert len(calls) == 1
    assert isinstance(calls[0]["args"][0], list), "subprocess must be called with a list"
    assert calls[0]["kwargs"].get("shell") is False


def test_lint_tool_detect_linters_returns_lists(tmp_path, monkeypatch) -> None:
    cfg.repo_root = str(tmp_path)
    tool = LintTool()
    linters = tool._detect_linters()
    for name, cmd_parts in linters:
        assert isinstance(cmd_parts, list), f"cmd_parts for {name!r} must be a list"


# ---------------------------------------------------------------------------
# RunTestsTool
# ---------------------------------------------------------------------------


def test_run_tests_tool_rejects_path_traversal(tmp_path, monkeypatch) -> None:
    cfg.repo_root = str(tmp_path)
    tool = RunTestsTool()
    # Force a runner to be detected so path validation is reached
    monkeypatch.setattr(tool, "_detect_runner", lambda: ("pytest", ["pytest"]))
    result = tool._run(path="../outside")
    assert "[ERROR]" in result
    assert "escapes repo root" in result


def test_run_tests_tool_resolve_path_rejects_escape(tmp_path) -> None:
    cfg.repo_root = str(tmp_path)
    tool = RunTestsTool()
    assert tool._resolve_path("../secret") is None


def test_run_tests_tool_uses_list_based_subprocess(tmp_path, monkeypatch) -> None:
    cfg.repo_root = str(tmp_path)

    calls: list[dict] = []

    def fake_run(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    tool = RunTestsTool()
    monkeypatch.setattr(tool, "_detect_runner", lambda: ("pytest", ["pytest"]))

    tool._run(path="")

    assert len(calls) == 1
    assert isinstance(calls[0]["args"][0], list), "subprocess must be called with a list"
    assert calls[0]["kwargs"].get("shell") is False
