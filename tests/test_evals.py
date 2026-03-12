from __future__ import annotations

from pathlib import Path

from swarm.evals import (
    append_event,
    build_eval_report,
    make_event,
    read_events,
    summarize_eval_report,
)


def test_make_event_records_run_start() -> None:
    event = make_event("swarm-abc123", "run_started", "running", {"builder": "react_dev"})

    assert event["task_id"] == "swarm-abc123"
    assert event["event_type"] == "run_started"
    assert event["status"] == "running"
    assert event["metadata"]["builder"] == "react_dev"
    assert "timestamp" in event


def test_append_event_writes_jsonl_in_order(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"

    append_event(str(events_path), make_event("swarm-1", "run_started", "running"))
    append_event(str(events_path), make_event("swarm-1", "validation_completed", "pass"))

    events = read_events(str(events_path))

    assert [event["event_type"] for event in events] == ["run_started", "validation_completed"]


def test_build_eval_report_scores_run_with_validation_and_retries() -> None:
    report = build_eval_report(
        task_id="swarm-1",
        events=[
            make_event("swarm-1", "run_started", "running"),
            make_event("swarm-1", "retry_triggered", "warn"),
            make_event("swarm-1", "validation_completed", "pass"),
            make_event("swarm-1", "run_completed", "complete"),
        ],
        final_status="completed",
        validation_status="pass",
        review_iterations=2,
        retries=1,
        failure_kind="",
    )

    assert report["task_id"] == "swarm-1"
    assert report["score"] < 100
    assert report["score"] > 0
    assert report["inputs"]["retries"] == 1
    assert report["inputs"]["validation_status"] == "pass"


def test_build_eval_report_penalizes_hard_failures() -> None:
    report = build_eval_report(
        task_id="swarm-2",
        events=[make_event("swarm-2", "run_failed", "failed")],
        final_status="failed",
        validation_status="fail",
        review_iterations=0,
        retries=0,
        failure_kind="postflight_validation_failed",
    )

    assert report["score"] == 0
    assert "hard failure" in " ".join(report["reasons"]).lower()


def test_summarize_eval_report_mentions_score_and_status() -> None:
    summary = summarize_eval_report(
        {
            "task_id": "swarm-1",
            "final_status": "completed",
            "score": 84,
            "reasons": ["Validation passed", "One retry used"],
        }
    )

    assert "84" in summary
    assert "completed" in summary
    assert "validation passed" in summary.lower()
