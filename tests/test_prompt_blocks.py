from __future__ import annotations

from swarm.prompt_blocks import (
    build_constraints_block,
    build_context_block,
    build_retrieval_block,
    compose_task_prompt,
)


def test_prompt_blocks_compose_task_context_retrieval_and_constraints() -> None:
    prompt = compose_task_prompt(
        task_text="Implement the dashboard page.",
        context_block=build_context_block(
            {
                "repo_summary": "Detected nextjs/react repo.",
                "builder_hint": "react_dev",
                "instructions": ["AGENTS.md", "README.md"],
                "risk_areas": ["auth"],
            }
        ),
        retrieval_block=build_retrieval_block(
            {
                "files": [{"path": "src/components/Dashboard.tsx"}],
                "memories": [{"text": "Prefer existing dashboard card patterns."}],
            }
        ),
        constraints_block=build_constraints_block(
            [
                "Do not edit generated files.",
                "Keep behavior unchanged outside the requested scope.",
            ]
        ),
        output_format="Return a file-by-file change summary.",
    )

    assert "TASK:" in prompt
    assert "REPO CONTEXT:" in prompt
    assert "RETRIEVAL HINTS:" in prompt
    assert "CONSTRAINTS:" in prompt
    assert "OUTPUT FORMAT:" in prompt


def test_prompt_blocks_exclude_empty_sections() -> None:
    prompt = compose_task_prompt(
        task_text="Fix the bug.",
        context_block=build_context_block({}),
        retrieval_block=build_retrieval_block({"files": [], "memories": []}),
        constraints_block=build_constraints_block([]),
        output_format="",
    )

    assert "REPO CONTEXT:" not in prompt
    assert "RETRIEVAL HINTS:" not in prompt
    assert "CONSTRAINTS:" not in prompt
    assert "OUTPUT FORMAT:" not in prompt
    assert "TASK:" in prompt


def test_prompt_blocks_are_bounded_in_size() -> None:
    huge_memory = "x" * 5000
    prompt = compose_task_prompt(
        task_text="Refactor the module.",
        context_block=build_context_block(
            {
                "repo_summary": "Detected python repo.",
                "builder_hint": "python_dev",
                "instructions": ["AGENTS.md"] * 20,
                "risk_areas": ["auth", "billing", "database", "deployment"],
            }
        ),
        retrieval_block=build_retrieval_block(
            {
                "files": [{"path": f"src/file_{i}.py"} for i in range(20)],
                "memories": [{"text": huge_memory}],
            }
        ),
        constraints_block=build_constraints_block(["Keep tests passing."] * 20),
        output_format="Return a concise summary.",
        max_chars=1200,
    )

    assert len(prompt) <= 1200
