from __future__ import annotations

import json
from pathlib import Path

from swarm.context_pack import build_context_pack


def test_build_context_pack_detects_nextjs_repo_and_commands(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "demo-app",
                "dependencies": {
                    "next": "15.0.0",
                    "react": "19.0.0",
                },
                "devDependencies": {
                    "typescript": "5.0.0",
                },
                "scripts": {
                    "lint": "next lint",
                    "test": "vitest run",
                    "build": "next build",
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text("# Agent Rules\nUse tests.\n", encoding="utf-8")
    rules_dir = tmp_path / ".cursor" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "frontend.mdc").write_text("Prefer existing UI patterns.\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo app\nA Next.js site.\n", encoding="utf-8")

    context = build_context_pack(str(tmp_path), "Add a dashboard page")

    assert context["builder_hint"] == "react_dev"
    assert context["stack"]["package_manager"] == "npm"
    assert context["stack"]["frameworks"] == ["nextjs", "react"]
    assert context["stack"]["languages"] == ["typescript", "javascript"]
    assert context["commands"]["lint"] == "npm run lint"
    assert context["commands"]["test"] == "npm test"
    assert "AGENTS.md" in context["instructions"]
    assert ".cursor/rules/frontend.mdc" in context["instructions"]
    assert "README.md" in context["instructions"]


def test_build_context_pack_detects_python_repo_and_risk_areas(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "demo-service"
version = "0.1.0"
        """.strip(),
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("fastapi\npytest\nruff\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo service\n", encoding="utf-8")
    (tmp_path / "auth_service.py").write_text("def login():\n    return True\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()

    context = build_context_pack(str(tmp_path), "Fix login validation")

    assert context["builder_hint"] == "python_dev"
    assert context["stack"]["frameworks"] == ["python"]
    assert context["commands"]["test"] == "pytest"
    assert context["commands"]["lint"] == "ruff check"
    assert "auth" in context["risk_areas"]
    assert "python" in context["repo_summary"].lower()


def test_build_context_pack_handles_sparse_repo_gracefully(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Tiny repo\n", encoding="utf-8")

    context = build_context_pack(str(tmp_path), "Document the setup")

    assert set(context) == {
        "repo_summary",
        "stack",
        "commands",
        "instructions",
        "risk_areas",
        "builder_hint",
    }
    assert context["builder_hint"] == "python_dev"
    assert isinstance(context["instructions"], list)
    assert isinstance(context["risk_areas"], list)
