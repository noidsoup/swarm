"""MCP server for the AI Dev Swarm.

Exposes tools to Cursor so it can act as the commander:
  - run_swarm: execute worker pipeline with a plan
  - run_project_task: execute a task against a registered project
  - swarm_status: check run results
  - project management tools: list/add/remove/spawn
  - list_agents: show available worker agents

Run directly:  python swarm/mcp_server.py
Cursor config:  "command": "python", "args": ["path/to/swarm/mcp_server.py"]
"""

from __future__ import annotations

import json
import os
import sys
import threading
import traceback
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from simplemem_client import SimpleMemClient, load_simplemem_settings
from swarm.context_pack import build_context_pack, summarize_context_pack
from swarm.evals import (
    append_event,
    build_eval_report,
    make_event,
    read_events,
    summarize_eval_report,
)
from swarm.retrieval import build_retrieval_pack, summarize_retrieval_pack
from swarm.run_artifacts import artifact_file_map, ensure_artifact_dir
from swarm.dispatch import Dispatcher
from swarm.projects import ProjectRegistry, spawn_project_from_template
from swarm.task_models import new_task_id, utcnow_iso

_swarm_root = str(Path(__file__).resolve().parent.parent)
if _swarm_root not in sys.path:
    sys.path.insert(0, _swarm_root)

mcp = FastMCP("ai-dev-swarm")

_last_result: dict | None = None
_last_run_id: str | None = None
_runs: dict[str, dict] = {}
_runs_lock = threading.Lock()
_projects = ProjectRegistry()


def _update_run(run_id: str, **updates) -> None:
    with _runs_lock:
        current = _runs.get(run_id, {})
        current.update(updates)
        _runs[run_id] = current


def _write_lesson(result: dict, failure_kind: str = "") -> None:
    try:
        client = SimpleMemClient(load_simplemem_settings())
        client.add_lesson(
            (
                f"MCP swarm run finished with status={result.get('status')} "
                f"score={result.get('score', 0)} failure_kind={failure_kind or 'none'}."
            ),
            {
                "type": "swarm_lesson",
                "builder": result.get("builder", "auto"),
                "status": result.get("status", ""),
                "score": result.get("score", 0),
                "failure_kind": failure_kind,
            },
        )
    except Exception:
        pass


