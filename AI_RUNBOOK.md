# AI Runbook — Swarm

Operational guide for working with the AI Dev Swarm project.

---

## Offloading AI to Windows

You can use **Ollama** (remote on Windows) or **Cursor AI** from the Mac; a local LLM on Windows is **optional** (one path). See **AGENTS.md → Offloading AI to Windows** for the three paths: (A) Remote Ollama, (B) Cursor/worker on Windows, (C) Cursor AI from Mac with Windows as execution/inference target.

---

## Project layout

```
swarm/
├── swarm/           # Core package: agents, crews, config, worker, api, mcp_server, task_store, task_models
├── scripts/         # Helper scripts: swarm_remote.py, mac-setup.sh, setup-autostart.ps1, setup-ssh-server.ps1
├── tests/           # Pytest tests: test_smoke.py, test_crews.py, test_worker.py
├── run.py           # Standalone CLI entry point
├── daemon.py        # Continuous-improvement watcher
├── docker-compose.yml
├── requirements.txt
├── setup.py         # pip-installable package
├── AGENTS.md        # Always-on agent instructions
├── REMOTE_SETUP.md  # Mac→Windows remote setup guide
└── .cursor/plans/PLAN.md
```

## Running locally (Mac, no GPU)

```bash
pip install -r requirements.txt
export OLLAMA_BASE_URL=http://localhost:11434   # or Windows IP
python run.py --no-commit "Add feature X"
```

## Running remotely (Mac → Windows GPU)

### Prerequisites
- Windows has Ollama installed and serving (port 11434)
- SSH access configured via `~/.ssh/config` (Host `winbox`)
- Port forwarding: 9000 (API), 11434 (Ollama), 3000 (monitoring)

### Start the tunnel
```bash
ssh -fN winbox
```

### Start services on Windows (via SSH)
```bash
ssh winbox "cd repos/swarm && pip install -r requirements.txt && python -m uvicorn swarm.api:app --host 0.0.0.0 --port 9000"
```
The worker starts automatically as a background thread inside the API process.

### Submit a task from Mac
```bash
python scripts/swarm_remote.py submit --feature "Add error handling to API endpoints"
python scripts/swarm_remote.py status <task-id>
python scripts/swarm_remote.py log <task-id>
```

## Get cursor mode working (Mac → Windows)

Goal: Mac dispatches a task; Windows runs the worker and LLM (Ollama), returns the result.

**1. Windows (this machine)**  
- Ollama running and reachable (default: `http://127.0.0.1:11434` is used on Windows when `OLLAMA_BASE_URL` is not set).  
- Smoke repo exists, e.g. `C:\Users\<you>\AppData\Local\Temp\smoke-repo` with a small file (e.g. `README.md`).  
- Start the cursor worker:
  - **Fast (no LLM):** `.\scripts\cursor-worker.ps1 start -Fast` — pipeline check only, returns in ~1 min.  
  - **Real (with LLM):** `.\scripts\cursor-worker.ps1 stop` then `.\scripts\cursor-worker.ps1 start` — 600s task timeout, uses Ollama.  
- Check: `.\scripts\cursor-worker.ps1 status` → "Worker running PID …".

**2. Mac**  
- In the swarm repo: `git pull origin main`.  
- Set env (or use `.env`): `WINDOWS_HOST`, `WINDOWS_USER`, and for SSH auth `WINDOWS_SSH_KEY` (path to key, e.g. `$HOME/.ssh/id_ed25519_nopass`).  
- Optional for long runs: `export WINDOWS_CURSOR_TIMEOUT=800 WINDOWS_CURSOR_HEARTBEAT_TIMEOUT=120`.  
- Dispatch (path must exist on Windows):
  ```bash
  python3 scripts/swarm_remote.py dispatch "cursor smoke test" --mode cursor --repo-path "C:/Users/<you>/AppData/Local/Temp/smoke-repo"
  ```
- Expect: `"status": "complete"` and a `build_summary`. For real run, allow several minutes (up to ~10 with 600s timeout).

