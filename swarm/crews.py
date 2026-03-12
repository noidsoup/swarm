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
    """Multi-agent crew with async tasks for independent checks."""
    for task in tasks:
        task.async_execution = True
    return Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=verbose,
    )
