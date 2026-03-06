# AI Dev Swarm

A 10-agent coding swarm powered by [CrewAI](https://github.com/crewaiinc/crewAI) and free local [Ollama](https://ollama.com) models. **Cursor AI acts as the commander** (architect + judge), while the swarm handles the grunt work for $0.

## Architecture

```
You (in Cursor) --> Cursor AI plans the work
                        |
                        v
                  MCP: run_swarm(plan)
                        |
                        v
              +--------------------+
              | Worker SwarmFlow   |
              |                    |
              | 1. BUILD           |
              | 2. REVIEW (x3)    |
              | 3. SECURITY        |
              | 4. PERFORMANCE     |
              | 5. TESTS           |
              | 6. LINT            |
              | 7. REFACTOR        |
              | 8. DOCS            |
              +--------------------+
                        |
                        v
              Cursor AI judges output
              Approves or sends back
```

## The 10 Worker Agents

| Agent | Role | What It Does |
|-------|------|-------------|
| React Dev | React / Next.js Engineer | Writes React, Next.js, TypeScript, Tailwind |
| WordPress Dev | WordPress Engineer | Writes PHP, plugins, REST API integrations |
| Shopify Dev | Shopify Engineer | Writes Liquid, Theme Kit, Storefront API |
| Reviewer | Code Reviewer | Critiques code, finds bugs and anti-patterns |
| Security | Security Auditor | Finds OWASP Top 10 vulnerabilities |
| Performance | Performance Engineer | Optimizes Core Web Vitals, bundle size |
| Tester | Test Engineer | Writes Jest, Playwright, pytest tests |
| Refactorer | Refactor Engineer | Cleans code without changing behavior |
| Docs | Documentation Writer | Writes README, docstrings, migration notes |
| Linter | Lint Specialist | Runs and fixes linter errors |

All agents run on **free Ollama models** locally. Cursor AI (which you already pay for) handles the smart planning and judgment.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Ollama and pull a model

```bash
winget install Ollama.Ollama
ollama pull qwen2.5-coder
```

### 3. Configure

```bash
cp .env.example .env
```

Default config uses `ollama/qwen2.5-coder` for all workers. No API keys needed.

### 4. Init git (for auto-commit features)

```bash
git init
```

## Usage

### Via Cursor (recommended -- MCP integration)

1. Enable the **swarm** MCP server in Cursor (Settings → MCP → add config for this repo’s `swarm` server).
2. In chat, describe the feature; Cursor (commander) will plan and call `run_swarm(plan, feature_name, ...)`.
3. Review the swarm’s build summary, review feedback, and quality report, then approve or send back.

### CLI (standalone)

```bash
# Standalone: swarm plans and executes
python run.py "Add product filtering to the Next.js collection page"

# Headless: you supply the plan (e.g. from Cursor)
python run.py --plan plan.md "Add product filtering"
python run.py --plan - "Fix login" < plan.txt

# Options
python run.py --no-commit "Refactor the auth module"
python run.py --dry-run "Add dark mode toggle"
python run.py --builder react_dev "Add a React component"
```

## Troubleshooting

- **Imports or dependencies fail:** Run `pip install -r requirements.txt` and ensure you’re in the repo root with the correct Python env.
- **Windows `charmap` codec errors:** The CLI forces UTF-8 for stdout/stderr on Windows. If you still see encoding errors (e.g. from subprocesses), run with `$env:PYTHONIOENCODING="utf-8"; python run.py ...` (PowerShell) or set `PYTHONIOENCODING=utf-8` in your environment.

## Test Plan

- `pip install -r requirements.txt` succeeds
- `python run.py --help` shows usage
- `python run.py "Add a hello world React component"` runs the full pipeline (requires Ollama or API key)
