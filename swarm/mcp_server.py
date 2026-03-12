"""MCP server for the AI Dev Swarm.

Exposes tools to Cursor so it can act as the commander:
  - run_swarm: execute the worker pipeline with a plan
  - swarm_status: check last run results
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
from swarm.task_models import new_task_id, utcnow_iso

_swarm_root = str(Path(__file__).resolve().parent.parent)
if _swarm_root not in sys.path:
    sys.path.insert(0, _swarm_root)

mcp = FastMCP("ai-dev-swarm")

_last_result: dict | None = None
_last_run_id: str | None = None
_runs: dict[str, dict] = {}
_runs_lock = threading.Lock()


def _update_run(run_id: str, **updates) -> None:
    with _runs_lock:
        current = _runs.get(run_id, {})
        current.update(updates)
        _runs[run_id] = current


def _execute_swarm_run(
    run_id: str,
    plan: str,
    feature_name: str,
    builder_type: str,
    repo_path: str,
) -> None:
    global _last_result

    from swarm.config import cfg

    if repo_path:
        cfg.repo_root = repo_path
    cfg.auto_commit = False

    try:
        from swarm.flow import WorkerSwarmFlow

        flow = WorkerSwarmFlow(
            plan=plan,
            feature_request=feature_name,
            builder_type=builder_type,
        )
        flow.kickoff()

        result = {
            "status": "complete",
            "task_id": run_id,
            "builder": flow._builder,
            "review_iterations": flow.state.review_iteration,
            "build_summary": flow.state.build_summary[:3000],
            "review_feedback": flow.state.review_feedback[:1500],
            "quality_report": flow.state.quality_report[:3000],
            "polish_report": flow.state.polish_report[:1500],
            "completed_at": utcnow_iso(),
        }
        _last_result = result
        _update_run(run_id, **result)
    except Exception as e:
        error_result = {
            "status": "error",
            "task_id": run_id,
            "error": str(e),
            "traceback": traceback.format_exc()[-2000:],
            "completed_at": utcnow_iso(),
        }
        _last_result = error_result
        _update_run(run_id, **error_result)


@mcp.tool()
def run_swarm(
    plan: str,
    feature_name: str = "",
    builder_type: str = "",
    repo_path: str = "",
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

    Returns:
        JSON with a task_id and initial running status. Poll `swarm_status`
        with that task_id to retrieve progress and final results.
    """
    global _last_run_id, _last_result

    if repo_path:
        resolved = Path(repo_path).resolve()
        if not resolved.is_dir():
            return json.dumps({
                "status": "error",
                "error": f"repo_path is not a valid directory: {repo_path}",
            })
        repo_path = str(resolved)

    run_id = new_task_id()
    _last_run_id = run_id
    initial_result = {
        "status": "running",
        "task_id": run_id,
        "feature_name": feature_name,
        "builder_type": builder_type or "auto",
        "repo_path": repo_path or os.getcwd(),
        "started_at": utcnow_iso(),
    }
    _last_result = initial_result
    _update_run(run_id, **initial_result)

    thread = threading.Thread(
        target=_execute_swarm_run,
        args=(run_id, plan, feature_name, builder_type, repo_path),
        daemon=True,
    )
    thread.start()
    return json.dumps(initial_result, indent=2)


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
