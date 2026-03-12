from __future__ import annotations

import json
from pathlib import Path

from simplemem_client import SimpleMemClient, SimpleMemSettings
from swarm.adaptation import load_prior_run_signals
from swarm.evals import build_eval_report, compare_run_outcomes


def _write_eval(root: Path, run_id: str, payload: dict) -> None:
    run_dir = root / ".swarm" / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "eval.json").write_text(json.dumps(payload), encoding="utf-8")


def test_build_eval_report_extracts_compact_lessons() -> None:
    report = build_eval_report(
        task_id="swarm-1",
        events=[],
        final_status="failed",
        validation_status="fail",
        review_iterations=0,
        retries=1,
        failure_kind="missing_tests",
        builder="react_dev",
        repo_profile="nextjs",
    )

    lessons = report["lessons"]

    assert 1 <= len(lessons) <= 3
    assert any(lesson["kind"] == "negative" for lesson in lessons)
    assert any("react_dev" in lesson["text"] for lesson in lessons)
    assert any(lesson["confidence"] >= 1 for lesson in lessons)


def test_compare_run_outcomes_detects_improvement_against_recent_runs() -> None:
    comparison = compare_run_outcomes(
        current_report={
            "score": 88,
            "inputs": {"retries": 0, "validation_status": "pass"},
        },
        previous_reports=[
            {"score": 60, "inputs": {"retries": 2, "validation_status": "warn"}},
            {"score": 70, "inputs": {"retries": 1, "validation_status": "pass"}},
        ],
    )

    assert comparison["improved"] is True
    assert comparison["score_delta"] > 0
    assert comparison["retry_delta"] < 0
    assert comparison["validation_delta"] >= 0


def test_load_prior_run_signals_promotes_repeated_lessons_to_trusted_signals(tmp_path: Path) -> None:
    _write_eval(
        tmp_path,
        "swarm-one",
        {
            "final_status": "failed",
            "score": 20,
            "inputs": {"validation_status": "fail", "failure_kind": "missing_tests"},
            "lessons": [
                {"key": "negative:missing_tests", "kind": "negative", "confidence": 1, "text": "Add tests"}
            ],
        },
    )
    _write_eval(
        tmp_path,
        "swarm-two",
        {
            "final_status": "failed",
            "score": 30,
            "inputs": {"validation_status": "fail", "failure_kind": "missing_tests"},
            "lessons": [
                {"key": "negative:missing_tests", "kind": "negative", "confidence": 1, "text": "Add tests"}
            ],
        },
    )

    signals = load_prior_run_signals(
        str(tmp_path),
        "Fix auth regression",
        {"builder_hint": "python_dev", "stack": {"frameworks": ["python"]}},
    )

    assert signals["trusted_negative_lessons"] == ["negative:missing_tests"]
    assert signals["lesson_confidence"]["negative:missing_tests"] == 2


def test_simplemem_add_lessons_writes_local_memories_with_metadata(tmp_path: Path) -> None:
    client = SimpleMemClient(
        SimpleMemSettings(
            enabled=True,
            backend="local",
            mcp_url="",
            token=None,
            user_id=None,
            namespace="swarm",
            local_dir=str(tmp_path / "simplemem"),
            dry_run=False,
        )
    )

    client.add_lessons(
        [
            {
                "key": "positive:react_clean_run",
                "text": "When using react_dev on nextjs repos, clean runs are common.",
                "kind": "positive",
                "confidence": 2,
                "metadata": {"builder": "react_dev", "api_key": "secret"},
            }
        ]
    )

    memories = json.loads((tmp_path / "simplemem" / "memories.json").read_text(encoding="utf-8"))

    assert len(memories) == 1
    assert memories[0]["metadata"]["key"] == "positive:react_clean_run"
    assert memories[0]["metadata"]["confidence"] == 2
    assert memories[0]["metadata"]["api_key"] == "[REDACTED]"
