"""Git operations — status, diff, commit, branch, log."""

from __future__ import annotations

import shlex
import subprocess
from typing import Optional, Sequence, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from swarm.config import cfg


def _git(args: Sequence[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cfg.repo_root,
        )
        out = result.stdout.strip()
        if result.returncode != 0:
            err = result.stderr.strip()
            return f"{out}\n[STDERR] {err}\n[EXIT CODE: {result.returncode}]".strip()
        return out or "(no output)"
    except Exception as e:
        return f"[ERROR] {e}"


class EmptyInput(BaseModel):
    pass


class GitStatusTool(BaseTool):
    name: str = "GitStatus"
    description: str = "Run `git status` and return the result."
    args_schema: Type[BaseModel] = EmptyInput

    def _run(self) -> str:
        return _git(["status", "--short"])


class GitDiffInput(BaseModel):
    staged: bool = Field(default=False, description="Show staged changes only")


class GitDiffTool(BaseTool):
    name: str = "GitDiff"
    description: str = "Run `git diff` to see uncommitted changes."
    args_schema: Type[BaseModel] = GitDiffInput

    def _run(self, staged: bool = False) -> str:
        args = ["diff"]
        if staged:
            args.append("--cached")
        return _git(args)


class GitCommitInput(BaseModel):
    message: str = Field(..., description="Commit message")
    files: str = Field(
        default=".",
        description="Space-separated file paths to stage, or '.' for all",
    )


class GitCommitTool(BaseTool):
    name: str = "GitCommit"
    description: str = "Stage files and create a git commit."
    args_schema: Type[BaseModel] = GitCommitInput

    def _run(self, message: str, files: str = ".") -> str:
        add_result = _git(["add", *shlex.split(files)])
        if "[ERROR]" in add_result or "[EXIT CODE:" in add_result:
            return add_result
        return _git(["commit", "-m", message])


class GitBranchInput(BaseModel):
    name: Optional[str] = Field(
        default=None,
        description="Branch name to create and switch to. Omit to list branches.",
    )


class GitBranchTool(BaseTool):
    name: str = "GitBranch"
    description: str = "List branches or create + switch to a new branch."
    args_schema: Type[BaseModel] = GitBranchInput

    def _run(self, name: Optional[str] = None) -> str:
        if name:
            return _git(["checkout", "-b", name])
        return _git(["branch", "-a"])


class GitLogInput(BaseModel):
    count: int = Field(default=10, description="Number of commits to show")


class GitLogTool(BaseTool):
    name: str = "GitLog"
    description: str = "Show recent git log (one-line format)."
    args_schema: Type[BaseModel] = GitLogInput

    def _run(self, count: int = 10) -> str:
        return _git(["log", "--oneline", "-n", str(count)])
