"""Background worker — pulls tasks from the Redis queue and runs the swarm.

Runs as: python -m swarm.worker
"""

from __future__ import annotations

import json
import ipaddress
import logging
import os
import subprocess
import time
import traceback
from pathlib import Path
from urllib.parse import urlparse

from simplemem_client import SimpleMemClient, load_simplemem_settings
from swarm.adaptation import (
    choose_adaptation_strategy,
    load_prior_run_signals,
    max_retry_budget,
    summarize_adaptation_strategy,
)
from swarm.context_pack import build_context_pack, summarize_context_pack
from swarm.evals import (
    append_event,
    build_eval_report,
    load_recent_eval_reports,
    make_event,
    read_events,
    summarize_eval_report,
)
from swarm.logging_utils import configure_logging
from swarm.retrieval import build_retrieval_pack, summarize_retrieval_pack
from swarm.run_artifacts import artifact_file_map, ensure_artifact_dir
from swarm.task_models import TaskStatus, utcnow_iso
from swarm.validation import (
    run_postflight_validation,
    run_preflight_validation,
    summarize_validation_report,
)
from swarm.task_store import store


POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL", "5"))
WORKSPACE = os.getenv("REPO_ROOT", "/workspace")
logger = logging.getLogger(__name__)


def _log(task_id: str, msg: str) -> None:
    ts = utcnow_iso()
    line = f"[{ts}] {msg}"
    logger.info("task_id=%s %s", task_id, msg)
    store.append_log(task_id, line)


def _prepare_workspace(task_id: str, repo_url: str) -> str:
    """Clone or create a workspace directory for the task."""
    task_dir = os.path.join(WORKSPACE, task_id)
    os.makedirs(task_dir, exist_ok=True)

    if repo_url:
        _validate_repo_url(repo_url)
        _log(task_id, f"Cloning {repo_url}...")
        subprocess.run(
            ["git", "clone", "--depth=1", repo_url, task_dir],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        _log(task_id, "Clone complete.")
    return task_dir


def _validate_repo_url(repo_url: str) -> None:
    """Reject local/private clone targets and unsupported schemes."""
    ssh_host = None
    if repo_url.startswith("git@"):
        ssh_host = repo_url.split("@", 1)[1].split(":", 1)[0]
        scheme = "ssh"
        host = ssh_host
    else:
        parsed = urlparse(repo_url)
        scheme = parsed.scheme
        host = parsed.hostname

    if scheme not in {"https", "http", "ssh", "git"}:
        raise ValueError(f"Unsupported repo URL scheme: {repo_url}")
    if not host:
        raise ValueError(f"Invalid repo URL: {repo_url}")

    blocked_hosts = {"localhost", "127.0.0.1", "::1"}
    if host.lower() in blocked_hosts or host.lower().endswith(".local"):
        raise ValueError(f"Refusing local repo URL: {repo_url}")

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return

    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
    ):
        raise ValueError(f"Refusing private repo URL: {repo_url}")


def _is_ollama_runner_startup_timeout(exc: Exception) -> bool:
    """Detect Ollama runner startup timeout failures that can be retried."""
    msg = str(exc).lower()
    return (
        "timed out waiting for llama runner to start" in msg
        or ("ollamaexception" in msg and "runner" in msg and "timed out" in msg)
    )


def _write_lesson(task, report: dict) -> None:
    try:
        client = SimpleMemClient(load_simplemem_settings())
        client.add_lessons(report.get("lessons", []))
        client.add_lesson(
            (
                f"Swarm task finished with status={report.get('final_status')} "
                f"score={report.get('score')} failure_kind={task.failure_kind or 'none'}."
            ),
            {
                "type": "swarm_lesson",
                "builder": task.builder_type or "auto",
                "status": report.get("final_status"),
                "score": report.get("score"),
                "failure_kind": task.failure_kind or "",
            },
        )
    except Exception:
        logger.debug("Skipping lesson write-back", exc_info=True)


def _execute_flow(task, cfg, context_pack_json: str, retrieval_pack_json: str):
    """Build and execute a worker flow for a queued task."""
    _log(task.task_id, "Importing WorkerSwarmFlow...")
    from swarm.flow import WorkerSwarmFlow

    flow = WorkerSwarmFlow(
        plan=task.plan or task.feature,
        feature_request=task.feature,
        builder_type=task.builder_type,
    )
    if context_pack_json:
        flow.state.context_pack_json = context_pack_json
    if retrieval_pack_json:
        flow.state.retrieval_pack_json = retrieval_pack_json
    flow.state.run_artifacts_dir = task.artifacts_dir

    _log(task.task_id, "Running agent pipeline...")
    flow.kickoff()
    return flow


def _call_execute_flow(task, cfg, context_pack_json: str, retrieval_pack_json: str):
    try:
        return _execute_flow(task, cfg, context_pack_json, retrieval_pack_json)
    except TypeError:
        return _execute_flow(task, cfg)