**3. If it fails**  
- Timeout on Mac: increase `WINDOWS_CURSOR_TIMEOUT` and `WINDOWS_CURSOR_HEARTBEAT_TIMEOUT`; ensure worker on Windows was started with real mode (no `-Fast`).  
- Timeout on Windows: worker uses 600s by default for real runs; if the build phase still doesn’t finish, set `WINDOWS_CURSOR_TASK_TIMEOUT=900` (or higher) before starting the worker.  
- Ollama not reached: on Windows the default base URL is `http://127.0.0.1:11434`; override with `OLLAMA_BASE_URL` if your Ollama is elsewhere.

---

## Test the whole system

Two ways to test:

**A) Windows-only (single machine)** — Full pipeline on this box (Ollama must be running):
```powershell
cd c:\Users\nicho\repos\swarm
python run.py --no-commit "Add a one-line comment to README.md"
```
Expect: PLAN → BUILD → REVIEW → … (allow several minutes). Check README in the repo you targeted (default: this repo).

**B) Mac → Windows (full offload)** — Mac dispatches, Windows runs the task. Best proof the "whole system" works:
1. **On Windows (you):** Start the worker (see "Cursor smoke test" below). Use fast smoke first: `.\scripts\cursor-worker.ps1 start -Fast`.
2. **On Mac:** Pull latest, set `WINDOWS_HOST`, `WINDOWS_USER`, `WINDOWS_SSH_KEY`, then run:
   `python3 scripts/swarm_remote.py dispatch "cursor smoke test" --mode cursor --repo-path "C:/Users/nicho/AppData/Local/Temp/smoke-repo"`
3. Expect `"status": "complete"` and a short `build_summary` (with fast smoke, within ~1 min).

Smoke repo path on Windows: `C:\Users\nicho\AppData\Local\Temp\smoke-repo` (already has README.md / app.py).

---

## Cursor smoke test (Mac → Windows)

Use this to verify the cursor worker path works end-to-end.

**1. On Windows** (in the swarm repo, with Ollama running):
```powershell
# Smoke can take 3–5 min on first run; use 300s so it can finish (default 3600)
$env:WINDOWS_CURSOR_TASK_TIMEOUT = "300"
python scripts/cursor_worker.py --daemon --poll-interval 2 --task-timeout 300 --log-file "$env:TEMP\swarm-worker.log" --pid-file "$env:TEMP\swarm-worker.pid"
```

**2. On Mac** (in the swarm repo; SSH to Windows and env set per `.env` / REMOTE_SETUP.md):
```bash
# Use a small throwaway repo path that exists on Windows (e.g. a clone or temp dir)
python scripts/swarm_remote.py dispatch "cursor smoke test" --mode cursor --repo-path "C:/Users/<you>/AppData/Local/Temp/smoke-repo"
```

**Mac env required for cursor mode:** `WINDOWS_HOST` and `WINDOWS_USER` must be set (or present in `.env`) when using `--mode cursor`.
```bash
WINDOWS_HOST=192.168.x.x WINDOWS_USER=<windows-user> WINDOWS_SSH_KEY="$HOME/.ssh/id_ed25519_nopass" \
python3 scripts/swarm_remote.py dispatch "cursor smoke test" --mode cursor --repo-path "C:/Users/<you>/AppData/Local/Temp/smoke-repo"
```

**3. Expect:** Command returns with `"status": "complete"` and a short `build_summary`, or a clear `error` (e.g. timeout).

**Fast smoke (no LLM):** On Windows, set `SWARM_SMOKE_SKIP_LLM=1` before starting the worker so the smoke task skips the model and returns immediately. Use this to verify the pipeline end-to-end without waiting for the model. Without it, smoke uses a minimal prompt (read one file, no edits); allow 3–5 minutes or increase the worker timeout.

**4. Start/stop worker (Windows helper):**
```powershell
.\scripts\cursor-worker.ps1 start --fast   # fast smoke (skip LLM, 60s timeout)
.\scripts\cursor-worker.ps1 start          # full smoke (300s timeout)
.\scripts\cursor-worker.ps1 stop
.\scripts\cursor-worker.ps1 status
```
Or manually stop: read PID from `%TEMP%\swarm-worker.pid`, then `Stop-Process -Id <pid> -Force`.

