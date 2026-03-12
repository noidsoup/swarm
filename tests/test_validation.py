from __future__ import annotations

from pathlib import Path

from swarm.validation import (
    run_postflight_validation,
    run_preflight_validation,
    summarize_validation_report,
)


def test_run_preflight_validation_passes_for_known_python_repo(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    report = run_preflight_validation(
        str(tmp_path),
        {
            "builder_hint": "python_dev",
            "commands": {"test": "pytest", "lint": "ruff check"},
        },
    )

    assert report["status"] == "pass"
    assert report["checks"]["repo_root"]["status"] == "pass"
    assert report["checks"]["commands"]["status"] == "pass"


def test_run_preflight_validation_warns_when_commands_unknown(tmp_path: Path) -> None:
    report = run_preflight_validation(
        str(tmp_path),
        {"builder_hint": "python_dev", "commands": {}},
    )

    assert report["status"] == "warn"
    assert report["checks"]["commands"]["status"] == "warn"


def test_run_postflight_validation_flags_changed_files_outside_expected_scope(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "swarm.validation._get_changed_files",
        lambda repo_root: ["src/expected.py", "secrets.env"],
    )
    monkeypatch.setattr(
        "swarm.validation._run_command",
        lambda command, cwd: {"command": command, "returncode": 0, "stdout": "", "stderr": ""},
    )

    report = run_postflight_validation(
        str(tmp_path),
        {"commands": {"test": "pytest", "lint": "ruff check"}},
        "Modified files: src/expected.py",
    )

    assert report["status"] == "fail"
    assert report["checks"]["scope"]["status"] == "fail"
    assert "secrets.env" in report["checks"]["scope"]["details"]["unexpected_files"]


def test_run_postflight_validation_records_command_failures_as_fail(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("swarm.validation._get_changed_files", lambda repo_root: ["src/app.py"])

    def fake_run(command: str, cwd: str) -> dict:
        return {
            "command": command,
            "returncode": 1 if command == "pytest" else 0,
            "stdout": "",
            "stderr": "boom" if command == "pytest" else "",
        }

    monkeypatch.setattr("swarm.validation._run_command", fake_run)

    report = run_postflight_validation(
        str(tmp_path),
        {"commands": {"test": "pytest", "lint": "ruff check"}},
        "Updated files: src/app.py",
    )

    assert report["status"] == "fail"
    assert report["checks"]["test"]["status"] == "fail"
    assert report["checks"]["lint"]["status"] == "pass"


def test_summarize_validation_report_mentions_status_and_failures() -> None:
    summary = summarize_validation_report(
        {
            "status": "fail",
            "checks": {
                "scope": {"status": "fail", "details": {"unexpected_files": ["oops.py"]}},
                "test": {"status": "pass", "details": {}},
            },
        }
    )

    assert "fail" in summary.lower()
    assert "scope" in summary.lower()