def _retry_with_adaptation(
    *,
    task,
    cfg,
    context_pack_json: str,
    retrieval_pack_json: str,
    artifact_paths: dict[str, str],
    adaptation_strategy: dict,
    retries: int,
    error: Exception,
):
    if not _is_ollama_runner_startup_timeout(error):
        raise error

    retry_budget = min(
        max_retry_budget(adaptation_strategy),
        int(getattr(cfg, "adaptation_max_retries", 1)),
    )
    fallback_model = adaptation_strategy.get("fallback_model", "") or os.getenv(
        "WORKER_FALLBACK_MODEL",
        "ollama/gemma3:4b",
    )
    if retry_budget == 0 and fallback_model and fallback_model != cfg.worker_model:
        retry_budget = 1
    if retries >= retry_budget or not fallback_model or fallback_model == cfg.worker_model:
        raise error

    append_event(
        artifact_paths["events"],
        make_event(
            task.task_id,
            "retry_triggered",
            "warn",
            {"reason": "ollama_runner_startup_timeout", "fallback_model": fallback_model},
        ),
    )
    _log(
        task.task_id,
        f"Ollama runner startup timed out on {cfg.worker_model}; retrying with fallback model {fallback_model}.",
    )
    cfg.worker_model = fallback_model
    return _call_execute_flow(task, cfg, context_pack_json, retrieval_pack_json), retries + 1


