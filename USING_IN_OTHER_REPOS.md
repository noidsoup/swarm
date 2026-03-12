# Using Swarm in Other Repositories

This project is designed to orchestrate work against arbitrary target repos.

## Integration Options

## 1) CLI with `--repo` (fastest path)

From this repo:

```bash
python run.py --repo /path/to/target-repo "Implement feature X"
python run.py --repo /path/to/target-repo --builder react_dev "Implement feature X"
python run.py --repo /path/to/target-repo --no-commit "Implement feature X"
```

Notes:

- `--repo` sets `cfg.repo_root` for this run.
- Auto-commit is **disabled by default** (`AUTO_COMMIT=false`), even without `--no-commit`.
- Use `--plan` for headless mode if you already have a plan.

## 2) Install as a package

```bash
pip install -e /path/to/swarm
```

Then from any location:

```bash
swarm-run --repo /path/to/target-repo "Implement feature X"
swarm-daemon /path/to/target-repo
```

## 3) MCP from Cursor

Configure MCP server to point at this repo's `swarm/mcp_server.py`, then call:

```text
run_swarm(plan, repo_path="/path/to/target-repo", execution_mode="local")
```

You can also use:

- `add_project(...)`
- `run_project_task(...)`
- `spawn_project(...)`

to avoid passing repo metadata each time.

## 4) Remote API / worker mode

If target execution should happen on another machine:

- Run API + worker remotely.
- Dispatch with `execution_mode="ollama"` and optional `repo_url`.
- Poll until completion via API or MCP status tool.

## 5) Cursor transport worker mode

For SSH inbox/outbox dispatch to remote machine:

- Configure `WINDOWS_HOST` and `WINDOWS_USER`.
- Optionally set `WINDOWS_SSH_KEY`.
- Use `execution_mode="cursor"`.

## Suggested Workflows

### A) Local repo with explicit plan

```bash
python run.py --repo /path/to/repo --plan plan.md "Feature name"
```

### B) Cursor commander + project registry

1. `add_project(name, repo_path, builder_type, execution_mode)`
2. `run_project_task(project_name, plan, feature_name)`
3. `swarm_status(task_id)` until terminal status.

### C) Smoke-check remote path

Use a "smoke test" feature/plan phrase to trigger smoke profile in local dispatch logic and validate transport quickly.

## Repo-Specific Configuration

Swarm reads environment via standard dotenv loading (`.env`) and process environment variables.

Recommended pattern per target environment:

- keep environment values in shell profile or `.env`
- set `WORKER_MODEL`, `DEFAULT_EXECUTION_MODE`, and remote variables as needed
- avoid committing credentials

## Constraints and Guardrails

- File operations are repo-root sandboxed.
- Remote worker clone URLs are validated; local/private clone targets are blocked.
- Unknown execution modes are rejected.

## Troubleshooting

- **Changes landed in wrong repo:** verify `--repo` or `repo_path`.
- **Task never finishes:** poll status and inspect `.swarm/runs/<task_id>/events.jsonl`.
- **Unexpected no-commit behavior:** this is default unless `AUTO_COMMIT=true`.
- **Remote clone denied:** use supported public/allowed `repo_url`.