## Model configuration

| Variable | Default | Purpose |
|---|---|---|
| `WORKER_MODEL` | `ollama/qwen2.5-coder:7b` | Primary model for all agents |
| `WORKER_FALLBACK_MODEL` | `ollama/gemma3:4b` | Auto-fallback on Ollama runner timeout |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |

## Context7 and Vercel-skill workflow

- Use `user-context7` for current framework/library docs before implementing version-sensitive changes.
- React/Next.js requests should route through these skills when applicable:
  - `vercel-react-best-practices`
  - `next-best-practices`
  - `next-cache-components`
  - `next-upgrade` for migrations
- Vercel deployment requests should use `vercel-deploy` and default to preview deploys.

## Orchestrator-skill workflow

- For orchestration internals (`swarm/flow.py`, `swarm/worker.py`, `swarm/task_store.py`, `swarm/task_models.py`), apply:
  - `python-error-handling`
  - `python-resilience`
  - `python-observability`
  - `python-performance-optimization` when throughput/latency is part of the request
- For `tests/**` changes, apply `python-testing-patterns`.
- For MCP surface changes (`swarm/mcp_server.py`, `swarm/tools/**`), apply `mcp-builder`.
- For API design/contract changes in `swarm/api.py`, apply `api-design-principles`.
- For CI workflow edits (`.github/workflows/**`), apply `github-actions-templates`.

## Agent guidance artifacts

- Frontend/framework guidance rule: `.cursor/rules/context7-vercel.mdc`
- Core orchestrator guidance rule: `.cursor/rules/orchestrator-skills.mdc`
- Primary project instructions: `AGENTS.md`
- Session continuity log: `AI_SESSION_MEMORY.md`

When updating workflow conventions, keep these files in sync so future sessions inherit the same defaults.

## Read memory for next steps

To surface the latest next steps from session memory, handoffs, and the plan (no SimpleMem backend required):

```bash
python simplemem_cli.py next-steps
```

Optional: `--repo-root .` (default) or another path. Output includes:

- **Next steps** from the last entries in `AI_SESSION_MEMORY.md`
- **Immediate Next Steps** and **Resume Advice** from the latest handoff in `.claude/handoffs/` or `.cursor/handoffs/`
- **Pending plan items** (unchecked `- [ ]` lines) from `.cursor/plans/PLAN.md`

## Testing

```bash
python -m pytest tests/ -v
```

Key test files:
- `tests/test_smoke.py` — import sanity
- `tests/test_crews.py` — CrewAI crew construction (no async mutation)
- `tests/test_worker.py` — Ollama fallback retry logic

## Common issues

| Symptom | Fix |
|---|---|
| `OllamaException - timed out waiting for llama runner to start` | Automatic: worker retries with `WORKER_FALLBACK_MODEL`. Manual: `ollama stop` then `ollama serve` on Windows |
| `charmap codec can't encode character` (Windows) | Set `PYTHONIOENCODING=utf-8` or use `run.py` which auto-wraps stdout |
| `bind [127.0.0.1]:9000: Address already in use` | Kill existing SSH tunnel: `lsof -ti:9000 \| xargs kill` |
| Cursor mode poll intermittently hangs with `winbox` alias | If `winbox` has `LocalForward` entries and a tunnel is already active, prefer `WINDOWS_HOST=<windows-ip>` + `WINDOWS_SSH_KEY=...` for dispatches (avoids forward-bind noise during repeated SSH polls) |
| Pytest collects `TestTool` as test class | Already fixed: renamed to `RunTestsTool` |
| CrewAI "must end with at most one async task" | Already fixed: `quality_crew` no longer forces async |

## Windows autostart (persistent across reboots)

Run on Windows (Admin PowerShell):
```powershell
.\scripts\setup-autostart.ps1
```
Creates a scheduled task `SwarmDockerComposeUp` that starts Docker Desktop and `docker compose up -d` on user login.

## Security notes
- Never commit SSH keys or `.env` files (`.gitignore` blocks them)
- `id_ed25519_nopass` is used for non-interactive agent sessions; keep it out of git
- `administrators_authorized_keys` on Windows controls SSH access
