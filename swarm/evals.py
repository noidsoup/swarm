"""Structured evaluation ledger helpers for swarm runs."""

from __future__ import annotations

import json
from pathlib import Path

from swarm.task_models import utcnow_iso


def load_recent_eval_reports(repo_root: str, *, limit: int = 5, exclude_task_id: str = "") -> list[dict]:
    runs_dir = Path(repo_root) / ".swarm" / "runs"
    if not runs_dir.exists():
        return []

    eval_paths = sorted(
        runs_dir.glob("*/eval.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    reports: list[dict] = []
    for eval_path in eval_paths:
        try:
            report = json.loads(eval_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if exclude_task_id and report.get("task_id") == exclude_task_id:
            continue
        reports.append(report)
        if len(reports) >= limit:
            break
    return reports


def _validation_rank(status: str) -> int:
    return {"fail": 0, "warn": 1, "pass": 2}.get(status, 0)


def compare_run_outcomes(current_report: dict, previous_reports: list[dict]) -> dict:
    if not previous_reports:
        return {
            "baseline_count": 0,
            "score_delta": 0.0,
            "retry_delta": 0.0,
            "validation_delta": 0.0,
            "improved": False,
        }

    score_baseline = sum(float(report.get("score", 0)) for report in previous_reports) / len(previous_reports)
    retry_baseline = sum(float(report.get("inputs", {}).get("retries", 0)) for report in previous_reports) / len(previous_reports)
    validation_baseline = sum(
        _validation_rank(str(report.get("inputs", {}).get("validation_status", "")))
        for report in previous_reports
    ) / len(previous_reports)

    current_score = float(current_report.get("score", 0))
    current_retries = float(current_report.get("inputs", {}).get("retries", 0))
    current_validation = float(
        _validation_rank(str(current_report.get("inputs", {}).get("validation_status", "")))
    )

    score_delta = current_score - score_baseline
    retry_delta = current_retries - retry_baseline
    validation_delta = current_validation - validation_baseline

    return {
        "baseline_count": len(previous_reports),
        "score_delta": round(score_delta, 2),
        "retry_delta": round(retry_delta, 2),
        "validation_delta": round(validation_delta, 2),
        "improved": score_delta > 0 and retry_delta <= 0 and validation_delta >= 0,
    }


def _extract_lessons(
    *,
    final_status: str,
    validation_status: str,
    retries: int,
    failure_kind: str,
    builder: str,
    repo_profile: str,
) -> list[dict]:
    lessons: list[dict] = []
    lesson_keys: set[str] = set()
    builder_name = builder or "auto"
    repo_name = repo_profile or "unknown"

    def add_lesson(key: str, kind: str, text: str) -> None:
        if key in lesson_keys or len(lessons) >= 3:
            return
        lesson_keys.add(key)
        lessons.append(
            {
                "key": key,
                "kind": kind,
                "confidence": 1,
                "text": text,
            }
        )

    if failure_kind:
        add_lesson(
            f"negative:{failure_kind}",
            "negative",
            f"When using {builder_name} on {repo_name} work, watch for failure kind `{failure_kind}`.",
        )
    if validation_status in {"fail", "warn"}:
        add_lesson(
            f"negative:validation:{validation_status}",
            "negative",
            f"{builder_name} often needs stronger validation on {repo_name} tasks when validation={validation_status}.",
        )
    if final_status == "completed" and validation_status == "pass" and retries == 0:
        add_lesson(
            f"positive:clean_run:{builder_name}:{repo_name}",
            "positive",
            f"When using {builder_name} on {repo_name} repos, clean runs without retries are achievable.",
        )
    elif final_status == "completed" and retries > 0:
        add_lesson(
            f"positive:recovery:{builder_name}:{repo_name}",
            "positive",
            f"{builder_name} can recover on {repo_name} tasks after retries, so fallback strategies are worth keeping.",
        )

    return lessons


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
    builder: str = "",
    repo_profile: str = "",
    previous_reports: list[dict] | None = None,
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

    report = {
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
            "builder": builder,
            "repo_profile": repo_profile,
        },
    }
    report["lessons"] = _extract_lessons(
        final_status=final_status,
        validation_status=validation_status,
        retries=retries,
        failure_kind=failure_kind,
        builder=builder,
        repo_profile=repo_profile,
    )
    report["comparison"] = compare_run_outcomes(report, previous_reports or [])

    return report


def summarize_eval_report(report: dict) -> str:
    reasons = "; ".join(report.get("reasons", [])[:3]) or "No reasons recorded"
    return (
        f"Eval status: {report.get('final_status', 'unknown')}. "
        f"Score: {report.get('score', 0)}. "
        f"{reasons}."
    )
