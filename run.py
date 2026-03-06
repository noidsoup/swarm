#!/usr/bin/env python3
"""AI Dev Swarm -- run a 10-agent coding swarm.

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
import sys
import time

# On Windows, CrewAI event bus can log emojis; force UTF-8 to avoid 'charmap' codec errors
if sys.platform == "win32":
    try:
        import io
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI Dev Swarm -- 10-agent coding pipeline",
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
        choices=["react_dev", "wordpress_dev", "shopify_dev"],
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
        default=3,
        help="Max review loop iterations (default: 3)",
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

    args = parser.parse_args()

    if not args.request and not args.plan:
        parser.print_help()
        sys.exit(1)

    from swarm.config import cfg

    if args.worker_model:
        cfg.worker_model = args.worker_model
    if args.no_commit:
        cfg.auto_commit = False
    if args.max_reviews:
        cfg.max_review_loops = args.max_reviews
    if args.quiet:
        cfg.verbose = False
    if args.repo:
        import os
        cfg.repo_root = os.path.abspath(args.repo)

    headless = args.plan is not None
    mode_label = "HEADLESS (Cursor is commander)" if headless else "STANDALONE"

    banner = """
    +-----------------------------------------------------------+
    |              AI DEV SWARM  --  10 Agent Army               |
    |                                                            |
    |   Builder > Reviewer > Security > Perf > Tests > Lint      |
    |   > Refactor > Docs                                        |
    +-----------------------------------------------------------+
    """
    print(banner)
    print(f"  Mode:    {mode_label}")
    print(f"  Request: {args.request or '(from plan)'}")
    print(f"  Worker:  {cfg.worker_model}")
    print(f"  Commit:  {'yes' if cfg.auto_commit else 'no'}")
    print(f"  Reviews: max {cfg.max_review_loops} iterations")
    print(f"  Repo:    {cfg.repo_root}")
    if args.builder:
        print(f"  Builder: {args.builder}")
    print()

    if args.dry_run:
        print("[DRY RUN] Would run the swarm with the config above. Exiting.")
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
        result = flow.kickoff()
        elapsed = time.time() - start_time

        print("\n" + "=" * 60)
        print("  WORKER SWARM COMPLETE")
        print("=" * 60)
        print(f"\n  Status:  {flow.state.final_status}")
        print(f"  Time:    {elapsed:.1f}s")
        print(f"  Reviews: {flow.state.review_iteration}")
        print("\n  Results returned. Cursor judges the output.")
    else:
        if not args.request:
            print("[ERROR] Standalone mode requires a feature request.")
            sys.exit(1)
        from swarm.flow import FullSwarmFlow

        flow = FullSwarmFlow(feature_request=args.request)
        result = flow.kickoff()
        elapsed = time.time() - start_time

        print("\n" + "=" * 60)
        print("  SWARM COMPLETE")
        print("=" * 60)
        print(f"\n  Status:  {flow.state.final_status}")
        print(f"  Time:    {elapsed:.1f}s")
        print(f"  Reviews: {flow.state.review_iteration}")

    print()


def _read_plan(plan_arg: str) -> str:
    """Read plan from file path or stdin."""
    if plan_arg == "-":
        return sys.stdin.read()
    from pathlib import Path

    p = Path(plan_arg)
    if not p.is_file():
        print(f"[ERROR] Plan file not found: {plan_arg}")
        sys.exit(1)
    return p.read_text(encoding="utf-8")


if __name__ == "__main__":
    main()
