from __future__ import annotations

import json
from pathlib import Path

import swarm.flow as flow_module


class DummyCrew:
    def __init__(self, result: str):
        self.result = result

    def kickoff(self) -> str:
        return self.result


def test_worker_swarm_flow_runs_review_loop_until_approved(monkeypatch) -> None:
    monkeypatch.setattr(
        flow_module,
        "build_agents",
        lambda: {
            "python_dev": object(),
            "react_dev": object(),
            "wordpress_dev": object(),
            "shopify_dev": object(),
            "reviewer": object(),
            "security": object(),
            "performance": object(),
            "tester": object(),
            "refactorer": object(),
            "docs": object(),
            "linter_agent": object(),
        },
    )
    monkeypatch.setattr(flow_module, "build_task", lambda agent, plan: ("build", plan))
    monkeypatch.setattr(flow_module, "review_task", lambda agent, summary: ("review", summary))
    monkeypatch.setattr(flow_module, "fix_task", lambda agent, feedback: ("fix", feedback))
    monkeypatch.setattr(flow_module, "security_task", lambda agent, summary: ("security", summary))
    monkeypatch.setattr(flow_module, "performance_task", lambda agent, summary: ("performance", summary))
    monkeypatch.setattr(flow_module, "test_task", lambda agent, summary: ("test", summary))
    monkeypatch.setattr(flow_module, "lint_task", lambda agent, summary: ("lint", summary))
    monkeypatch.setattr(flow_module, "refactor_task", lambda agent, summary: ("refactor", summary))
    monkeypatch.setattr(flow_module, "docs_task", lambda agent, summary: ("docs", summary))

    review_results = iter(["Needs fixes", "APPROVED"])

    def fake_solo_crew(agent, task, verbose=True):
        kind = task[0]
        if kind == "build":
            return DummyCrew("built feature")
        if kind == "review":
            return DummyCrew(next(review_results))
        if kind == "fix":
            return DummyCrew("fixed review issues")
        raise AssertionError(f"Unexpected solo crew task: {task}")

    def fake_quality_crew(agents, tasks, verbose=True):
        kinds = {task[0] for task in tasks}
        if "security" in kinds:
            return DummyCrew("quality report")
        if "refactor" in kinds:
            return DummyCrew("polish report")
        raise AssertionError(f"Unexpected quality crew tasks: {tasks}")

    monkeypatch.setattr(flow_module, "solo_crew", fake_solo_crew)
    monkeypatch.setattr(flow_module, "quality_crew", fake_quality_crew)

    flow = flow_module.WorkerSwarmFlow(plan="Ship it")

    result = json.loads(flow.kickoff())

    assert result["status"] == "complete"
    assert result["review_iterations"] == 2
    assert "fixed review issues" in flow.state.build_summary
    assert flow.state.quality_report == "quality report"
    assert flow.state.polish_report == "polish report"


def test_worker_swarm_flow_can_run_selected_phases(monkeypatch) -> None:
    monkeypatch.setattr(
        flow_module,
        "build_agents",
        lambda: {
            "python_dev": object(),
            "react_dev": object(),
            "wordpress_dev": object(),
            "shopify_dev": object(),
            "reviewer": object(),
            "security": object(),
            "performance": object(),
            "tester": object(),
            "refactorer": object(),
            "docs": object(),
            "linter_agent": object(),
        },
    )
    monkeypatch.setattr(flow_module, "build_task", lambda agent, plan: ("build", plan))
    monkeypatch.setattr(flow_module, "security_task", lambda agent, summary: ("security", summary))
    monkeypatch.setattr(flow_module, "performance_task", lambda agent, summary: ("performance", summary))
    monkeypatch.setattr(flow_module, "test_task", lambda agent, summary: ("test", summary))
    monkeypatch.setattr(flow_module, "lint_task", lambda agent, summary: ("lint", summary))

    def fake_solo_crew(agent, task, verbose=True):
        assert task[0] == "build"
        return DummyCrew("built feature")

    def fake_quality_crew(agents, tasks, verbose=True):
        return DummyCrew("quality report")

    monkeypatch.setattr(flow_module, "solo_crew", fake_solo_crew)
    monkeypatch.setattr(flow_module, "quality_crew", fake_quality_crew)

    flow = flow_module.WorkerSwarmFlow(plan="Ship it")

    result = json.loads(flow.run_selected_phases(["build", "quality"]))

    assert result["status"] == "complete"
    assert flow.state.review_iteration == 0
    assert flow.state.quality_report == "quality report"
    assert flow.state.polish_report == ""


def test_build_phase_writes_checkpoints_and_captured_stdout(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        flow_module,
        "build_agents",
        lambda: {
            "python_dev": object(),
            "react_dev": object(),
            "wordpress_dev": object(),
            "shopify_dev": object(),
            "reviewer": object(),
            "security": object(),
            "performance": object(),
            "tester": object(),
            "refactorer": object(),
            "docs": object(),
            "linter_agent": object(),
        },
    )
    monkeypatch.setattr(flow_module, "build_task", lambda agent, plan: ("build", plan))

    class VerboseCrew(DummyCrew):
        def kickoff(self) -> str:
            print("tool call started")
            return self.result

    monkeypatch.setattr(flow_module, "solo_crew", lambda agent, task, verbose=True: VerboseCrew("built feature"))

    flow = flow_module.WorkerSwarmFlow(plan="Ship it")
    flow.state.run_artifacts_dir = str(tmp_path)

    result = flow._run_build_phase()

    assert result == "built feature"
    build_log = Path(tmp_path) / "build_phase.log"
    assert build_log.exists()
    content = build_log.read_text(encoding="utf-8")
    assert "checkpoint=build_phase_started" in content
    assert "checkpoint=build_task_created" in content
    assert "checkpoint=build_kickoff_started" in content
    assert "tool call started" in content
    assert "checkpoint=build_kickoff_completed" in content
