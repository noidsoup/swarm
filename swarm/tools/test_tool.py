"""Run test suites — auto-detects jest, pytest, vitest."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from swarm.config import cfg


class RunTestsInput(BaseModel):
    path: str = Field(
        default="",
        description="Specific test file or directory. Empty = run all tests.",
    )


class RunTestsTool(BaseTool):
    name: str = "RunTests"
    description: str = (
        "Run the project's test suite. Auto-detects jest, vitest, pytest, or npm test. "
        "Returns pass/fail output."
    )
    args_schema: Type[BaseModel] = RunTestsInput

    def _run(self, path: str = "") -> str:
        runner = self._detect_runner()
        if not runner:
            return "[WARN] No test runner found. Install jest, vitest, or pytest."

        name, cmd = runner
        full_cmd = f"{cmd} {path}".strip()
        try:
            result = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=cfg.shell_timeout * 2,
                cwd=cfg.repo_root,
            )
            output = result.stdout + result.stderr
            status = "PASSED" if result.returncode == 0 else "FAILED"
            return f"=== {name} [{status}] ===\n{output.strip()}"
        except subprocess.TimeoutExpired:
            return f"=== {name} ===\n[TIMEOUT after {cfg.shell_timeout * 2}s]"
        except Exception as e:
            return f"[ERROR] {e}"

    def _detect_runner(self) -> tuple[str, str] | None:
        root = Path(cfg.repo_root)

        if (root / "vitest.config.ts").exists() or (root / "vitest.config.js").exists():
            return ("vitest", "npx vitest run")

        if (root / "jest.config.ts").exists() or (root / "jest.config.js").exists():
            return ("jest", "npx jest")

        pkg = root / "package.json"
        if pkg.exists():
            import json

            try:
                data = json.loads(pkg.read_text())
                if "jest" in data.get("devDependencies", {}):
                    return ("jest", "npx jest")
                if "scripts" in data and "test" in data["scripts"]:
                    return ("npm test", "npm test --")
            except Exception:
                pass

        if (root / "pytest.ini").exists() or (root / "pyproject.toml").exists():
            return ("pytest", "pytest")

        return None
