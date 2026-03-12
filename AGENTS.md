# AGENTS.md

## Purpose

`swarm` is an AI coding orchestrator. Cursor acts as the commander; the project runs builder, reviewer, quality, and polish agents through CrewAI flows.

## Main Entry Points

- `run.py`: local CLI for headless and standalone runs
- `swarm/mcp_server.py`: Cursor MCP entry point
- `swarm/api.py`: remote task submission API
- `swarm/worker.py`: background task worker
- `daemon.py` and `swarm/daemon_cli.py`: continuous improvement daemon entry points

## Builder Routing

- Default builder for generic work is `python_dev`
- `react_dev` is used for React/Next.js/frontend requests
- `wordpress_dev` is used for WordPress/PHP/plugin requests
- `shopify_dev` is used for Shopify/Liquid/theme requests

## Change Guidelines

- Keep the flow pipeline deterministic: BUILD -> REVIEW LOOP -> QUALITY -> POLISH
- When editing `swarm/flow.py`, prefer shared helpers over copy-pasted phase logic
- When editing tools in `swarm/tools/`, preserve repo-root sandboxing and avoid shell interpolation for git/file operations
- When changing queue or worker behavior, keep the in-memory fallback working alongside Redis
- Use standard `logging` for operational output; avoid adding new `print()` calls in runtime code

## Verification

- Run `ruff check swarm tests run.py daemon.py setup.py simplemem_client.py simplemem_cli.py`
- Run `pytest`
- If you change packaging or installs, make sure `requirements.txt` and `setup.py` stay aligned

## Test Expectations

- Add or update tests for any behavior change in config, flow orchestration, task storage, or tool safety
- Prefer unit tests for helpers and mocked integration tests for flow orchestration

## MCP and Remote Workflow

- `run_swarm()` is asynchronous and returns a task ID immediately
- Poll with `swarm_status(task_id)` for final status and summaries
- Remote API tasks should be safe for untrusted input: validate paths, repo URLs, and shell-adjacent arguments
