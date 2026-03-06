"""Run linters on specified files or the whole project."""

from __future__ import annotations

import shutil
import subprocess
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from swarm.config import cfg


class LintInput(BaseModel):
    path: str = Field(
        default=".",
        description="File or directory to lint (relative to repo root)",
    )
    fix: bool = Field(default=False, description="Auto-fix issues if possible")


class LintTool(BaseTool):
    name: str = "Lint"
    description: str = (
        "Run the project's linter. Auto-detects eslint, pylint, ruff, or flake8. "
        "Returns lint output with errors and warnings."
    )
    args_schema: Type[BaseModel] = LintInput

    def _run(self, path: str = ".", fix: bool = False) -> str:
        linters = self._detect_linters()
        if not linters:
            return "[WARN] No linter found. Install eslint, ruff, pylint, or flake8."

        results: list[str] = []
        for name, cmd in linters:
            fix_flag = ""
            if fix:
                fix_flag = " --fix" if name in ("eslint", "ruff") else ""
            full_cmd = f"{cmd}{fix_flag} {path}"
            try:
                result = subprocess.run(
                    full_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=cfg.shell_timeout,
                    cwd=cfg.repo_root,
                )
                output = result.stdout + result.stderr
                results.append(f"=== {name} ===\n{output.strip()}")
            except subprocess.TimeoutExpired:
                results.append(f"=== {name} ===\n[TIMEOUT]")
            except Exception as e:
                results.append(f"=== {name} ===\n[ERROR] {e}")

        return "\n\n".join(results)

    def _detect_linters(self) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []
        candidates = [
            ("eslint", "npx eslint"),
            ("ruff", "ruff check"),
            ("pylint", "pylint"),
            ("flake8", "flake8"),
        ]
        for name, cmd in candidates:
            binary = cmd.split()[0]
            if binary == "npx" or shutil.which(binary):
                found.append((name, cmd))
        return found
