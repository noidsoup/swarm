"""Deterministic validation helpers for swarm runs."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def _status_for_checks(checks: dict[str, dict]) -> str:
    statuses = [check["status"] for check in checks.values()]
    if any(status == "fail" for status in statuses):
        return "fail"
    if any(status == "warn" for status in statuses):
        return "warn"
    return "pass"


def _run_command(command: str, cwd: str) -> dict:
    try:
        completed = subprocess.run(
            command.split(),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        return {"command": command, "returncode": 127, "stdout": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired as exc:
        return {"command": command, "returncode": 124, "stdout": exc.stdout or "", "stderr": exc.stderr or "timed out"}

    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _get_changed_files(repo_root: str) -> list[str]:
    root = Path(repo_root)
    if not (root / ".git").exists():
        return []

    completed = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _extract_expected_files(build_summary: str) -> set[str]:
    matches = re.findall(r"[\w./-]+\.(?:py|ts|tsx|js|jsx|json|md|php)", build_summary)
    return {match for match in matches}


def run_preflight_validation(repo_root: str, context_pack: dict) -> dict:
    root = Path(repo_root)
    commands = context_pack.get("commands", {})
    checks = {
        "repo_root": {
            "status": "pass" if root.exists() and root.is_dir() else "fail",
            "details": {"repo_root": repo_root},
        },
        "commands": {
            "status": "pass" if commands else "warn",
            "details": {"commands": commands},
        },
    }
    return {"status": _status_for_checks(checks), "checks": checks}


def run_postflight_validation(repo_root: str, context_pack: dict, build_summary: str) -> dict:
    commands = context_pack.get("commands", {})
    checks: dict[str, dict] = {}

    expected_files = _extract_expected_files(build_summary)
    changed_files = _get_changed_files(repo_root)
    if not changed_files or not expected_files:
        checks["scope"] = {
            "status": "warn",
            "details": {"changed_files": changed_files, "expected_files": sorted(expected_files)},
        }
    else:
        unexpected_files = sorted(set(changed_files) - expected_files)
        checks["scope"] = {
            "status": "fail" if unexpected_files else "pass",
            "details": {
                "changed_files": changed_files,
                "expected_files": sorted(expected_files),
                "unexpected_files": unexpected_files,
            },
        }

    for label in ("test", "lint", "build"):
        command = commands.get(label)
        if not command:
            checks[label] = {"status": "warn", "details": {"message": f"No {label} command configured"}}
            continue
        result = _run_command(command, repo_root)
        checks[label] = {
            "status": "pass" if result["returncode"] == 0 else "fail",
            "details": result,
        }

    return {"status": _status_for_checks(checks), "checks": checks}


def summarize_validation_report(report: dict) -> str:
    failing = [name for name, check in report.get("checks", {}).items() if check.get("status") == "fail"]
    warnings = [name for name, check in report.get("checks", {}).items() if check.get("status") == "warn"]
    parts = [f"Validation status: {report.get('status', 'unknown')}."]
    if failing:
        parts.append(f"Failing checks: {', '.join(failing)}.")
    if warnings:
        parts.append(f"Warnings: {', '.join(warnings)}.")
    return " ".join(parts)
