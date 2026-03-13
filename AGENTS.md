# AGENTS.md

## Purpose

`swarm` is an AI coding orchestrator. Cursor acts as the commander; the project runs builder, reviewer, quality, and polish agents through CrewAI flows.

## Offloading AI to Windows

The goal is to run complex AI tasks from the Mac and have the heavy work happen on the Windows machine (e.g. Docker, services, or GPU there). You can use **Ollama** (remote on Windows) or **Cursor AI** from the Mac; the local LLM on Windows is **optional** — just one path.

- **Path A — Remote Ollama:** Mac runs the swarm (orchestration); set `OLLAMA_BASE_URL` to the Windows Ollama URL. All model inference runs on Windows; no swarm process required on Windows, only Ollama.
- **Path B — Cursor / worker on Windows:** Mac sends tasks (e.g. cursor mode inbox/outbox, or API); Windows runs the worker (and optionally Ollama there). Full pipeline can run on Windows; Mac triggers and polls.
- **Path C — Cursor AI from Mac:** Use Cursor’s models from the Mac (Docker, MCP, or other integration) with Windows as the execution or inference target where needed. Local LLM on Windows is optional.

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
- `scripts/swarm_remote.py`: Mac-side remote CLI (dispatch, run, update-windows, status, logs, cancel)

## Mac-side remote CLI (swarm_remote)

When using cursor mode (Mac dispatches, Windows runs the worker), use `scripts/swarm_remote.py` from the Mac:

- **dispatch** — Submit a task (async by default); returns `task_id`. Use `--wait` to block until done.
- **run** — Cursor-only: dispatch, poll status until terminal state, and **retry on failure** (e.g. `--retry 5`). Use for "run until success."
- **update-windows** — SSH to Windows and run `git checkout main && git pull` in the swarm repo; use `--restart-worker` to restart the cursor worker after pull. Requires `WINDOWS_HOST`, `WINDOWS_USER` (and optionally `WINDOWS_SSH_KEY`).
- **Never ask the user for Windows connection details.** They are in repo `.env` (and in `AI_SESSION_MEMORY.md` / runbook). Use those; if missing, infer from repo docs or session memory, not from the user.
- **status** / **logs** / **cancel** — Track or cancel a task by `task_id`. These fall back to cursor outbox when the API is unreachable.

## Documentation Canonicals

- `README.md`: product-level overview and current capabilities
- `AI_RUNBOOK.md`: operator workflows, execution modes, and troubleshooting
- `AI_FEATURE_MAP.md`: module-by-module feature index and test-locked invariants
- `COMMANDER_LOOP.md`: review/fix loop behavior and phase routing
- `USING_IN_OTHER_REPOS.md`: integration patterns for multi-repo usage

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

## Orchestrator Skill Defaults

- For `swarm/flow.py`, `swarm/worker.py`, task store/models, and queue behavior changes, apply:
  - `python-error-handling`
  - `python-resilience`
  - `python-observability`
  - `python-performance-optimization` when performance is in scope
- For `tests/**` updates, apply `python-testing-patterns`.
- For `swarm/mcp_server.py` and `swarm/tools/**`, apply `mcp-builder`.
- For `swarm/api.py` contract changes, apply `api-design-principles`.
- For `.github/workflows/**`, apply `github-actions-templates`.

## Change Guidelines

- Keep the flow pipeline deterministic: BUILD -> REVIEW LOOP -> QUALITY -> POLISH
- When editing `swarm/flow.py`, prefer shared helpers over copy-pasted phase logic
- When editing tools in `swarm/tools/`, preserve repo-root sandboxing and avoid shell interpolation for git/file operations
- When changing queue or worker behavior, keep the in-memory fallback working alongside Redis
- Use standard `logging` for operational output; avoid adding new `print()` calls in runtime code

## Verification

- Run `ruff check swarm tests run.py daemon.py setup.py simplemem_client.py simplemem_cli.py scripts/swarm_remote.py`
- Run `pytest`
- If you change packaging or installs, make sure `requirements.txt` and `setup.py` stay aligned

## Test Expectations

- Add or update tests for any behavior change in config, flow orchestration, task storage, or tool safety
- Prefer unit tests for helpers and mocked integration tests for flow orchestration

## MCP and Remote Workflow

- `run_swarm()` is asynchronous and returns a task ID immediately
- Poll with `swarm_status(task_id)` for final status and summaries
- From the Mac, use `scripts/swarm_remote.py run "feature" --retry N` to dispatch in cursor mode and retry until success; use `update-windows` to pull latest on the Windows repo (and optionally restart the worker) via SSH
- Remote API tasks should be safe for untrusted input: validate paths, repo URLs, and shell-adjacent arguments

## Quick Runtime Matrix

- **Headless (recommended):** Cursor plans/judges, swarm executes phases (`build, review, quality, polish`).
- **Standalone:** Swarm runs planning + execution end-to-end; shipping is only automatic when `AUTO_COMMIT=true`.
- **Remote Ollama on Windows:** set `OLLAMA_BASE_URL` to the Windows Ollama URL; Mac runs orchestration while Windows provides model inference.
- **Cursor worker on Windows:** Mac runs `swarm_remote.py dispatch` or `run` (with `--mode cursor`); Windows runs the cursor worker. Use `swarm_remote.py update-windows` to pull and optionally restart the worker from the Mac.
