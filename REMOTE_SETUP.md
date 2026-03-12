# Remote AI Compute Setup

Run the AI Dev Swarm on your Windows PC (GPU), control it from your Mac.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Windows PC (RTX 4070, 12GB VRAM)                   │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  Ollama   │  │  Redis   │  │  Swarm Worker    │  │
│  │  (GPU)    │  │  (queue) │  │  (pulls tasks)   │  │
│  │  :11434   │  │  :6379   │  │                  │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│                                                      │
│  ┌──────────────────┐  ┌─────────────────────────┐  │
│  │  Swarm API        │  │  Monitoring             │  │
│  │  (FastAPI)        │  │  Prometheus + Grafana   │  │
│  │  :9000            │  │  :9090 / :3000          │  │
│  └──────────────────┘  └─────────────────────────┘  │
│                                                      │
│  SSH Server :22                                      │
└───────────────────────────┬─────────────────────────┘
                            │ SSH tunnel
┌───────────────────────────┴─────────────────────────┐
│  Mac (client)                                        │
│                                                      │
│  swarm-remote submit "Build a login page"            │
│  swarm-remote status                                 │
│  swarm-remote logs <task-id>                         │
│  swarm-remote gpu                                    │
│                                                      │
│  OR: Cursor Remote SSH (full interactive mode)       │
└─────────────────────────────────────────────────────┘
```

## Quick Start (Windows — first time)

### 1. SSH Server (run as Admin)

```powershell
# Open PowerShell as Administrator
.\scripts\setup-ssh-server.ps1
```

### 2. Start Docker Desktop

Open Docker Desktop. Ensure:
- WSL2 backend is enabled
- GPU support is enabled (Settings > Resources)

Then verify:

```powershell
# Run as Admin
.\scripts\setup-docker-gpu.ps1
```

### 3. Launch the swarm stack

```powershell
docker compose up -d
```

### 4. Pull models

```bash
bash scripts/pull-models.sh          # just 7b
bash scripts/pull-models.sh --large  # 7b + 14b + 3b
```

### 5. Verify

```bash
# Health check
curl http://localhost:9000/health

# GPU status
curl http://localhost:9000/gpu

# Available models
curl http://localhost:9000/models
```

## Quick Start (Mac — first time)

### 1. Set up SSH + CLI

```bash
# Clone the repo (or just copy scripts/)
git clone https://github.com/noidsoup/swarm.git
cd swarm

# Run the Mac setup (replace IP with your Windows machine)
bash scripts/mac-setup.sh 192.168.1.50 nicho
```

### 2. Connect

```bash
# SSH tunnel (auto-forwards ports 9000, 11434, 3000)
ssh winbox
```

### 3. Submit tasks

```bash
# From a new Mac terminal (while SSH tunnel is running):
python3 scripts/swarm_remote.py submit "Build a dark mode toggle for React"
python3 scripts/swarm_remote.py status
python3 scripts/swarm_remote.py logs swarm-abc123def456
python3 scripts/swarm_remote.py gpu
```

## Docker Services

| Service | Port | Purpose |
|---------|------|---------|
| `ollama` | 11434 | LLM inference (GPU) |
| `redis` | 6379 | Task queue |
| `swarm-api` | 9000 | REST API gateway |
| `swarm-worker` | — | Background task processor |
| `swarm-mcp` | 8000 | MCP server for Cursor |

### With monitoring

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

Adds Prometheus (:9090), Grafana (:3000), and NVIDIA GPU exporter.

Grafana default login: `admin` / `swarm`

## Per-Role Model Configuration

Set env vars to assign different models to different agent roles:

```bash
# .env
WORKER_MODEL=ollama/qwen2.5-coder:7b        # default
PLANNER_MODEL=ollama/qwen2.5-coder:14b       # heavier for planning
REVIEWER_MODEL=ollama/qwen2.5-coder:14b      # heavier for code review
LINTER_MODEL=ollama/qwen2.5-coder:3b         # lightweight for linting
DOCS_MODEL=ollama/qwen2.5-coder:3b           # lightweight for docs
```

## Hardening (after verifying SSH key login works)

```powershell
# Disable password auth — key-only
.\scripts\harden-ssh.ps1

# Auto-start on boot
.\scripts\setup-autostart.ps1
```

## Wake-on-LAN (power on from Mac)

```bash
# Find your Windows MAC address: ipconfig /all (Physical Address)
python3 scripts/wake-on-lan.py AA:BB:CC:DD:EE:FF
```

## Cursor Remote SSH

For full interactive Cursor on the Windows machine:

1. Install "Remote - SSH" extension in Cursor
2. Connect to `winbox` (uses your SSH config)
3. Open `/workspace/<repo>` on the remote
4. All Cursor commands execute on Windows hardware