def _execute_swarm_run(
    run_id: str,
    plan: str,
    feature_name: str,
    builder_type: str,
    repo_path: str,
    repo_url: str,
    execution_mode: str,
) -> None:
    global _last_result

    from swarm.config import cfg

    cfg.repo_root = repo_path or os.getcwd()
    cfg.auto_commit = False
    artifacts_dir = ensure_artifact_dir(cfg.repo_root, run_id)
    context_pack = build_context_pack(cfg.repo_root, feature_name, plan)
    artifact_paths = artifact_file_map(cfg.repo_root, run_id)
    append_event(
        artifact_paths["events"],
        make_event(run_id, "run_started", "running", {"builder": builder_type or "auto"}),
    )
    with open(artifact_paths["context"], "w", encoding="utf-8") as f:
        json.dump(context_pack, f, indent=2)
    context_summary = summarize_context_pack(context_pack)
    append_event(
        artifact_paths["events"],
        make_event(run_id, "context_built", "pass", {"summary": context_summary}),
    )
    retrieval_pack = build_retrieval_pack(cfg.repo_root, feature_name, context_pack)
    with open(artifact_paths["retrieval"], "w", encoding="utf-8") as f:
        json.dump(retrieval_pack, f, indent=2)
    retrieval_summary = summarize_retrieval_pack(retrieval_pack)
    append_event(
        artifact_paths["events"],
        make_event(run_id, "retrieval_built", "pass", {"summary": retrieval_summary}),
    )
    try:
        dispatcher = Dispatcher(cfg)
        result = dispatcher.dispatch(
            plan=plan,
            feature_name=feature_name,
            builder_type=builder_type,
            repo_path=repo_path,
            repo_url=repo_url,
            execution_mode=execution_mode,
        )
        result.update(
            {
                "status": "complete",
                "task_id": run_id,
                "artifacts_dir": artifacts_dir,
                "context_summary": context_summary,
                "retrieval_summary": retrieval_summary,
                "completed_at": result.get("completed_at") or utcnow_iso(),
            }
        )
        append_event(artifact_paths["events"], make_event(run_id, "phase_completed", "pass", {"phase": "dispatch"}))
        append_event(
            artifact_paths["events"],
            make_event(
                run_id,
                "phase_completed",
                "pass",
                {"phase": "result", "review_iterations": result.get("review_iterations", 0)},
            ),
        )
        if result.get("quality_report"):
            append_event(artifact_paths["events"], make_event(run_id, "phase_completed", "pass", {"phase": "quality"}))
        if result.get("polish_report"):
            append_event(artifact_paths["events"], make_event(run_id, "phase_completed", "pass", {"phase": "polish"}))
        append_event(artifact_paths["events"], make_event(run_id, "run_completed", "complete"))
        eval_report = build_eval_report(
            task_id=run_id,
            events=read_events(artifact_paths["events"]),
            final_status="completed",
            validation_status="warn",
            review_iterations=result.get("review_iterations", 0),
            retries=0,
            failure_kind="",
        )
        with open(artifact_paths["eval"], "w", encoding="utf-8") as f:
            json.dump(eval_report, f, indent=2)

        result.update(
            {
                "eval_summary": summarize_eval_report(eval_report),
                "score": eval_report["score"],
            }
        )
        _last_result = result
        _update_run(run_id, **result)
        _write_lesson(result)
    except Exception as e:
        append_event(artifact_paths["events"], make_event(run_id, "run_failed", "failed", {"error": str(e)}))
        eval_report = build_eval_report(
            task_id=run_id,
            events=read_events(artifact_paths["events"]),
            final_status="failed",
            validation_status="warn",
            review_iterations=0,
            retries=0,
            failure_kind="execution_failed",
        )
        with open(artifact_paths["eval"], "w", encoding="utf-8") as f:
            json.dump(eval_report, f, indent=2)
        error_result = {
            "status": "error",
            "task_id": run_id,
            "error": str(e),
            "eval_summary": summarize_eval_report(eval_report),
            "score": eval_report["score"],
            "traceback": traceback.format_exc()[-2000:],
            "completed_at": utcnow_iso(),
        }
        _last_result = error_result
        _update_run(run_id, **error_result)
        _write_lesson(error_result, failure_kind="execution_failed")


@mcp.tool()
def run_swarm(
    plan: str,
    feature_name: str = "",
    builder_type: str = "",
    repo_path: str = "",
    repo_url: str = "",
    execution_mode: str = "",
) -> str:
    """Start the worker swarm pipeline in the background.

    Cursor acts as commander (architect + judge). This tool runs the
    worker agents: Build > Review Loop > Quality Gates > Polish.

    Args:
        plan: The implementation plan (markdown). Be specific with file
              paths and step-by-step instructions.
        feature_name: Short name for the feature (used for branch naming).
        builder_type: Force a specific builder: "python_dev", "react_dev",
                      "wordpress_dev", or "shopify_dev". Leave empty to auto-detect from plan.
        repo_path: Absolute path to the target repo. Defaults to cwd.
        repo_url: Remote git URL (primarily for ollama mode workers).
        execution_mode: local | ollama | cursor. Defaults to DEFAULT_EXECUTION_MODE.

    Returns:
        JSON with a task_id and initial running status. Poll `swarm_status`
        with that task_id to retrieve progress and final results.
    """
    global _last_run_id, _last_result
    from swarm.config import cfg

    run_id = new_task_id()
    _last_run_id = run_id
    mode = (execution_mode or cfg.default_execution_mode or "local").lower()
    initial_result = {
        "status": "running",
        "task_id": run_id,
        "feature_name": feature_name,
        "builder_type": builder_type or "auto",
        "repo_path": repo_path or os.getcwd(),
        "repo_url": repo_url,
        "execution_mode": mode,
        "artifacts_dir": ensure_artifact_dir(repo_path or os.getcwd(), run_id),
        "context_summary": summarize_context_pack(build_context_pack(repo_path or os.getcwd(), feature_name, plan)),
        "retrieval_summary": "",
        "started_at": utcnow_iso(),
    }
    _last_result = initial_result
    _update_run(run_id, **initial_result)

    thread = threading.Thread(
        target=_execute_swarm_run,
        args=(run_id, plan, feature_name, builder_type, repo_path, repo_url, mode),
        daemon=True,
    )
    thread.start()
    return json.dumps(initial_result, indent=2)


