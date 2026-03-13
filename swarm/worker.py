"""Background worker — pulls tasks from the Redis queue and runs the swarm.

Runs as: python -m swarm.worker
"""

from __future__ import annotations

import json
import ipaddress
import logging
import os
import signal
import subprocess
import threading
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
from swarm.task_models import TaskResult, TaskStatus, utcnow_iso
from swarm.validation import (
    run_postflight_validation,
    run_preflight_validation,
    summarize_validation_report,
)
from swarm.errors import PreflightError, PostflightError, RetryableError
from swarm.task_store import store

from dataclasses import dataclass, field as dataclass_field

POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL", "5"))
WORKSPACE = os.getenv("REPO_ROOT", "/workspace")
logger = logging.getLogger(__name__)

_shutdown_event = threading.Event()


@dataclass
class RunContext:
    """Carries state between pipeline steps inside _run_swarm."""

    task_id: str
    task: TaskResult
    cfg: object
    task_dir: str = ""
    artifact_paths: dict[str, str] = dataclass_field(default_factory=dict)
    context_pack: dict = dataclass_field(default_factory=dict)
    context_pack_json: str = ""
    retrieval_pack: dict = dataclass_field(default_factory=dict)
    retrieval_pack_json: str = ""
    adaptation_strategy: dict = dataclass_field(default_factory=dict)
    flow_adaptation_json: str = ""
    validation_report: dict = dataclass_field(default_factory=dict)
    latest_validation_status: str = "warn"
    retries: int = 0
    flow: object = None


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
        pass
    else:
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
        ):
            raise ValueError(f"Refusing private repo URL: {repo_url}")
        return

    import socket
    try:
        resolved = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return

    for _family, _type, _proto, _canonname, sockaddr in resolved:
        try:
            addr = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise ValueError(f"Refusing repo URL that resolves to private address: {repo_url} -> {sockaddr[0]}")


def _is_ollama_runner_startup_timeout(exc: Exception) -> bool:
    """Detect Ollama runner startup timeout failures that can be retried."""
    msg = str(exc).lower()
    return (
        "timed out waiting for llama runner to start" in msg
        or ("ollamaexception" in msg and "runner" in msg and "timed out" in msg)
    )


def _is_transient_error(exc: Exception) -> bool:
    """Detect transient errors that may succeed on retry."""
    if _is_ollama_runner_startup_timeout(exc):
        return True
    if isinstance(exc, RetryableError):
        return True
    msg = str(exc).lower()
    transient_markers = (
        "connection reset",
        "connection refused",
        "timed out",
        "timeout",
        "429",
        "503",
        "rate limit",
        "too many requests",
        "temporary failure",
    )
    return any(marker in msg for marker in transient_markers)


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
    return _execute_flow(task, cfg, context_pack_json, retrieval_pack_json)


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
    if not _is_transient_error(error):
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


def _workspace_step(ctx: RunContext) -> None:
    """Prepare workspace directory and artifact paths."""
    ctx.task_dir = _prepare_workspace(ctx.task_id, ctx.task.repo_url)
    os.makedirs(ctx.task_dir, exist_ok=True)
    ctx.cfg.repo_root = ctx.task_dir
    ctx.cfg.auto_commit = False
    ctx.task.artifacts_dir = ensure_artifact_dir(ctx.task_dir, ctx.task_id)
    ctx.artifact_paths = artifact_file_map(ctx.task_dir, ctx.task_id)
    append_event(
        ctx.artifact_paths["events"],
        make_event(ctx.task_id, "run_started", "running", {"builder": ctx.task.builder_type or "auto"}),
    )


def _context_step(ctx: RunContext) -> None:
    """Build context pack, adaptation strategy, and retrieval pack."""
    ctx.context_pack = build_context_pack(ctx.task_dir, ctx.task.feature, ctx.task.plan)
    with open(ctx.artifact_paths["context"], "w", encoding="utf-8") as f:
        json.dump(ctx.context_pack, f, indent=2)
    ctx.task.context_summary = summarize_context_pack(ctx.context_pack)
    ctx.context_pack_json = json.dumps(ctx.context_pack)
    append_event(
        ctx.artifact_paths["events"],
        make_event(ctx.task_id, "context_built", "pass", {"summary": ctx.task.context_summary}),
    )

    prior_signals = load_prior_run_signals(ctx.task_dir, ctx.task.feature, ctx.context_pack)
    ctx.adaptation_strategy = choose_adaptation_strategy(ctx.task.feature, ctx.context_pack, prior_signals)
    ctx.task.adaptation_summary = summarize_adaptation_strategy(ctx.adaptation_strategy)
    ctx.flow_adaptation_json = json.dumps(ctx.adaptation_strategy)
    with open(Path(ctx.artifact_paths["eval"]).with_name("adaptation.json"), "w", encoding="utf-8") as f:
        json.dump(ctx.adaptation_strategy, f, indent=2)
    append_event(
        ctx.artifact_paths["events"],
        make_event(ctx.task_id, "phase_completed", "pass", {"phase": "adaptation", "summary": ctx.task.adaptation_summary}),
    )

    retrieval_request = ctx.task.feature
    retrieval_biases = ctx.adaptation_strategy.get("retrieval_biases", [])
    if "tests" in retrieval_biases:
        retrieval_request = f"{retrieval_request} tests"
    if ctx.adaptation_strategy.get("builder_override"):
        ctx.task.builder_type = ctx.adaptation_strategy["builder_override"]

    ctx.retrieval_pack = build_retrieval_pack(ctx.task_dir, retrieval_request, ctx.context_pack)
    with open(ctx.artifact_paths["retrieval"], "w", encoding="utf-8") as f:
        json.dump(ctx.retrieval_pack, f, indent=2)
    ctx.task.retrieval_summary = summarize_retrieval_pack(ctx.retrieval_pack)
    ctx.retrieval_pack_json = json.dumps(ctx.retrieval_pack)
    append_event(
        ctx.artifact_paths["events"],
        make_event(ctx.task_id, "retrieval_built", "pass", {"summary": ctx.task.retrieval_summary}),
    )


