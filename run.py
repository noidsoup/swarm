#!/usr/bin/env python3
"""AI Dev Swarm -- run an 11-agent coding swarm.

Headless mode (Cursor is commander):
    python run.py --plan plan.md "Add product filtering"
    python run.py --plan - "Fix login" < plan.txt

Standalone mode (agents do everything):
    python run.py "Add product filtering to the Next.js collection page"

Options:
    python run.py --no-commit "Refactor the auth module"
    python run.py --dry-run "Add dark mode toggle"
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

WORKER_PHASES = ["build", "review", "quality", "polish"]
FULL_PHASES = ["plan", "build", "review", "quality", "polish", "ship"]


def _configure_windows_utf8_stdio() -> None:
    """Force UTF-8 stdio on Windows to avoid charmap issues."""
    if sys.platform != "win32":
        return

    try:
        import io

        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass


def _parse_phase_list(value: str) -> set[str]:
    return {phase.strip().lower() for phase in value.split(",") if phase.strip()}


def _resolve_phase_selection(only: str | None, skip: str | None, headless: bool) -> list[str]:
    available = WORKER_PHASES if headless else FULL_PHASES

    if only and skip:
        raise ValueError("Use either --only or --skip, not both.")

    if only:
        selected = _parse_phase_list(only)
    else:
        selected = set(available)
        if skip:
            selected -= _parse_phase_list(skip)

    unknown = selected - set(available)
    if unknown:
        raise ValueError(f"Unknown phases: {', '.join(sorted(unknown))}")
    if not selected:
        raise ValueError("Phase selection cannot be empty.")

    if headless:
        if selected & {"review", "quality", "polish"}:
            selected.add("build")
    else:
        if selected & {"build", "review", "quality", "polish", "ship"}:
            selected.add("plan")
        if selected & {"review", "quality", "polish", "ship"}:
            selected.add("build")
        if "ship" in selected:
            selected.update({"review", "quality", "polish"})

    return [phase for phase in available if phase in selected]


def main() -> None:
    from swarm.logging_utils import configure_logging

    _configure_windows_utf8_stdio()

    parser = argparse.ArgumentParser(
        description="AI Dev Swarm -- 11-agent coding pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "request",
        nargs="?",
        help="Feature request or task description",
    )
    parser.add_argument(
        "--plan",
        metavar="FILE",
        help="Path to a plan file (or '-' for stdin). Enables headless mode.",
    )
    parser.add_argument(
        "--builder",
        choices=["python_dev", "react_dev", "wordpress_dev", "shopify_dev"],
        help="Force a specific builder agent",
    )
    parser.add_argument(
        "--worker-model",
        help="Worker model (e.g. ollama/qwen2.5-coder, gpt-4o-mini)",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Skip auto-commit even if approved",
    )
    parser.add_argument(
        "--max-reviews",
        type=int,
        default=None,
        help="Max review loop iterations (defaults to config value)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print config and exit without running",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce agent output verbosity",
    )
    parser.add_argument(
        "--repo",
        metavar="PATH",
        help="Path to target repository (default: current directory)",
    )
    parser.add_argument(
        "--only",
        metavar="PHASES",
        help="Comma-separated phases to run (prerequisites are added automatically)",
    )
    parser.add_argument(
        "--skip",
        metavar="PHASES",
        help="Comma-separated phases to skip",
    )

    args = parser.parse_args()

    if not args.request and not args.plan:
        parser.print_help()
        sys.exit(1)

    from swarm.config import cfg

    configure_logging()
    logger = logging.getLogger(__name__)

    if args.worker_model:
        cfg.worker_model = args.worker_model
    if args.no_commit:
        cfg.auto_commit = False
    if args.max_reviews is not None:
        cfg.max_review_loops = args.max_reviews
    if args.quiet:
        cfg.verbose = False
    if args.repo:
        import os
        cfg.repo_root = os.path.abspath(args.repo)

    headless = args.plan is not None
    mode_label = "HEADLESS (Cursor is commander)" if headless else "STANDALONE"
    try:
        selected_phases = _resolve_phase_selection(args.only, args.skip, headless)
    except ValueError as e:
        parser.error(str(e))

    banner = """
    +-----------------------------------------------------------+
    |              AI DEV SWARM  --  11 Agent Army               |
    |                                                            |
    |   Builder > Reviewer > Security > Perf > Tests > Lint      |
    |   > Refactor > Docs                                        |
    +-----------------------------------------------------------+
    """
    logger.info("\n%s", banner)
    logger.info("Mode=%s", mode_label)
    logger.info("Request=%s", args.request or "(from plan)")
    logger.info("Worker=%s", cfg.worker_model)
    logger.info("Commit=%s", "yes" if cfg.auto_commit else "no")
    logger.info("Reviews=max %s iterations", cfg.max_review_loops)
    logger.info("Repo=%s", cfg.repo_root)
    logger.info("Phases=%s", ",".join(selected_phases))
    if args.builder:
        logger.info("Builder=%s", args.builder)

    if args.dry_run:
        logger.info("Dry run complete no work executed")
        sys.exit(0)

    start_time = time.time()

    if headless:
        plan_text = _read_plan(args.plan)
        from swarm.flow import WorkerSwarmFlow

        flow = WorkerSwarmFlow(
            plan=plan_text,
            feature_request=args.request or "",
            builder_type=args.builder or "",
        )
        if selected_phases == WORKER_PHASES:
            flow.kickoff()
        else:
            flow.run_selected_phases(selected_phases)
        elapsed = time.time() - start_time

        logger.info("Worker swarm complete status=%s", flow.state.final_status)
        logger.info("Elapsed_seconds=%.1f", elapsed)
        logger.info("Review_iterations=%s", flow.state.review_iteration)
        logger.info("Results returned Cursor judges the output")
    else:
        if not args.request:
            logger.error("Standalone mode requires a feature request")
            sys.exit(1)
        from swarm.flow import FullSwarmFlow

        flow = FullSwarmFlow(feature_request=args.request)
        if selected_phases == FULL_PHASES:
            flow.kickoff()
        else:
            flow.run_selected_phases(selected_phases)
        elapsed = time.time() - start_time

        logger.info("Standalone swarm complete status=%s", flow.state.final_status)
        logger.info("Elapsed_seconds=%.1f", elapsed)
        logger.info("Review_iterations=%s", flow.state.review_iteration)


def _read_plan(plan_arg: str) -> str:
    """Read plan from file path or stdin."""
    if plan_arg == "-":
        return sys.stdin.read()
    from pathlib import Path

    p = Path(plan_arg)
    if not p.is_file():
        logging.getLogger(__name__).error("Plan file not found path=%s", plan_arg)
        sys.exit(1)
    return p.read_text(encoding="utf-8")


if __name__ == "__main__":
    main()
