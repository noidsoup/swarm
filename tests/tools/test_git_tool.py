from __future__ import annotations

import subprocess

from swarm.tools.git_tool import GitCommitTool, _git


def test_git_runs_without_shell(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_run(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = _git(["status", "--short"])

    assert result == "ok"
    assert calls[0]["args"][0] == ["git", "status", "--short"]
    assert "shell" not in calls[0]["kwargs"]


def test_git_commit_passes_message_as_literal_argument(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(*args, **kwargs):
        calls.append(args[0])
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    tool = GitCommitTool()

    result = tool._run('fix: keep "quotes" and ; shell chars', "README.md")

    assert result == "ok"
    assert calls[0] == ["git", "add", "README.md"]
    assert calls[1] == ["git", "commit", "-m", 'fix: keep "quotes" and ; shell chars']