def _run_swarm(task_id: str) -> None:
    task = store.get(task_id)
    if not task:
        return

    artifact_paths: dict[str, str] = {}
    retries = 0
    latest_validation_status = "warn"
    task.status = TaskStatus.RUNNING
    task.started_at = utcnow_iso()
    store.update(task)

    _log(task_id, f"Starting swarm for: {task.feature}")

    try:
        task_dir = _prepare_workspace(task_id, task.repo_url)
        os.makedirs(task_dir, exist_ok=True)

        from swarm.config import cfg
        cfg.repo_root = task_dir
        cfg.auto_commit = False
        task.artifacts_dir = ensure_artifact_dir(task_dir, task_id)
        artifact_paths = artifact_file_map(task_dir, task_id)
        append_event(
            artifact_paths["events"],
            make_event(task_id, "run_started", "running", {"builder": task.builder_type or "auto"}),
        )
        context_pack = build_context_pack(task_dir, task.feature, task.plan)
        with open(artifact_paths["context"], "w", encoding="utf-8") as f:
            json.dump(context_pack, f, indent=2)
        task.context_summary = summarize_context_pack(context_pack)
        context_pack_json = json.dumps(context_pack)
        append_event(
            artifact_paths["events"],
            make_event(task_id, "context_built", "pass", {"summary": task.context_summary}),
        )
        prior_signals = load_prior_run_signals(task_dir, task.feature, context_pack)
        adaptation_strategy = choose_adaptation_strategy(task.feature, context_pack, prior_signals)
        task.adaptation_summary = summarize_adaptation_strategy(adaptation_strategy)
        flow_adaptation_json = json.dumps(adaptation_strategy)
        with open(Path(artifact_paths["eval"]).with_name("adaptation.json"), "w", encoding="utf-8") as f:
            json.dump(adaptation_strategy, f, indent=2)
        append_event(
            artifact_paths["events"],
            make_event(task_id, "phase_completed", "pass", {"phase": "adaptation", "summary": task.adaptation_summary}),
        )

        retrieval_request = task.feature
        retrieval_biases = adaptation_strategy.get("retrieval_biases", [])
        if "tests" in retrieval_biases:
            retrieval_request = f"{retrieval_request} tests"
        if adaptation_strategy.get("builder_override"):
            task.builder_type = adaptation_strategy["builder_override"]

        retrieval_pack = build_retrieval_pack(task_dir, retrieval_request, context_pack)
        with open(artifact_paths["retrieval"], "w", encoding="utf-8") as f:
            json.dump(retrieval_pack, f, indent=2)
        task.retrieval_summary = summarize_retrieval_pack(retrieval_pack)
        retrieval_pack_json = json.dumps(retrieval_pack)
        append_event(
            artifact_paths["events"],
            make_event(task_id, "retrieval_built", "pass", {"summary": task.retrieval_summary}),
        )
        validation_report = {"preflight": run_preflight_validation(task_dir, context_pack)}
        latest_validation_status = validation_report["preflight"]["status"]
        task.validation_summary = summarize_validation_report(validation_report["preflight"])
        with open(artifact_paths["validation"], "w", encoding="utf-8") as f:
            json.dump(validation_report, f, indent=2)
        append_event(
            artifact_paths["events"],
            make_event(
                task_id,
                "validation_completed",
                validation_report["preflight"]["status"],
                {"stage": "preflight", "summary": task.validation_summary},
            ),
        )
        store.update(task)

        if validation_report["preflight"]["status"] == "fail":
            task.failure_kind = "preflight_validation_failed"
            store.update(task)
            raise RuntimeError("Preflight validation failed")

        try:
            flow = _call_execute_flow(task, cfg, context_pack_json, retrieval_pack_json)
        except Exception as first_error:
            flow, retries = _retry_with_adaptation(
                task=task,
                cfg=cfg,
                context_pack_json=context_pack_json,
                retrieval_pack_json=retrieval_pack_json,
                artifact_paths=artifact_paths,
                adaptation_strategy=adaptation_strategy,
                retries=retries,
                error=first_error,
            )
            _log(task_id, f"Adaptive retry succeeded with {cfg.worker_model}.")

        task = store.get(task_id)
        task.status = TaskStatus.COMPLETED
        task.completed_at = utcnow_iso()
        task.build_summary = flow.state.build_summary[:5000]
        task.review_feedback = flow.state.review_feedback[:3000]
        task.quality_report = flow.state.quality_report[:5000]
        task.polish_report = flow.state.polish_report[:3000]
        task.artifacts_dir = getattr(flow.state, "run_artifacts_dir", task.artifacts_dir)
        append_event(
            artifact_paths["events"],
            make_event(task_id, "phase_completed", "pass", {"phase": "build"}),
        )
        append_event(
            artifact_paths["events"],
            make_event(
                task_id,
                "phase_completed",
                "pass",
                {"phase": "review", "review_iterations": getattr(flow.state, "review_iteration", 0)},
            ),
        )
        if flow.state.quality_report:
            append_event(
                artifact_paths["events"],
                make_event(task_id, "phase_completed", "pass", {"phase": "quality"}),
            )
        if flow.state.polish_report:
            append_event(
                artifact_paths["events"],
                make_event(task_id, "phase_completed", "pass", {"phase": "polish"}),
            )
        validation_report["postflight"] = run_postflight_validation(task_dir, context_pack, flow.state.build_summary)
        if adaptation_strategy.get("strict_validation") and validation_report["postflight"]["status"] == "warn":
            validation_report["postflight"]["status"] = "fail"
            validation_report["postflight"]["checks"]["strict_mode"] = {
                "status": "fail",
                "details": {"message": "Strict validation escalated warnings to failure"},
            }
        latest_validation_status = validation_report["postflight"]["status"]
        flow.state.validation_report_json = json.dumps(validation_report)
        flow.state.adaptation_report_json = flow_adaptation_json
        task.validation_summary = summarize_validation_report(validation_report["postflight"])
        with open(artifact_paths["validation"], "w", encoding="utf-8") as f:
            json.dump(validation_report, f, indent=2)
        append_event(
            artifact_paths["events"],
            make_event(
                task_id,
                "validation_completed",
                validation_report["postflight"]["status"],
                {"stage": "postflight", "summary": task.validation_summary},
            ),
        )

        if validation_report["postflight"]["status"] == "fail":
            task.failure_kind = "postflight_validation_failed"
            store.update(task)
            raise RuntimeError("Postflight validation failed")

        append_event(artifact_paths["events"], make_event(task_id, "run_completed", "complete"))
        eval_report = build_eval_report(
            task_id=task_id,
            events=read_events(artifact_paths["events"]),
            final_status="completed",
            validation_status=latest_validation_status,
            review_iterations=getattr(flow.state, "review_iteration", 0),
            retries=retries,
            failure_kind=task.failure_kind,
            builder=task.builder_type or "auto",
            repo_profile=",".join(context_pack.get("stack", {}).get("frameworks", [])[:2]),
            previous_reports=load_recent_eval_reports(task_dir, exclude_task_id=task_id),
        )
        with open(artifact_paths["eval"], "w", encoding="utf-8") as f:
            json.dump(eval_report, f, indent=2)
        task.eval_summary = summarize_eval_report(eval_report)
        flow.state.eval_report_json = json.dumps(eval_report)
        store.update(task)
        _write_lesson(task, eval_report)

        _log(task_id, "Swarm completed successfully.")

    except Exception as e:
        task = store.get(task_id)
        task.status = TaskStatus.FAILED
        task.completed_at = utcnow_iso()
        if not task.failure_kind:
            task.failure_kind = "execution_failed"
        task.error = f"{e}\n{traceback.format_exc()[-2000:]}"
        if artifact_paths:
            append_event(
                artifact_paths["events"],
                make_event(task_id, "run_failed", "failed", {"error": str(e), "failure_kind": task.failure_kind}),
            )
            eval_report = build_eval_report(
                task_id=task_id,
                events=read_events(artifact_paths["events"]),
                final_status="failed",
                validation_status=latest_validation_status,
                review_iterations=0,
                retries=retries,
                failure_kind=task.failure_kind,
                builder=task.builder_type or "auto",
                repo_profile=",".join(context_pack.get("stack", {}).get("frameworks", [])[:2]),
                previous_reports=load_recent_eval_reports(task_dir, exclude_task_id=task_id),
            )
            with open(artifact_paths["eval"], "w", encoding="utf-8") as f:
                json.dump(eval_report, f, indent=2)
            task.eval_summary = summarize_eval_report(eval_report)
            _write_lesson(task, eval_report)
        store.update(task)
        _log(task_id, f"Swarm failed: {e}")


def main() -> None:
    configure_logging()
    logger.info("Swarm worker started poll_interval=%s", POLL_INTERVAL)
    logger.info("Swarm worker workspace=%s", WORKSPACE)
    os.makedirs(WORKSPACE, exist_ok=True)

    while True:
        task_id = store.next_queued()
        if task_id:
            _run_swarm(task_id)
        else:
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
