# AI Dev Swarm

`swarm` is an AI coding orchestrator. Cursor acts as the commander, and this repo runs a deterministic worker pipeline to implement, review, and harden code changes.

## What This Project Is

- **Commander model:** Cursor plans work and judges outcomes.
- **Worker runtime:** This repo executes BUILD -> REVIEW LOOP -> QUALITY -> POLISH.
- **Execution backends:** `local`, `ollama` (remote API worker), and `cursor` (SSH inbox/outbox worker).
- **Primary use case:** run coding tasks end-to-end with repeatable phases, artifacts, and status polling.

## Current Architecture

```text
Cursor (commander)
  -> MCP tool: run_swarm(plan, ...)
  -> Dispatcher chooses execution_mode
       local   -> WorkerSwarmFlow in-process
       ollama  -> POST /tasks to remote swarm API + poll
       cursor  -> SSH inbox/outbox transport to remote cursor worker
  -> Returns structured result + artifacts path
```

Worker flow (`WorkerSwarmFlow`) is:

```text
BUILD -> REVIEW (loop with FIX) -> QUALITY GATES -> POLISH -> COMPLETE
```

Standalone CLI flow (`FullSwarmFlow`) adds planning and optional shipping:

```text
PLAN -> BUILD -> REVIEW LOOP -> QUALITY -> POLISH -> SHIP (only if AUTO_COMMIT=true)
```

## Worker Agent Roster (11)

Builders:

- `python_dev`
- `react_dev`
- `wordpress_dev`
- `shopify_dev`

Review / quality / polish:

- `reviewer`
- `security`
- `performance`
- `tester`
- `linter_agent`
- `refactorer`
- `docs`

Builder selection is automatic from request/plan keywords unless overridden with `builder_type` or `--builder`.

## Key Features

- **Deterministic phase pipeline:** shared flow methods in `swarm/flow.py`.
- **Review loop routing:** loops until `APPROVED` or `max_review_loops`.
- **Context + retrieval packs:** built before execution and persisted to artifacts.
- **Validation gates:** preflight and postflight checks in worker mode.
- **Adaptive retries:** fallback model retry for Ollama runner startup timeouts.
- **Multi-backend dispatch:** local runtime, remote API queue worker, or cursor transport worker.
- **Task persistence:** Redis queue when available with in-memory fallback.
- **Per-run artifacts:** canonical run directory under `.swarm/runs/<task_id>/`.
- **Project registry + templates:** register projects and scaffold from templates via MCP.

## Entry Points

- `run.py` - local CLI for standalone or headless runs.
- `swarm/mcp_server.py` - MCP surface for Cursor.
- `swarm/api.py` - remote FastAPI task gateway.
- `swarm/worker.py` - background queue worker.
- `daemon.py` and `swarm/daemon_cli.py` - continuous improvement daemon.

## Installation

```bash
pip install -r requirements.txt
```

Optional editable install:

```bash
pip install -e .
```

## Configuration

Core environment variables:

- `WORKER_MODEL` (default `ollama/qwen2.5-coder:7b`)
- `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434` on Windows, `http://localhost:11434` otherwise)
- `AUTO_COMMIT` (default `false`)
- `BRANCH_PREFIX` (default `swarm/`)
- `DEFAULT_EXECUTION_MODE` (`local`, `ollama`, `cursor`)
- `WINDOWS_HOST`, `WINDOWS_USER`, `WINDOWS_SSH_KEY`, `WINDOWS_SWARM_API`, `WINDOWS_CURSOR_WORKSPACE`

Per-role model overrides are supported (`PLANNER_MODEL`, `REVIEWER_MODEL`, `BUILDER_MODEL`, etc.).

## Usage

### 1) Local standalone (swarm plans + executes)

```bash
python run.py "Add request tracing to API handlers"
```

### 2) Headless (you provide the plan)

```bash
python run.py --plan plan.md "Add request tracing to API handlers"
python run.py --plan - "Fix flaky test retries" < plan.txt
```

### 3) Run selected phases

```bash
python run.py --only build,review --plan plan.md "Feature task"
python run.py --skip polish "Feature task"
```

### 4) MCP (recommended with Cursor)

Configure Cursor MCP to run:

- command: `python`
- args: `["/absolute/path/to/swarm/swarm/mcp_server.py"]`

Then call:

- `run_swarm(...)`
- `swarm_status(task_id)`
- `list_agents()`
- project tools (`list_projects`, `add_project`, `run_project_task`, `spawn_project`)

### 5) Remote API mode (`execution_mode=ollama`)

Run API + worker on remote host (or Docker), then dispatch and poll.

### 6) Cursor worker mode (`execution_mode=cursor`)

Use SSH inbox/outbox transport with `CursorWorkerClient` and `CursorWorkerService`. From the Mac, use `scripts/swarm_remote.py`:

- **dispatch** — submit a task (async by default); `--wait` to block.
- **run** — cursor-only: dispatch, poll until done, and retry on failure (e.g. `--retry 5`).
- **update-windows** — SSH to Windows and run `git pull` in the swarm repo; `--restart-worker` to restart the cursor worker.
- **status** / **logs** / **cancel** — track or cancel by `task_id`.

Requires `WINDOWS_HOST`, `WINDOWS_USER` (and optionally `WINDOWS_SSH_KEY`). See `AI_RUNBOOK.md` for full sequences.

## API Surface (Remote Gateway)

From `swarm/api.py`:

- `POST /tasks`
- `GET /tasks`
- `GET /tasks/{task_id}`
- `GET /tasks/{task_id}/log` (SSE)
- `DELETE /tasks/{task_id}`
- `GET /health`
- `GET /models`
- `GET /gpu`

## Artifacts and Observability

Each run writes under:

```text
<repo>/.swarm/runs/<task_id>/
```

Canonical files:

- `context.json`
- `retrieval.json`
- `validation.json`
- `eval.json`
- `events.jsonl`
- `build_phase.log`

Task records also include summaries (`context_summary`, `retrieval_summary`, `validation_summary`, `eval_summary`, `adaptation_summary`) and comparison/lessons fields.

## Safety Model

- File tools enforce repo-root path containment.
- Artifact paths validate task IDs and prevent traversal.
- Git helper uses arg-list subprocess calls (`shell=False`).
- Worker blocks private/local `repo_url` targets for remote clones.
- `WriteFile` blocks destructive no-overlap rewrites by default unless explicitly overridden via `SWARM_ALLOW_NO_OVERLAP_REWRITE=true`.

## Testing and Verification

Run full checks:

```bash
ruff check swarm tests run.py daemon.py setup.py simplemem_client.py simplemem_cli.py
pytest
```

High-value test areas:

- flow/review loop behavior
- dispatch mode routing
- task-store fallback semantics
- run artifact path safety
- tool safety contracts
- worker retry and adaptation behavior

## Documentation Map

- `AGENTS.md` - always-on agent instructions and operational truths.
- `AI_RUNBOOK.md` - operator handbook and troubleshooting.
- `AI_FEATURE_MAP.md` - module-by-module capability index for AI agents.
- `COMMANDER_LOOP.md` - detailed review-loop and phase routing behavior.
- `USING_IN_OTHER_REPOS.md` - multi-repo integration patterns.
