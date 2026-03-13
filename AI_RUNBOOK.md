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

**Ready for real dev (quick check):** On Windows run `.\scripts\cursor-worker.ps1 status` (worker running). On Mac run a dispatch with `--mode cursor` and your repo path; use `status <task_id>` / `logs <task_id>` to track. Default task timeout is 3600s.

### swarm_remote commands (Mac-side)

All require `WINDOWS_HOST` and `WINDOWS_USER` for cursor mode; optional `WINDOWS_SSH_KEY`.

| Command | Description |
|--------|-------------|
| `dispatch "feature"` | Submit task (async by default); use `--wait` to block. |
| `run "feature" [--retry N]` | Cursor-only: dispatch, poll until done, retry on failure until success. |
| `update-windows [--restart-worker]` | SSH to Windows: `git checkout main && git pull`; optionally restart cursor worker. |
| `status [task_id]` | Show task status (or list all). Falls back to cursor outbox if API unreachable. |
| `logs <task_id>` | Stream or poll task logs. |
| `cancel <task_id>` | Cancel a queued or in-flight task. |

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

### Update Windows from Mac (git pull via SSH)

From the Mac, pull latest on the Windows swarm repo (and optionally restart the worker):

```bash
WINDOWS_HOST=<windows-ip> WINDOWS_USER=<windows-user> python3 scripts/swarm_remote.py update-windows
# Optional: restart cursor worker after pull
WINDOWS_HOST=... WINDOWS_USER=... python3 scripts/swarm_remote.py update-windows --restart-worker
```

Uses `WINDOWS_SSH_KEY` if set; runs `git checkout main && git pull` in the Windows repo (default `C:\Users\<user>\repos\swarm`). Override path with `--repo-path "C:\\Users\\you\\repos\\swarm"`.

### Windows "ready" sequence for real cursor runs

Run this on Windows before Mac dispatches a real task. Default task timeout is **3600s**; override only if you need longer:

```powershell
cd C:\Users\<you>\repos\swarm
git checkout main
git pull

.\scripts\cursor-worker.ps1 stop
Remove-Item Env:SWARM_SMOKE_SKIP_LLM -ErrorAction SilentlyContinue
# Optional: $env:WINDOWS_CURSOR_TASK_TIMEOUT = "7200"   # for very long runs
.\scripts\cursor-worker.ps1 start
.\scripts\cursor-worker.ps1 status
```

Expected:

- Worker status prints `Worker running PID ...`
- Start output shows timeout (default **3600s** for real runs; override with `$env:WINDOWS_CURSOR_TASK_TIMEOUT`)

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

# run until success (dispatch + poll + retry on failure, cursor only)
python3 scripts/swarm_remote.py run "Add a tiny append-only note to README" --repo-path "C:/Users/<you>/repos/swarm" --retry 5
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

3) **Optional: set longer timeout** (default is 3600s)

