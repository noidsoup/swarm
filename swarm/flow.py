"""SwarmFlow -- orchestrator for the agent pipeline.

Two modes:
  WorkerSwarmFlow (headless) -- Cursor provides the plan, agents execute:
    BUILD > REVIEW LOOP > QUALITY GATES > POLISH > return results

  FullSwarmFlow (standalone) -- agents handle everything end-to-end:
    PLAN > BUILD > REVIEW LOOP > QUALITY GATES > POLISH > JUDGE > SHIP
"""

from __future__ import annotations

import json
import re
import textwrap

from crewai.flow.flow import Flow, listen, router, start
from pydantic import BaseModel

from swarm.agents import build_agents
from swarm.config import cfg
from swarm.crews import quality_crew, solo_crew
from swarm.tasks import (
    build_task,
    docs_task,
    fix_task,
    lint_task,
    performance_task,
    refactor_task,
    review_task,
    security_task,
    test_task,
)
from swarm.tools.git_tool import _git


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
class SwarmState(BaseModel):
    feature_request: str = ""
    plan: str = ""
    build_summary: str = ""
    review_feedback: str = ""
    review_iteration: int = 0
    quality_report: str = ""
    polish_report: str = ""
    final_status: str = ""


def _pick_builder(request: str) -> str:
    """Route to the right builder based on keywords."""
    lower = request.lower()
    if any(kw in lower for kw in ("wordpress", "wp", "plugin", "php")):
        return "wordpress_dev"
    if any(kw in lower for kw in ("shopify", "liquid", "theme")):
        return "shopify_dev"
    if any(
        kw in lower
        for kw in (
            "react",
            "next.js",
            "nextjs",
            "typescript",
            "javascript",
            "frontend",
            "tailwind",
            "tsx",
            "jsx",
        )
    ):
        return "react_dev"
    return "python_dev"


def _print_phase(name: str) -> None:
    bar = "=" * 60
    print(f"\n{bar}")
    print(f"  PHASE: {name}")
    print(f"{bar}\n")