def _preflight_step(ctx: RunContext) -> None:
    """Run preflight validation. Raises PreflightError on hard failure."""
    ctx.validation_report["preflight"] = run_preflight_validation(ctx.task_dir, ctx.context_pack)
    ctx.latest_validation_status = ctx.validation_report["preflight"]["status"]
    ctx.task.validation_summary = summarize_validation_report(ctx.validation_report["preflight"])
    with open(ctx.artifact_paths["validation"], "w", encoding="utf-8") as f:
        json.dump(ctx.validation_report, f, indent=2)
    append_event(
        ctx.artifact_paths["events"],
        make_event(
            ctx.task_id,
            "validation_completed",
            ctx.validation_report["preflight"]["status"],
            {"stage": "preflight", "summary": ctx.task.validation_summary},
        ),
    )
    store.update(ctx.task)

    if ctx.validation_report["preflight"]["status"] == "fail":
        ctx.task.failure_kind = "preflight_validation_failed"
        store.update(ctx.task)
        raise PreflightError("Preflight validation failed")


def _execute_step(ctx: RunContext) -> None:
    """Run the agent flow with retry/adaptation on transient failure."""
    try:
        ctx.flow = _call_execute_flow(ctx.task, ctx.cfg, ctx.context_pack_json, ctx.retrieval_pack_json)
    except Exception as first_error:
        ctx.flow, ctx.retries = _retry_with_adaptation(
            task=ctx.task,
            cfg=ctx.cfg,
            context_pack_json=ctx.context_pack_json,
            retrieval_pack_json=ctx.retrieval_pack_json,
            artifact_paths=ctx.artifact_paths,
            adaptation_strategy=ctx.adaptation_strategy,
            retries=ctx.retries,
            error=first_error,
        )
        _log(ctx.task_id, f"Adaptive retry succeeded with {ctx.cfg.worker_model}.")


def _postflight_step(ctx: RunContext) -> None:
    """Collect results, run postflight validation, raise PostflightError on failure."""
    task = store.get(ctx.task_id)
    task.status = TaskStatus.COMPLETED
    task.completed_at = utcnow_iso()
    task.build_summary = ctx.flow.state.build_summary[:5000]
    task.review_feedback = ctx.flow.state.review_feedback[:3000]
    task.quality_report = ctx.flow.state.quality_report[:5000]
    task.polish_report = ctx.flow.state.polish_report[:3000]
    task.artifacts_dir = getattr(ctx.flow.state, "run_artifacts_dir", task.artifacts_dir)
    ctx.task = task
    store.update(ctx.task)

    append_event(ctx.artifact_paths["events"], make_event(ctx.task_id, "phase_completed", "pass", {"phase": "build"}))
    append_event(
        ctx.artifact_paths["events"],
        make_event(
            ctx.task_id,
            "phase_completed",
            "pass",
            {"phase": "review", "review_iterations": getattr(ctx.flow.state, "review_iteration", 0)},
        ),
    )
    if ctx.flow.state.quality_report:
        append_event(ctx.artifact_paths["events"], make_event(ctx.task_id, "phase_completed", "pass", {"phase": "quality"}))
    if ctx.flow.state.polish_report:
        append_event(ctx.artifact_paths["events"], make_event(ctx.task_id, "phase_completed", "pass", {"phase": "polish"}))

    ctx.validation_report["postflight"] = run_postflight_validation(
        ctx.task_dir, ctx.context_pack, ctx.flow.state.build_summary
    )
    if ctx.adaptation_strategy.get("strict_validation") and ctx.validation_report["postflight"]["status"] == "warn":
        ctx.validation_report["postflight"]["status"] = "fail"
        ctx.validation_report["postflight"]["checks"]["strict_mode"] = {
            "status": "fail",
            "details": {"message": "Strict validation escalated warnings to failure"},
        }
    ctx.latest_validation_status = ctx.validation_report["postflight"]["status"]
    ctx.flow.state.validation_report_json = json.dumps(ctx.validation_report)
    ctx.flow.state.adaptation_report_json = ctx.flow_adaptation_json
    ctx.task.validation_summary = summarize_validation_report(ctx.validation_report["postflight"])
    with open(ctx.artifact_paths["validation"], "w", encoding="utf-8") as f:
        json.dump(ctx.validation_report, f, indent=2)
    append_event(
        ctx.artifact_paths["events"],
        make_event(
            ctx.task_id,
            "validation_completed",
            ctx.validation_report["postflight"]["status"],
            {"stage": "postflight", "summary": ctx.task.validation_summary},
        ),
    )

    if ctx.validation_report["postflight"]["status"] == "fail":
        ctx.task.failure_kind = "postflight_validation_failed"
        store.update(ctx.task)
        raise PostflightError("Postflight validation failed")


