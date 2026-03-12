"""Run linters on specified files or the whole project."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
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

        resolved_path = self._resolve_path(path)
        if resolved_path is None:
            return f"[ERROR] Path escapes repo root: {path}"

        results: list[str] = []
        for name, cmd_parts in linters:
            args = list(cmd_parts)
            if fix and name in ("eslint", "ruff"):
                args.append("--fix")
            args.append(resolved_path)
            try:
                result = subprocess.run(
                    args,
                    shell=False,
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

    def _resolve_path(self, path: str) -> str | None:
        """Resolve path relative to repo root, rejecting traversal attempts."""
        base = Path(cfg.repo_root).resolve()
        full = (base / path).resolve()
        try:
            full.relative_to(base)
        except ValueError:
            return None
        return str(full)

    def _detect_linters(self) -> list[tuple[str, list[str]]]:
        found: list[tuple[str, list[str]]] = []
        candidates: list[tuple[str, list[str]]] = [
            ("eslint", ["npx", "eslint"]),
            ("ruff", ["ruff", "check"]),
            ("pylint", ["pylint"]),
            ("flake8", ["flake8"]),
        ]
        for name, cmd_parts in candidates:
            binary = cmd_parts[0]
            if binary == "npx" or shutil.which(binary):
                found.append((name, cmd_parts))
        return found
