# AI Runbook - Swarm

Operational reference for running and debugging the swarm across local and remote setups.

## 1) Runtime Modes

- **Standalone CLI:** `run.py` handles planning + execution (`FullSwarmFlow`).
- **Headless CLI:** you provide plan; worker phases run (`WorkerSwarmFlow`).
- **MCP mode:** Cursor calls `run_swarm()` and polls `swarm_status()`.
- **Remote API mode (`ollama`):** dispatch to `swarm/api.py` and queue worker.
- **Cursor worker mode (`cursor`):** SSH-based inbox/outbox transport.

## 2) Phase Model

Worker pipeline:

```text
BUILD -> REVIEW LOOP (with FIX) -> QUALITY -> POLISH
```

Standalone adds:

```text
PLAN -> ...worker pipeline... -> SHIP (if AUTO_COMMIT=true)
```

Important: quality and polish crews are sequential in current implementation.

## 3) Core Commands

### Local CLI

```bash
python run.py "Implement feature X"
python run.py --plan plan.md "Implement feature X"
python run.py --only build,review --plan plan.md "Implement feature X"
python run.py --skip polish "Implement feature X"
python run.py --no-commit "Implement feature X"
python run.py --dry-run "Implement feature X"
```

### Packaged CLIs

```bash
swarm-run "Implement feature X"
swarm-daemon /path/to/repo
```

### API server + worker

```bash
uvicorn swarm.api:app --host 0.0.0.0 --port 9000
python -m swarm.worker
```

## 4) Remote / Windows Offload

This repo supports three patterns:

- **A. Remote inference only:** set `OLLAMA_BASE_URL` to Windows host, run swarm locally.
- **B. Remote queue worker:** run API + worker on Windows, dispatch via `execution_mode=ollama`.
- **C. Cursor transport worker:** run cursor worker service on Windows, dispatch via `execution_mode=cursor`.

### Cursor mode required env vars (dispatcher side)

- `WINDOWS_HOST`
- `WINDOWS_USER`
- optional: `WINDOWS_SSH_KEY`, `WINDOWS_CURSOR_WORKSPACE`

Timeout knobs:

- `WINDOWS_CURSOR_TIMEOUT`
- `WINDOWS_CURSOR_HEARTBEAT_TIMEOUT`
- `WINDOWS_CURSOR_TASK_TIMEOUT` (worker side)

## 5) MCP Operations

From `swarm/mcp_server.py`, supported tools:

- `run_swarm(plan, feature_name, builder_type, repo_path, repo_url, execution_mode)`
- `swarm_status(task_id)`
- `list_agents()`
- `list_projects()`
- `add_project(...)`
- `remove_project(name)`
- `run_project_task(project_name, plan, feature_name)`
- `spawn_project(name, description, template, repo_path)`

`run_swarm()` is asynchronous and returns a task ID immediately.

## 6) REST API Operations

Endpoints in `swarm/api.py`:

- `POST /tasks`: create queued task.
- `GET /tasks`: list tasks.
- `GET /tasks/{task_id}`: full task payload and summaries.
- `GET /tasks/{task_id}/log`: SSE stream of task log lines + terminal done event.
- `DELETE /tasks/{task_id}`: mark task cancelled.
- `GET /health`: Ollama and task-store health summary.
- `GET /models`: Ollama model list.
- `GET /gpu`: `nvidia-smi` snapshot.

## 7) Task Lifecycle and Store

Status enum (`swarm/task_models.py`):

- `queued`
- `running`
- `completed`
- `failed`
- `cancelled`

Store backend (`swarm/task_store.py`):

- Uses Redis when `REDIS_URL` is set and reachable.
- Falls back to in-memory store if Redis is unavailable.
- Queue source is Redis list in Redis mode; in-memory scan in fallback mode.

## 8) Artifact Layout

Per-task artifacts live at:

```text
<repo-root>/.swarm/runs/<task_id>/
```

Canonical files:

- `context.json`
- `retrieval.json`
- `validation.json`
- `eval.json`
- `events.jsonl`
- `build_phase.log`

These are created by worker/MCP orchestration and are the primary debugging source for run behavior.

## 9) Config and Defaults

Primary defaults from `swarm/config.py`:

- `WORKER_MODEL`: `ollama/qwen2.5-coder:7b`
- `AUTO_COMMIT`: `false`
- `BRANCH_PREFIX`: `swarm/`
- `MAX_REVIEW_LOOPS`: `3` (via runtime config object)
- `OLLAMA_BASE_URL` default:
  - Windows: `http://127.0.0.1:11434`
  - non-Windows: `http://localhost:11434`
- `DEFAULT_EXECUTION_MODE`: `local`

## 10) Troubleshooting Matrix

- **Stuck or slow remote run**
  - Check `SWARM_REMOTE_TIMEOUT` and backend health.
  - Poll task status directly (`GET /tasks/{id}` or `swarm_status()`).
- **Cursor mode timeout**
  - Increase `WINDOWS_CURSOR_TIMEOUT`.
  - Check outbox heartbeat updates and `WINDOWS_CURSOR_HEARTBEAT_TIMEOUT`.
- **Ollama runner startup timeout**
  - Worker can retry with `WORKER_FALLBACK_MODEL`.
  - Confirm Ollama is serving and model exists.
- **No artifacts produced**
  - Verify repo path exists and worker can write to `<repo>/.swarm/runs`.
- **Unexpected commit behavior**
  - Default is no auto-commit (`AUTO_COMMIT=false`).
- **`repo_url` clone rejected**
  - Worker blocks local/private targets by design.

## 11) Safety and Trust Boundaries

- Repo-root containment is enforced for file tool paths.
- Task artifact paths are sanitized by task ID.
- Write protection guard prevents no-overlap full-file rewrite by default.
- Remote clone URLs are validated against local/private hosts.
- Execution-mode allowlist blocks unknown backends.

## 12) Recommended Verification Routine

When changing runtime/orchestration behavior:

```bash
ruff check swarm tests run.py daemon.py setup.py simplemem_client.py simplemem_cli.py
pytest
```

When changing docs only:

- Manually verify command examples and default values against:
  - `swarm/config.py`
  - `run.py`
  - `swarm/mcp_server.py`
  - `swarm/api.py`
