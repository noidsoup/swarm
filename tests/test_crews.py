from __future__ import annotations

import swarm.crews as crews


class DummyTask:
    def __init__(self, async_execution: bool = False) -> None:
        self.async_execution = async_execution


def test_quality_crew_does_not_force_async_tasks(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummyCrew:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(crews, "Crew", DummyCrew)

    tasks = [DummyTask(async_execution=False), DummyTask(async_execution=True)]

    crews.quality_crew(agents=[object()], tasks=tasks, verbose=False)

    # Keep caller-provided task execution flags unchanged for compatibility
    # with CrewAI's sequential async-task validation rules.
    assert [task.async_execution for task in tasks] == [False, True]
    assert captured["tasks"] == tasks
    assert captured["verbose"] is False
