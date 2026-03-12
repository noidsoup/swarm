# AI Feature Map

Comprehensive feature index for AI agents working in this repository.

## Purpose

Use this document as the high-signal map of what exists, where behavior is implemented, and what invariants are already covered by tests.

## System Model

- **Commander:** external (Cursor) plans/judges.
- **Workers:** this repo executes orchestration and quality phases.
- **Execution surfaces:** CLI, MCP tools, REST API, background worker, cursor transport worker.

## Feature Inventory by Module

## Orchestration Core

- `swarm/flow.py`
  - `BaseSwarmFlow` shared phase logic.
  - `WorkerSwarmFlow` headless pipeline.
  - `FullSwarmFlow` standalone pipeline with planning and optional ship.
  - review router logic (`APPROVED` check + max loop cutoff).
  - phase subset execution (`run_selected_phases`).
  - build-phase checkpoint logging to artifacts.

- `swarm/agents.py`
  - constructs 11 worker agents.
  - role-specific model lookup through config.
  - tool access partitioning by role.

- `swarm/crews.py`
  - single-agent crews for plan/build/review/fix.
  - sequential quality crew for quality and polish phases.

- `swarm/tasks.py`
  - prompt/task factories for each phase.

## Worker Runtime, Learning, and Validation

- `swarm/worker.py`
  - queue consumption and task lifecycle transitions.
  - workspace prep and repo clone validation.
  - context pack generation.
  - adaptation strategy selection and fallback retries.
  - retrieval pack generation.
  - preflight/postflight validation.
  - eval report generation and lesson writeback.
  - artifact file persistence and event ledger.

- `swarm/context_pack.py`
  - stack/framework/language inference.
  - builder hint inference for routing support.

- `swarm/retrieval.py`
  - retrieval pack from repository signals.

- `swarm/adaptation.py`
  - adaptation strategies from prior-run signals.
  - optional builder override and strict-validation behavior.

- `swarm/validation.py`
  - preflight and postflight checks with pass/warn/fail semantics.

- `swarm/evals.py`
  - structured event scoring and comparison with recent runs.

## Dispatch and Multi-Backend Execution

- `swarm/dispatch.py`
  - execution mode allowlist: `local`, `ollama`, `cursor`.
  - local dispatch into in-process worker flow.
  - remote API dispatch and polling.
  - cursor transport dispatch via SSH client.
  - smoke-task fast path profile.

- `swarm/cursor_worker.py`
  - SSH client for inbox/outbox task transport.
  - cursor worker service for task execution with heartbeat + timeout.
  - daemon spawn helpers for persistent worker process.

## Task and API Surfaces

- `swarm/task_models.py`
  - canonical request/result payload schemas.
  - status enum: queued/running/completed/failed/cancelled.

- `swarm/task_store.py`
  - Redis-backed queue + state store.
  - in-memory fallback when Redis unavailable.

- `swarm/api.py`
  - task submission/list/status/cancel endpoints.
  - SSE log streaming endpoint.
  - health/models/gpu endpoints.

- `swarm/mcp_server.py`
  - MCP tools: run/status/agents/project management.
  - async run registry and polling model.
  - artifact + eval enrichment on results.

## Project and Template Management

- `swarm/projects.py`
  - project registry persistence under `~/.swarm/projects.yaml`.
  - project create/update/remove/list.
  - template-based project scaffold generation.

- `templates/projects/*`
  - starter templates for new project scaffolds.

## Tooling and Safety Features

- `swarm/tools/file_tool.py`
  - repo-root path sandbox.
  - read/write/list directory operations.
  - no-overlap rewrite guard for existing files.

- `swarm/tools/git_tool.py`
  - git status/diff/commit/branch/log wrappers.

- `swarm/tools/lint_tool.py`
  - auto-detect lint command and run/fix.

- `swarm/tools/test_tool.py`
  - auto-detect test command and execute.

- `swarm/tools/shell_tool.py`
  - bounded-time shell command execution in repo context.

- `swarm/run_artifacts.py`
  - task-id sanitization.
  - canonical artifact path + file map generation.

## CLI and Daemon Entry Points

- `run.py`
  - standalone/headless CLI with phase selection.
  - builder override and repo targeting.
  - dry-run and verbosity controls.

- `swarm/cli.py`
  - package entrypoint wrapper for `run.py`.

- `daemon.py`, `swarm/daemon_cli.py`, `swarm/background_loop.py`, `swarm/watcher.py`
  - continuous improvement loop and file watcher driven operations.

## Artifact Contract

Per run directory:

```text
<repo>/.swarm/runs/<task_id>/
  context.json
  retrieval.json
  validation.json
  eval.json
  events.jsonl
  build_phase.log
```

Task payloads may include:

- context/retrieval/validation/eval/adaptation summaries
- lessons and comparison fields
- artifacts_dir path

## Behavior Invariants (from tests)

## Orchestration/runtime

- Review loop routing and termination behavior are asserted.
- Dispatch mode routing and local working-dir behavior are asserted.
- Artifact directory wiring in dispatch/flow is asserted.
- Worker fallback retry logic for Ollama startup timeout is asserted.

## Tool safety

- File path traversal rejection is asserted.
- WriteFile no-overlap rewrite block and override behavior are asserted.
- Git tool subprocess invocation contract is asserted.

## Task/API contracts

- Task store create/get/update/log/next queued behavior is asserted.
- API payload contains learning summary fields and artifacts references.

## Artifact safety

- Task ID sanitization and artifact path containment are asserted.
- Artifact file map names are asserted.

## Known Operational Truths

- Runtime currently uses 11 worker agents.
- `AUTO_COMMIT` default is `false`.
- quality/polish crews are sequential.
- MCP `run_swarm()` is asynchronous and requires polling.

## Recommended AI Workflow in This Repo

1. Read `AGENTS.md` first.
2. Use this feature map to locate implementation modules quickly.
3. Verify defaults against `swarm/config.py` before updating docs or runbooks.
4. For behavior changes, update tests in `tests/**` along with docs.
5. Keep `README.md`, `AI_RUNBOOK.md`, and this file consistent.
