"""Read, write, and list files in the repo."""

from __future__ import annotations

from pathlib import Path
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from swarm.config import cfg


def _resolve_repo_path(path: str) -> Path:
    base = Path(cfg.repo_root).resolve()
    full = (base / path).resolve()
    try:
        full.relative_to(base)
    except ValueError:
        raise ValueError(f"Path escapes repo root: {path}")
    return full


class FileReadInput(BaseModel):
    path: str = Field(..., description="Relative path to the file to read")


class FileReadTool(BaseTool):
    name: str = "ReadFile"
    description: str = "Read the full contents of a file. Path is relative to repo root."
    args_schema: Type[BaseModel] = FileReadInput

    def _run(self, path: str) -> str:
        try:
            full = _resolve_repo_path(path)
        except ValueError as e:
            return f"[ERROR] {e}"
        if not full.is_file():
            return f"[ERROR] File not found: {path}"
        try:
            return full.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[ERROR] {e}"


class FileWriteInput(BaseModel):
    path: str = Field(..., description="Relative path to write to")
    content: str = Field(..., description="Full file content to write")


class FileWriteTool(BaseTool):
    name: str = "WriteFile"
    description: str = (
        "Write content to a file (creates dirs if needed). "
        "Path is relative to repo root. Overwrites existing files."
    )
    args_schema: Type[BaseModel] = FileWriteInput

    def _run(self, path: str, content: str) -> str:
        try:
            full = _resolve_repo_path(path)
        except ValueError as e:
            return f"[ERROR] {e}"
        try:
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
            return f"Wrote {len(content)} chars to {path}"
        except Exception as e:
            return f"[ERROR] {e}"


_MAX_DEPTH_LIMIT = 10


class ListDirInput(BaseModel):
    path: str = Field(
        default=".",
        description="Relative directory path to list (default: repo root)",
    )
    max_depth: int = Field(default=2, description="Max directory depth to list (capped at 10)")


class ListDirectoryTool(BaseTool):
    name: str = "ListDirectory"
    description: str = "List files and folders in a directory. Returns a tree view."
    args_schema: Type[BaseModel] = ListDirInput

    def _run(self, path: str = ".", max_depth: int = 2) -> str:
        max_depth = min(max(max_depth, 1), _MAX_DEPTH_LIMIT)
        try:
            root = _resolve_repo_path(path)
        except ValueError as e:
            return f"[ERROR] {e}"
        if not root.is_dir():
            return f"[ERROR] Not a directory: {path}"
        lines: list[str] = []
        self._walk(root, root, lines, 0, max_depth)
        return "\n".join(lines) or "(empty directory)"

    def _walk(
        self,
        base: Path,
        current: Path,
        lines: list[str],
        depth: int,
        max_depth: int,
    ) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return
        skip = {"node_modules", ".git", "__pycache__", ".venv", "venv"}
        for entry in entries:
            if entry.name in skip:
                continue
            rel = entry.relative_to(base)
            indent = "  " * depth
            if entry.is_dir():
                lines.append(f"{indent}{rel}/")
                self._walk(base, entry, lines, depth + 1, max_depth)
            else:
                lines.append(f"{indent}{rel}")
