# AGENTS.md

## Purpose

`swarm` is an AI coding orchestrator. Cursor acts as the commander; the project runs builder, reviewer, quality, and polish agents through CrewAI flows.

## Operational Truths (Read First)

- The orchestrator is this repo and is typically run from the Mac checkout (`/Users/nicholas/Repos/swarm`).
- Ollama does **not** have to run on Mac; workers use `OLLAMA_BASE_URL` from env/config, so it can point to a Windows host (for example `http://192.168.x.x:11434`).
- Default Ollama endpoint is `http://localhost:11434` when `OLLAMA_BASE_URL` is not overridden.
- Current runtime advertises an **11-agent** pipeline (`run.py` and `swarm/mcp_server.py`), including `python_dev` plus framework-specialized builders.
- Quality/polish are implemented as sequential crews in current code; do not describe them as guaranteed parallel execution.
- Standalone "ship/commit" behavior depends on `AUTO_COMMIT`; default is `false` so commits are skipped unless explicitly enabled.
- `run_swarm()` in MCP is asynchronous and returns a task ID; use `swarm_status(task_id)` to poll.

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

## Context7 and Vercel Skill Defaults

- For framework/library behavior, version-specific APIs, and migration guidance, query `user-context7` first.
- For React/Next.js tasks, apply Vercel-oriented skills when relevant:
  - `vercel-react-best-practices`
  - `next-best-practices`
  - `next-cache-components`
  - `next-upgrade` (for migrations)
- For deployment requests targeting Vercel, use `vercel-deploy` and default to preview deploys unless production is explicitly requested.

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

## Quick Runtime Matrix

- **Headless (recommended):** Cursor plans/judges, swarm executes phases (`build, review, quality, polish`).
- **Standalone:** Swarm runs planning + execution end-to-end; shipping is only automatic when `AUTO_COMMIT=true`.
- **Remote Ollama on Windows:** set `OLLAMA_BASE_URL` to the Windows Ollama URL; Mac runs orchestration while Windows provides model inference.
