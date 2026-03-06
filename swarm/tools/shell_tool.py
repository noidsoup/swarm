"""Run arbitrary shell commands with timeout protection."""

from __future__ import annotations

import subprocess
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from swarm.config import cfg


class ShellInput(BaseModel):
    command: str = Field(..., description="Shell command to execute")


class ShellTool(BaseTool):
    name: str = "Shell"
    description: str = (
        "Execute a shell command and return stdout + stderr. "
        "Use for npm, pip, eslint, jest, or any CLI tool."
    )
    args_schema: Type[BaseModel] = ShellInput

    def _run(self, command: str) -> str:
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=cfg.shell_timeout,
                cwd=cfg.repo_root,
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\n[STDERR]\n{result.stderr}"
            if result.returncode != 0:
                output += f"\n[EXIT CODE: {result.returncode}]"
            return output.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            return f"[ERROR] Command timed out after {cfg.shell_timeout}s"
        except Exception as e:
            return f"[ERROR] {e}"
