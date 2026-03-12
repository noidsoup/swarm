"""Structured evaluation ledger helpers for swarm runs."""

from __future__ import annotations

import json
from pathlib import Path

from swarm.task_models import utcnow_iso


def make_event(task_id: str, event_type: str, status: str, metadata: dict | None = None) -> dict:
    return {
        "task_id": task_id,
        "timestamp": utcnow_iso(),
        "event_type": event_type,
        "status": status,
        "metadata": metadata or {},
    }


def append_event(events_path: str, event: dict) -> None:
    path = Path(events_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def read_events(events_path: str) -> list[dict]:
    path = Path(events_path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_eval_report(
    task_id: str,
    events: list[dict],
    final_status: str,
    validation_status: str,
    review_iterations: int,
    retries: int,
    failure_kind: str,
) -> dict:
    reasons: list[str] = []
    score = 100

    if final_status != "completed":
        score -= 60
        reasons.append("Run did not complete successfully")
    if validation_status == "fail":
        score -= 50
        reasons.append("Hard failure in validation")
    elif validation_status == "warn":
        score -= 15
        reasons.append("Validation completed with warnings")
    elif validation_status == "pass":
        reasons.append("Validation passed")

    if review_iterations:
        penalty = min(review_iterations * 5, 20)
        score -= penalty
        reasons.append(f"Review iterations used: {review_iterations}")

    if retries:
        penalty = min(retries * 10, 20)
        score -= penalty
        reasons.append(f"Retries used: {retries}")

    if failure_kind:
        reasons.append(f"Failure kind: {failure_kind}")

    score = max(score, 0)

    return {
        "task_id": task_id,
        "final_status": final_status,
        "score": score,
        "reasons": reasons,
        "inputs": {
            "validation_status": validation_status,
            "review_iterations": review_iterations,
            "retries": retries,
            "failure_kind": failure_kind,
            "event_count": len(events),
        },
    }


def summarize_eval_report(report: dict) -> str:
    reasons = "; ".join(report.get("reasons", [])[:3]) or "No reasons recorded"
    return (
        f"Eval status: {report.get('final_status', 'unknown')}. "
        f"Score: {report.get('score', 0)}. "
        f"{reasons}."
    )