# ===================================================================
# BaseSwarmFlow -- shared execution phases
# ===================================================================
class BaseSwarmFlow(Flow[SwarmState]):
    """Shared swarm execution phases used by worker and standalone flows."""

    def __init__(
        self,
        feature_request: str = "",
        plan: str = "",
        builder_type: str = "",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.state.feature_request = feature_request
        self.state.plan = plan
        self._agents = build_agents()
        self._builder = builder_type or _pick_builder(feature_request or plan)

    def _run_build_phase(self) -> str:
        _print_phase(f"BUILD ({self._builder})")
        builder = self._agents[self._builder]
        task = build_task(builder, self.state.plan)
        crew = solo_crew(builder, task, verbose=cfg.verbose)
        result = crew.kickoff()
        self.state.build_summary = str(result)
        print(f"\n[BUILD RESULT]\n{self.state.build_summary[:500]}...")
        return self.state.build_summary

    def _run_review_phase(self) -> str:
        _print_phase(
            f"REVIEW (iteration {self.state.review_iteration + 1}/{cfg.max_review_loops})"
        )
        reviewer = self._agents["reviewer"]
        task = review_task(reviewer, self.state.build_summary)
        crew = solo_crew(reviewer, task, verbose=cfg.verbose)
        result = crew.kickoff()
        self.state.review_feedback = str(result)
        self.state.review_iteration += 1
        print(f"\n[REVIEW RESULT]\n{self.state.review_feedback[:500]}...")
        return self.state.review_feedback

    def _run_review_router(self) -> str:
        if "APPROVED" in self.state.review_feedback.upper():
            return "approved"
        if self.state.review_iteration >= cfg.max_review_loops:
            print("\n[WARN] Max review iterations reached. Proceeding anyway.")
            return "approved"
        return "needs_fix"

    def _run_fix_phase(self) -> str:
        _print_phase(f"FIX (iteration {self.state.review_iteration})")
        builder = self._agents[self._builder]
        task = fix_task(builder, self.state.review_feedback)
        crew = solo_crew(builder, task, verbose=cfg.verbose)
        result = crew.kickoff()
        self.state.build_summary += f"\n\n--- Fix iteration {self.state.review_iteration} ---\n{result}"
        return str(result)

    def _run_quality_phase(self) -> str:
        _print_phase("QUALITY GATES")
        agents = self._agents
        summary = self.state.build_summary

        sec_t = security_task(agents["security"], summary)
        perf_t = performance_task(agents["performance"], summary)
        tst_t = test_task(agents["tester"], summary)
        lnt_t = lint_task(agents["linter_agent"], summary)

        crew = quality_crew(
            agents=[agents["security"], agents["performance"], agents["tester"], agents["linter_agent"]],
            tasks=[sec_t, perf_t, tst_t, lnt_t],
            verbose=cfg.verbose,
        )
        result = crew.kickoff()
        self.state.quality_report = str(result)
        print(f"\n[QUALITY RESULT]\n{self.state.quality_report[:500]}...")
        return self.state.quality_report

    def _run_polish_phase(self) -> str:
        _print_phase("POLISH")
        agents = self._agents
        summary = self.state.build_summary

        ref_t = refactor_task(agents["refactorer"], summary)
        doc_t = docs_task(agents["docs"], summary)

        crew = quality_crew(
            agents=[agents["refactorer"], agents["docs"]],
            tasks=[ref_t, doc_t],
            verbose=cfg.verbose,
        )
        result = crew.kickoff()
        self.state.polish_report = str(result)
        print(f"\n[POLISH RESULT]\n{self.state.polish_report[:500]}...")
        return self.state.polish_report


# ===================================================================
# WorkerSwarmFlow -- headless mode (Cursor is commander)
# ===================================================================
class WorkerSwarmFlow(BaseSwarmFlow):
    """Cursor provides the plan. Workers execute, review, and polish.

    Returns a structured results dict that Cursor uses to judge.
    """

    def __init__(self, plan: str, feature_request: str = "", builder_type: str = "", **kwargs):
        super().__init__(
            feature_request=feature_request,
            plan=plan,
            builder_type=builder_type,
            **kwargs,
        )

    # -- BUILD --
    @start()
    def build_phase(self) -> str:
        return self._run_build_phase()

    # -- REVIEW LOOP --
    @listen(build_phase)
    def review_phase(self, _: str) -> str:
        return self._run_review_phase()

    @router(review_phase)
    def review_router(self, _: str) -> str:
        return self._run_review_router()

    @listen("needs_fix")
    def fix_phase(self) -> str:
        return self._run_fix_phase()

    @listen(fix_phase)
    def re_review(self, fix_result: str) -> str:
        return self.review_phase(fix_result)

    # -- QUALITY GATES --
    @listen("approved")
    def quality_phase(self) -> str:
        return self._run_quality_phase()

    # -- POLISH --
    @listen(quality_phase)
    def polish_phase(self, _: str) -> str:
        return self._run_polish_phase()

    # -- FINISH (return structured results to Cursor) --
    @listen(polish_phase)
    def finish_phase(self, _: str) -> str:
        self.state.final_status = "WORKER_COMPLETE"
        results = {
            "status": "complete",
            "builder": self._builder,
            "review_iterations": self.state.review_iteration,
            "build_summary": self.state.build_summary[:2000],
            "review_feedback": self.state.review_feedback[:1000],
            "quality_report": self.state.quality_report[:2000],
            "polish_report": self.state.polish_report[:1000],
        }
        print("\n" + "=" * 60)
        print("  WORKER SWARM COMPLETE -- awaiting Cursor judgment")
        print("=" * 60)
        return json.dumps(results, indent=2)


# ===================================================================
# FullSwarmFlow -- standalone mode (no Cursor needed)
# ===================================================================
class FullSwarmFlow(BaseSwarmFlow):
    """Standalone mode: all agents run locally including planning and judging.

    Uses the worker model for everything (no commander model needed).
    Pipeline: PLAN > BUILD > REVIEW LOOP > QUALITY > POLISH > SHIP
    """

    def __init__(self, feature_request: str, **kwargs):
        super().__init__(feature_request=feature_request, **kwargs)

    # -- PLAN (worker model acts as architect) --
    @start()
    def planning_phase(self) -> str:
        _print_phase("PLAN")
        from swarm.tasks import plan_task as _plan_task

        planner = self._agents["reviewer"]
        task = _plan_task(planner, self.state.feature_request)
        crew = solo_crew(planner, task, verbose=cfg.verbose)
        result = crew.kickoff()
        self.state.plan = str(result)
        print(f"\n[PLAN RESULT]\n{self.state.plan[:500]}...")
        return self.state.plan

    # -- BUILD --
    @listen(planning_phase)
    def build_phase(self, _: str) -> str:
        return self._run_build_phase()

    # -- REVIEW LOOP --
    @listen(build_phase)
    def review_phase(self, _: str) -> str:
        return self._run_review_phase()

    @router(review_phase)
    def review_router(self, _: str) -> str:
        return self._run_review_router()

    @listen("needs_fix")
    def fix_phase(self) -> str:
        return self._run_fix_phase()

    @listen(fix_phase)
    def re_review(self, fix_result: str) -> str:
        return self.review_phase(fix_result)

    # -- QUALITY GATES --
    @listen("approved")
    def quality_phase(self) -> str:
        return self._run_quality_phase()

    # -- POLISH --
    @listen(quality_phase)
    def polish_phase(self, _: str) -> str:
        return self._run_polish_phase()

    # -- SHIP --
    @listen(polish_phase)
    def ship_phase(self, _: str) -> str:
        _print_phase("SHIP")

        if not cfg.auto_commit:
            self.state.final_status = "COMPLETE (auto-commit disabled)"
            print("\n[COMPLETE] Auto-commit is disabled. Commit manually.")
            return self.state.final_status

        slug = re.sub(r"[^a-z0-9]+", "-", self.state.feature_request.lower())[:40].strip("-")
        branch_name = f"{cfg.branch_prefix}{slug}"

        _git(["checkout", "-b", branch_name])
        _git(["add", "-A"])

        commit_msg = (
            f"feat: {self.state.feature_request}\n\n"
            f"Implemented by AI Dev Swarm (standalone mode)\n"
            f"Review iterations: {self.state.review_iteration}\n"
            f"Builder: {self._builder}"
        )
        result = _git(["commit", "-m", commit_msg])

        self.state.final_status = f"SHIPPED on branch {branch_name}"
        print(f"\n[SHIPPED] {result}")
        print(f"Branch: {branch_name}")
        return self.state.final_status
