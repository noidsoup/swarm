# AI Runbook — Swarm

Operational guide for working with the AI Dev Swarm project.

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

## Cursor smoke test (Mac → Windows)

Use this to verify the cursor worker path works end-to-end.

**1. On Windows** (in the swarm repo, with Ollama running):
```powershell
# Optional: set a short timeout so smoke finishes quickly (default 3600)
$env:WINDOWS_CURSOR_TASK_TIMEOUT = "120"
python scripts/cursor_worker.py --daemon --poll-interval 2 --task-timeout 120 --log-file "$env:TEMP\swarm-worker.log" --pid-file "$env:TEMP\swarm-worker.pid"
```

**2. On Mac** (in the swarm repo; SSH to Windows and env set per `.env` / REMOTE_SETUP.md):
```bash
# Use a small throwaway repo path that exists on Windows (e.g. a clone or temp dir)
python scripts/swarm_remote.py dispatch "cursor smoke test" --mode cursor --repo-path "C:/Users/<you>/AppData/Local/Temp/smoke-repo"
```

**3. Expect:** Command returns with `"status": "complete"` and a short `build_summary`, or a clear `error` (e.g. timeout). Smoke tasks use a minimal prompt (read one file, no edits) so they should finish within the worker timeout.

**4. Stop the worker on Windows** (if needed):
```powershell
$pid = Get-Content "$env:TEMP\swarm-worker.pid" -ErrorAction SilentlyContinue; if ($pid) { Stop-Process -Id $pid -ErrorAction SilentlyContinue }
```

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
