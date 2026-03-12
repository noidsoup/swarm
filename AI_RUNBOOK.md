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

## Model configuration

| Variable | Default | Purpose |
|---|---|---|
| `WORKER_MODEL` | `ollama/qwen2.5-coder:7b` | Primary model for all agents |
| `WORKER_FALLBACK_MODEL` | `ollama/gemma3:4b` | Auto-fallback on Ollama runner timeout |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |

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
