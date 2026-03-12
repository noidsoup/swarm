"""Deterministic repo context pack builder for orchestration runs."""

from __future__ import annotations

import json
from pathlib import Path


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _detect_package_manager(repo_root: Path, package_json: dict) -> str:
    package_manager = str(package_json.get("packageManager", ""))
    if package_manager.startswith("pnpm"):
        return "pnpm"
    if package_manager.startswith("yarn"):
        return "yarn"
    if (repo_root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (repo_root / "yarn.lock").exists():
        return "yarn"
    if (repo_root / "package.json").exists():
        return "npm"
    if (repo_root / "pyproject.toml").exists() or (repo_root / "requirements.txt").exists():
        return "pip"
    return ""


def _detect_frameworks(repo_root: Path, package_json: dict) -> list[str]:
    deps = {
        **package_json.get("dependencies", {}),
        **package_json.get("devDependencies", {}),
    }
    frameworks: list[str] = []
    if "next" in deps:
        frameworks.append("nextjs")
    if "react" in deps:
        frameworks.append("react")
    if not frameworks and (
        (repo_root / "pyproject.toml").exists() or (repo_root / "requirements.txt").exists()
    ):
        frameworks.append("python")
    return frameworks


def _detect_languages(repo_root: Path, package_json: dict) -> list[str]:
    deps = {
        **package_json.get("dependencies", {}),
        **package_json.get("devDependencies", {}),
    }
    languages: list[str] = []
    if (repo_root / "package.json").exists():
        if "typescript" in deps or (repo_root / "tsconfig.json").exists():
            languages.append("typescript")
        languages.append("javascript")
    elif (repo_root / "pyproject.toml").exists() or (repo_root / "requirements.txt").exists():
        languages.append("python")
    return languages


def _detect_commands(repo_root: Path, package_json: dict, package_manager: str) -> dict[str, str]:
    commands: dict[str, str] = {}
    scripts = package_json.get("scripts", {})
    requirements_text = ""
    requirements_path = repo_root / "requirements.txt"
    if requirements_path.exists():
        requirements_text = requirements_path.read_text(encoding="utf-8", errors="ignore")
    if package_manager in {"npm", "pnpm", "yarn"}:
        install_command = {
            "npm": "npm install",
            "pnpm": "pnpm install",
            "yarn": "yarn install",
        }[package_manager]
        commands["install"] = install_command
        if "test" in scripts:
            commands["test"] = "npm test" if package_manager == "npm" else f"{package_manager} test"
        if "lint" in scripts:
            commands["lint"] = "npm run lint" if package_manager == "npm" else f"{package_manager} lint"
        if "build" in scripts:
            commands["build"] = "npm run build" if package_manager == "npm" else f"{package_manager} build"
    elif package_manager == "pip":
        if requirements_path.exists():
            commands["install"] = "pip install -r requirements.txt"
        if (repo_root / "tests").exists() or "pytest" in requirements_text:
            commands["test"] = "pytest"
        if (repo_root / "pyproject.toml").exists() or "ruff" in requirements_text:
            commands["lint"] = "ruff check"
    return commands


def _discover_instruction_files(repo_root: Path) -> list[str]:
    instruction_paths: list[Path] = []
    for name in ("AGENTS.md", "README.md", "AI_RUNBOOK.md"):
        candidate = repo_root / name
        if candidate.exists():
            instruction_paths.append(candidate)

    rules_dir = repo_root / ".cursor" / "rules"
    if rules_dir.exists():
        instruction_paths.extend(sorted(path for path in rules_dir.glob("*.mdc") if path.is_file()))

    return [path.relative_to(repo_root).as_posix() for path in instruction_paths]


def _infer_risk_areas(repo_root: Path, feature_request: str, plan: str) -> list[str]:
    haystack = " ".join(
        [feature_request.lower(), plan.lower(), " ".join(path.name.lower() for path in repo_root.rglob("*"))]
    )
    risk_areas: list[str] = []
    risk_keywords = {
        "auth": ("auth", "login", "oauth", "session", "jwt"),
        "billing": ("billing", "payment", "invoice", "stripe"),
        "database": ("migration", "schema", "database", "db"),
        "deployment": ("deploy", "docker", "terraform", "kubernetes"),
    }
    for risk, keywords in risk_keywords.items():
        if any(keyword in haystack for keyword in keywords):
            risk_areas.append(risk)
    return risk_areas


def _infer_builder_hint(frameworks: list[str], feature_request: str, plan: str) -> str:
    lower = f"{feature_request} {plan}".lower()
    if "wordpress" in lower or "php" in lower:
        return "wordpress_dev"
    if "shopify" in lower or "liquid" in lower:
        return "shopify_dev"
    if any(framework in frameworks for framework in ("nextjs", "react")):
        return "react_dev"
    return "python_dev"


def summarize_context_pack(context_pack: dict) -> str:
    frameworks = ", ".join(context_pack["stack"]["frameworks"]) or "unknown stack"
    instructions = ", ".join(context_pack["instructions"][:3]) or "no repo instructions found"
    risks = ", ".join(context_pack["risk_areas"]) or "no obvious risk areas"
    return (
        f"{context_pack['repo_summary']} "
        f"Frameworks: {frameworks}. "
        f"Instructions: {instructions}. "
        f"Risk areas: {risks}."
    )


def build_context_pack(repo_root: str, feature_request: str, plan: str = "") -> dict:
    root = Path(repo_root)
    package_json = _read_json(root / "package.json") if (root / "package.json").exists() else {}
    package_manager = _detect_package_manager(root, package_json)
    frameworks = _detect_frameworks(root, package_json)
    languages = _detect_languages(root, package_json)
    commands = _detect_commands(root, package_json, package_manager)
    instructions = _discover_instruction_files(root)
    risk_areas = _infer_risk_areas(root, feature_request, plan)
    builder_hint = _infer_builder_hint(frameworks, feature_request, plan)

    repo_parts = []
    if frameworks:
        repo_parts.append("/".join(frameworks))
    elif languages:
        repo_parts.append("/".join(languages))
    else:
        repo_parts.append("general")
    if package_manager:
        repo_parts.append(f"using {package_manager}")

    return {
        "repo_summary": f"Detected {' '.join(repo_parts)} repo.",
        "stack": {
            "frameworks": frameworks,
            "languages": languages,
            "package_manager": package_manager,
        },
        "commands": commands,
        "instructions": instructions,
        "risk_areas": risk_areas,
        "builder_hint": builder_hint,
    }