```powershell
# Only if you need > 1 hour per task:
$env:WINDOWS_CURSOR_TASK_TIMEOUT = "7200"
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

### Windows agent: copy/paste execution flow (long tasks)

Use this exact flow when delegating work to the Windows agent and you want reliable completion for 30-90 minute tasks.

1) **Prepare Windows worker shell**

```powershell
cd C:\Users\<you>\repos\swarm
git checkout main
git pull
.\scripts\cursor-worker.ps1 stop
Remove-Item Env:SWARM_SMOKE_SKIP_LLM -ErrorAction SilentlyContinue
$env:WINDOWS_CURSOR_TASK_TIMEOUT = "3600"
.\scripts\cursor-worker.ps1 start
.\scripts\cursor-worker.ps1 status
```

2) **Submit from Mac (async-first)**

```bash
WINDOWS_CURSOR_TIMEOUT=7200 \
WINDOWS_CURSOR_HEARTBEAT_TIMEOUT=600 \
WINDOWS_SSH_KEY="$HOME/.ssh/id_ed25519_nopass" \
WINDOWS_HOST=<windows-ip> \
WINDOWS_USER=<windows-user> \
scripts/remote-dev-mac.sh dispatch "<task prompt>" --mode cursor --repo-path "C:/Users/<you>/AppData/Local/Temp/smoke-repo"
```

3) **Track run from Mac**

```bash
WINDOWS_SSH_KEY="$HOME/.ssh/id_ed25519_nopass" WINDOWS_HOST=<windows-ip> WINDOWS_USER=<windows-user> scripts/remote-dev-mac.sh status <task_id>
WINDOWS_SSH_KEY="$HOME/.ssh/id_ed25519_nopass" WINDOWS_HOST=<windows-ip> WINDOWS_USER=<windows-user> scripts/remote-dev-mac.sh logs <task_id>
WINDOWS_SSH_KEY="$HOME/.ssh/id_ed25519_nopass" WINDOWS_HOST=<windows-ip> WINDOWS_USER=<windows-user> scripts/remote-dev-mac.sh cancel <task_id>
```

4) **If `status` endpoint is unreachable from Mac**

Directly inspect queue files on Windows over SSH:

```bash
ssh -i "$HOME/.ssh/id_ed25519_nopass" <windows-user>@<windows-ip> "python -c \"from pathlib import Path; import json; p=Path('~/.swarm/outbox/<task_id>.json').expanduser(); print(json.loads(p.read_text(encoding='utf-8')).get('status') if p.exists() else 'MISSING')\""
```

5) **If task hits 600s timeout error**

- Root cause is worker-side cap (`WINDOWS_CURSOR_TASK_TIMEOUT`), not polling.
- Restart worker with higher timeout in the same shell:

```powershell
.\scripts\cursor-worker.ps1 stop
$env:WINDOWS_CURSOR_TASK_TIMEOUT = "3600"
.\scripts\cursor-worker.ps1 start
```

6) **Post-run verification**

- Confirm terminal status in outbox (`complete`/`error`).
- Confirm file content change directly in target repo.
- If prompt required "exactly one line appended", verify no duplicate appended lines before marking success.

7) **"I/O operation on closed file" on Windows**

- The worker runs as a daemon child with stdout/stderr redirected to a log file; something may still write to a closed stream.
- To see the full traceback: on Windows, stop the daemon (`.\\scripts\\cursor-worker.ps1 stop`), put one task in the inbox (dispatch from Mac without `--wait`), then run `python scripts/cursor_worker.py --once` in a console. The exception and traceback will print to the console.
- Check the daemon log: `Get-Content "$env:TEMP\\swarm-worker.log" -Tail 200`.

### Windows agent: apply latest Mac-side status/cancel reliability fixes

Use this when the Mac can dispatch tasks but `status`/`cancel` intermittently fail due to API transport resets.

1) **Pull latest on Windows**

```powershell
cd C:\Users\<you>\repos\swarm
git checkout main
git pull
```

2) **Restart cursor worker in a fresh shell**

```powershell
.\scripts\cursor-worker.ps1 stop
Remove-Item Env:SWARM_SMOKE_SKIP_LLM -ErrorAction SilentlyContinue
$env:WINDOWS_CURSOR_TASK_TIMEOUT = "3600"
.\scripts\cursor-worker.ps1 start
.\scripts\cursor-worker.ps1 status
```

3) **Run Mac-side async submit (from Mac)**

```bash
WINDOWS_CURSOR_TIMEOUT=7200 \
WINDOWS_CURSOR_HEARTBEAT_TIMEOUT=600 \
WINDOWS_SSH_KEY="$HOME/.ssh/id_ed25519_nopass" \
WINDOWS_HOST=<windows-ip> \
WINDOWS_USER=<windows-user> \
scripts/remote-dev-mac.sh dispatch "<task prompt>" --mode cursor --repo-path "C:/Users/<you>/AppData/Local/Temp/smoke-repo"
```

4) **Track from Mac (now resilient to API connection resets)**

```bash
WINDOWS_SSH_KEY="$HOME/.ssh/id_ed25519_nopass" WINDOWS_HOST=<windows-ip> WINDOWS_USER=<windows-user> scripts/remote-dev-mac.sh status <task_id>
WINDOWS_SSH_KEY="$HOME/.ssh/id_ed25519_nopass" WINDOWS_HOST=<windows-ip> WINDOWS_USER=<windows-user> scripts/remote-dev-mac.sh logs <task_id>
WINDOWS_SSH_KEY="$HOME/.ssh/id_ed25519_nopass" WINDOWS_HOST=<windows-ip> WINDOWS_USER=<windows-user> scripts/remote-dev-mac.sh cancel <task_id>
```

What changed:
- `status/logs/cancel` now fall back to cursor outbox/inbox tracking when API calls fail with transport-level `httpx` errors (not only 404).
- queued-task cancel path was hardened in cursor worker remote script generation.

5) **Quick verification checklist**

- `dispatch` returns queued `task_id` quickly.
- `status <task_id>` returns a cursor payload even if API is unreachable.
- `cancel <task_id>` succeeds for queued tasks.
- Windows queue files are consistent:
  - `~/.swarm/inbox/<task_id>.json` removed on queued cancel
  - `~/.swarm/outbox/<task_id>.json` contains terminal status.

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
- `PARALLEL_QUALITY`: `false` (set `true` to run quality-agent checks in parallel local flow)
- `SWARM_API_TOKEN`: empty by default; when set, API requires `Authorization: Bearer <token>` except `/health`, `/docs`, `/openapi.json`
- `SWARM_LOG_FORMAT`: `text` by default; set to `json` for structured JSON logs

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

Additional local verification used for smoke transport checks without model calls:

```bash
SWARM_SMOKE_SKIP_LLM=1 python3 - <<'PY'
from swarm.config import cfg
from swarm.dispatch import Dispatcher
print(Dispatcher(cfg).dispatch(
    plan='cursor smoke test',
    feature_name='cursor smoke test',
    builder_type='python_dev',
    repo_path='.',
    execution_mode='local',
)["build_summary"])
PY
```

## 13) 2026-03-13 Hardening Updates

- Worker execution path is now step-based (`RunContext`) instead of a single monolithic `_run_swarm` body.
- Error handling uses typed exceptions in `swarm/errors.py` for clearer failure semantics.
- Worker supports graceful shutdown (`SIGTERM`, `SIGINT`) and retains partial results before postflight fail paths.
- Local dispatch now uses per-run config copies and temporary module cfg override binding to prevent process-global config drift.
- API supports bearer-token auth via `SWARM_API_TOKEN`.
- Repo URL validation now resolves DNS and blocks hosts resolving to private/loopback IPs.
- Logging supports text/json formatting switch (`SWARM_LOG_FORMAT`), and flow phase timing is emitted in logs.

When changing docs only:

- Manually verify command examples and default values against:
  - `swarm/config.py`
  - `run.py`
  - `swarm/mcp_server.py`
  - `swarm/api.py`