def _eval_step(ctx: RunContext) -> None:
    """Generate eval report and write lessons."""
    append_event(ctx.artifact_paths["events"], make_event(ctx.task_id, "run_completed", "complete"))
    eval_report = build_eval_report(
        task_id=ctx.task_id,
        events=read_events(ctx.artifact_paths["events"]),
        final_status="completed",
        validation_status=ctx.latest_validation_status,
        review_iterations=getattr(ctx.flow.state, "review_iteration", 0),
        retries=ctx.retries,
        failure_kind=ctx.task.failure_kind,
        builder=ctx.task.builder_type or "auto",
        repo_profile=",".join(ctx.context_pack.get("stack", {}).get("frameworks", [])[:2]),
        previous_reports=load_recent_eval_reports(ctx.task_dir, exclude_task_id=ctx.task_id),
    )
    with open(ctx.artifact_paths["eval"], "w", encoding="utf-8") as f:
        json.dump(eval_report, f, indent=2)
    ctx.task.eval_summary = summarize_eval_report(eval_report)
    ctx.task.lessons = eval_report.get("lessons", [])
    ctx.task.comparison = eval_report.get("comparison", {})
    ctx.flow.state.eval_report_json = json.dumps(eval_report)
    store.update(ctx.task)
    _write_lesson(ctx.task, eval_report)


def _run_swarm(task_id: str) -> None:
    task = store.get(task_id)
    if not task:
        return

    task.status = TaskStatus.RUNNING
    task.started_at = utcnow_iso()
    store.update(task)
    _log(task_id, f"Starting swarm for: {task.feature}")

    from swarm.config import cfg

    task_cfg = cfg.copy() if hasattr(cfg, "copy") else cfg
    ctx = RunContext(task_id=task_id, task=task, cfg=task_cfg)

    try:
        _workspace_step(ctx)
        _context_step(ctx)
        _preflight_step(ctx)
        _execute_step(ctx)
        _postflight_step(ctx)
        _eval_step(ctx)
        _log(task_id, "Swarm completed successfully.")

    except Exception as e:
        task = store.get(task_id)
        task.status = TaskStatus.FAILED
        task.completed_at = utcnow_iso()
        if not task.failure_kind:
            task.failure_kind = "execution_failed"
        task.error = f"{e}\n{traceback.format_exc()[-2000:]}"
        if ctx.artifact_paths:
            append_event(
                ctx.artifact_paths["events"],
                make_event(task_id, "run_failed", "failed", {"error": str(e), "failure_kind": task.failure_kind}),
            )
            eval_report = build_eval_report(
                task_id=task_id,
                events=read_events(ctx.artifact_paths["events"]),
                final_status="failed",
                validation_status=ctx.latest_validation_status,
                review_iterations=0,
                retries=ctx.retries,
                failure_kind=task.failure_kind,
                builder=task.builder_type or "auto",
                repo_profile=",".join(ctx.context_pack.get("stack", {}).get("frameworks", [])[:2]),
                previous_reports=load_recent_eval_reports(ctx.task_dir, exclude_task_id=task_id),
            )
            with open(ctx.artifact_paths["eval"], "w", encoding="utf-8") as f:
                json.dump(eval_report, f, indent=2)
            task.eval_summary = summarize_eval_report(eval_report)
            task.lessons = eval_report.get("lessons", [])
            task.comparison = eval_report.get("comparison", {})
            _write_lesson(task, eval_report)
        store.update(task)
        _log(task_id, f"Swarm failed: {e}")


def main() -> None:
    configure_logging()
    logger.info("Swarm worker started poll_interval=%s", POLL_INTERVAL)
    logger.info("Swarm worker workspace=%s", WORKSPACE)
    os.makedirs(WORKSPACE, exist_ok=True)

    def _handle_shutdown(signum, frame):
        logger.info("Received signal %s, shutting down after current task...", signum)
        _shutdown_event.set()

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    while not _shutdown_event.is_set():
        task_id = store.next_queued()
        if task_id:
            _run_swarm(task_id)
        else:
            _shutdown_event.wait(timeout=POLL_INTERVAL)

    logger.info("Worker shut down gracefully.")


if __name__ == "__main__":
    main()