@mcp.tool()
def list_projects() -> str:
    """List registered projects for multi-project orchestration."""
    return json.dumps(_projects.list_projects(), indent=2)


@mcp.tool()
def add_project(
    name: str,
    repo_path: str = "",
    repo_url: str = "",
    builder_type: str = "",
    execution_mode: str = "",
    active: bool = True,
) -> str:
    """Register or update a project in the local project registry."""
    record = _projects.add_project(
        name=name,
        repo_path=repo_path,
        repo_url=repo_url,
        builder_type=builder_type,
        execution_mode=execution_mode,
        active=active,
    )
    return json.dumps(record.__dict__, indent=2)


@mcp.tool()
def remove_project(name: str) -> str:
    """Remove a project from the local project registry."""
    removed = _projects.remove_project(name)
    return json.dumps({"name": name, "removed": removed}, indent=2)


@mcp.tool()
def run_project_task(
    project_name: str,
    plan: str,
    feature_name: str = "",
) -> str:
    """Run a task using a project's defaults (repo/builder/execution mode)."""
    project = _projects.get_project(project_name)
    if not project:
        return json.dumps({"status": "error", "message": f"Unknown project: {project_name}"}, indent=2)

    return run_swarm(
        plan=plan,
        feature_name=feature_name or f"{project_name} task",
        builder_type=project.builder_type,
        repo_path=project.repo_path,
        repo_url=project.repo_url,
        execution_mode=project.execution_mode,
    )


@mcp.tool()
def spawn_project(
    name: str,
    description: str = "",
    template: str = "empty",
    repo_path: str = "",
) -> str:
    """Create a new project from template and register it."""
    from swarm.config import cfg

    created_path = spawn_project_from_template(
        name=name,
        description=description,
        template=template,
        repo_path=repo_path,
    )
    record = _projects.add_project(
        name=name,
        repo_path=created_path,
        execution_mode=cfg.default_execution_mode,
        active=True,
    )
    return json.dumps(
        {
            "status": "created",
            "path": created_path,
            "project": record.__dict__,
        },
        indent=2,
    )


@mcp.tool()
def swarm_status(task_id: str = "") -> str:
    """Check the status of a swarm run.

    Pass a specific task_id to poll that run. If omitted, returns the most
    recent run.
    """
    run_id = task_id or _last_run_id
    if not run_id:
        return json.dumps({"status": "no_runs", "message": "No swarm runs yet. Call run_swarm first."})
    with _runs_lock:
        result = _runs.get(run_id)
    if result is None:
        return json.dumps({"status": "not_found", "task_id": run_id})
    return json.dumps(result, indent=2)


@mcp.tool()
def list_agents() -> str:
    """List all available worker agents and their specializations.

    Returns a JSON array of agent descriptions. Use this to understand
    what the swarm can do before calling run_swarm.
    """
    agents = [
        {"name": "python_dev", "role": "Python Engineer", "focus": "Python apps, CLIs, APIs, automation"},
        {"name": "react_dev", "role": "React / Next.js Engineer", "focus": "React, Next.js, TypeScript, Tailwind"},
        {"name": "wordpress_dev", "role": "WordPress Engineer", "focus": "PHP, WordPress plugins, REST API"},
        {"name": "shopify_dev", "role": "Shopify Engineer", "focus": "Liquid, Theme Kit, Storefront API"},
        {"name": "reviewer", "role": "Code Reviewer", "focus": "Bugs, anti-patterns, code quality"},
        {"name": "security", "role": "Security Auditor", "focus": "OWASP Top 10, XSS, injection, auth"},
        {"name": "performance", "role": "Performance Engineer", "focus": "Core Web Vitals, bundle size, re-renders"},
        {"name": "tester", "role": "Test Engineer", "focus": "Jest, Vitest, Playwright, pytest"},
        {"name": "refactorer", "role": "Refactor Engineer", "focus": "Clean code, DRY, readability"},
        {"name": "docs", "role": "Documentation Writer", "focus": "README, JSDoc, docstrings, migration notes"},
        {"name": "linter_agent", "role": "Lint Specialist", "focus": "eslint, ruff, pylint, code style"},
    ]
    return json.dumps(agents, indent=2)


if __name__ == "__main__":
    mcp.run()
