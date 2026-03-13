"""Crew assembly — groups of agents that work together in each phase."""

from __future__ import annotations

from crewai import Agent, Crew, Process, Task


def solo_crew(agent: Agent, task: Task, verbose: bool = True) -> Crew:
    """Single-agent crew for sequential pipeline steps."""
    return Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=verbose,
    )


def quality_crew(
    agents: list[Agent],
    tasks: list[Task],
    verbose: bool = True,
) -> Crew:
    """Multi-agent crew for quality and polish checks.

    CrewAI currently validates sequential crews to allow at most one async task
    at the end. Keep quality/polish tasks synchronous so these crews are always
    valid across CrewAI versions.
    """
    return Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=verbose,
    )


def parallel_solo_crews(
    agent_task_pairs: list[tuple[Agent, Task]],
    verbose: bool = True,
) -> list[str]:
    """Run multiple solo crews in parallel threads, return results in order."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def run_one(agent: Agent, task: Task) -> str:
        crew = solo_crew(agent, task, verbose=verbose)
        return str(crew.kickoff())

    results: list[str | None] = [None] * len(agent_task_pairs)
    with ThreadPoolExecutor(max_workers=len(agent_task_pairs)) as pool:
        future_to_idx = {
            pool.submit(run_one, agent, task): idx
            for idx, (agent, task) in enumerate(agent_task_pairs)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()
    return results
