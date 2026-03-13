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

### Windows "ready" sequence for real cursor runs

Run this on Windows every time before Mac dispatches a real task:

```powershell
cd C:\Users\<you>\repos\swarm
git checkout main
git pull

.\scripts\cursor-worker.ps1 stop
$env:WINDOWS_CURSOR_TASK_TIMEOUT = "1800"
Remove-Item Env:SWARM_SMOKE_SKIP_LLM -ErrorAction SilentlyContinue
.\scripts\cursor-worker.ps1 start
.\scripts\cursor-worker.ps1 status
```

Expected:

- Worker status prints `Worker running PID ...`
- Start output reflects the timeout from your env (for example `1800s`), not a forced `600s`

Optional diagnostics:

```powershell
echo $env:WINDOWS_CURSOR_TASK_TIMEOUT
Get-Content "$env:TEMP\swarm-worker.log" -Tail 120
```

Then dispatch from Mac:

```bash
WINDOWS_CURSOR_TIMEOUT=900 WINDOWS_CURSOR_HEARTBEAT_TIMEOUT=180 WINDOWS_SSH_KEY="$HOME/.ssh/id_ed25519_nopass" WINDOWS_HOST=<windows-ip> WINDOWS_USER=<windows-user> python3 scripts/swarm_remote.py dispatch "<task prompt>" --mode cursor --repo-path "C:/Users/<you>/AppData/Local/Temp/smoke-repo"
```

Cursor-mode dispatch is async-first by default:

- Default (recommended): returns quickly with `task_id`
- Blocking mode: add `--wait`
- Compatibility: `--async` is accepted but not required for cursor mode

Examples:

```bash
# async-first (default)
python3 scripts/swarm_remote.py dispatch "Add a tiny append-only note to README" --mode cursor --repo-path "C:/Users/<you>/AppData/Local/Temp/smoke-repo"

# blocking until completion
python3 scripts/swarm_remote.py dispatch "Add a tiny append-only note to README" --mode cursor --wait --repo-path "C:/Users/<you>/AppData/Local/Temp/smoke-repo"
```

### Detailed Windows operator instructions (copy/paste)

Use this full sequence when you want Windows to be the execution machine and avoid stale worker state.

1) **Open PowerShell on Windows and refresh repo**

```powershell
cd C:\Users\<you>\repos\swarm
git checkout main
git pull
```

2) **Hard-stop old worker and clear smoke mode**

```powershell
.\scripts\cursor-worker.ps1 stop
Remove-Item Env:SWARM_SMOKE_SKIP_LLM -ErrorAction SilentlyContinue
```

3) **Set real-run timeout in the current shell**

```powershell
$env:WINDOWS_CURSOR_TASK_TIMEOUT = "1800"
echo $env:WINDOWS_CURSOR_TASK_TIMEOUT
```

4) **Start worker and verify**

```powershell
.\scripts\cursor-worker.ps1 start
.\scripts\cursor-worker.ps1 status
```

Expected output:
- `Started worker PID ... (timeout 1800s)` (or whatever you set)
- `Worker running PID ...`

5) **Watch logs while Mac task runs (optional but recommended)**

```powershell
Get-Content "$env:TEMP\swarm-worker.log" -Wait
```

6) **After Mac dispatch returns, verify result payload exists**

```powershell
Get-ChildItem "$HOME\.swarm\outbox" | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name,LastWriteTime
```

7) **If still timing out at 600s**

- You are likely running an old process or old script copy.
- Repeat steps 1-4 and confirm start output prints your timeout value, not `600s`.
- If needed, kill stale process manually, then restart:

```powershell
Get-Process python | Where-Object { $_.Path -like "*python*" } | Select-Object Id,ProcessName,Path
# then stop the specific stale PID only if it is the old worker
Stop-Process -Id <pid> -Force
```

8) **If worker starts but tasks still fail**

- Confirm Ollama is reachable on Windows:

```powershell
curl http://127.0.0.1:11434/api/tags
```

- Check worker log tail for model load/runtime errors:

```powershell
Get-Content "$env:TEMP\swarm-worker.log" -Tail 200
```

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
