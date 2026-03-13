# Async Cursor Submit + Track Plan

## Objective

Implement a long-term async workflow for cursor-mode dispatch so Mac submit is non-blocking when requested, while preserving current blocking behavior by default.

## Required Behavior

- `dispatch --mode cursor --async ...` returns quickly (few seconds) with `task_id`.
- Tracking uses existing commands and APIs:
  - `status <task_id>`
  - `logs <task_id>`
  - `cancel <task_id>`
- Default behavior remains blocking unless `--async` is passed.
- No breaking change for existing scripts.

## Implementation Scope

### 1) `swarm/cursor_worker.py`

Refactor `CursorWorkerClient` to separate submit from waiting:

- `submit(payload) -> task_id`
  - Create task envelope
  - Ensure remote dirs exist
  - Upload inbox file
  - Return generated `task_id`
- `wait(task_id) -> result`
  - Current polling logic from `submit_and_wait`
  - Preserve timeout and heartbeat behavior
- Keep `submit_and_wait(payload)` as convenience:
  - Call `submit(payload)`
  - Call `wait(task_id)`

Notes:
- Keep heartbeat/timeout semantics unchanged.
- Keep envelope schema and remote file paths unchanged.

### 2) `swarm/dispatch.py`

Add optional completion waiting control:

- Extend `dispatch(...)` signature with `wait_for_completion: bool = True` (or equivalent).
- In cursor mode:
  - If wait is enabled, keep current behavior.
  - If wait is disabled, call `submit(payload)` and return:
    - `{ "status": "queued", "task_id": "...", "execution_mode": "cursor" }`
    - Include stable metadata fields if useful (`feature_name`, `builder_type`, `submitted_at`).

Optional helper:
- Add a cursor-status helper that checks task result by `task_id` using existing cursor-worker outbox lookup, returning queued/running/completed semantics.

### 3) `scripts/swarm_remote.py`

Add async submit flag on `dispatch`:

- New flag: `--async` (store as `async_dispatch` or similar).
- Behavior:
  - If `--async` set and mode is cursor: call dispatch with `wait_for_completion=False`.
  - Otherwise keep blocking behavior.

User output in async mode:
- Print returned JSON.
- Print copy/paste next commands:
  - `swarm-remote status <task_id>` or project equivalent command
  - `swarm-remote logs <task_id>`
  - `swarm-remote cancel <task_id>`

Guardrails:
- If `--async` is passed in non-cursor mode, either:
  - ignore with warning, or
  - return clear validation error.
Choose one and test it.

## Tests

Add or update tests for:

- Cursor worker client:
  - `submit()` returns `task_id` and uploads expected envelope.
  - `wait()` returns terminal result.
  - `submit_and_wait()` still works.
- Dispatcher:
  - cursor + wait=True uses blocking path.
  - cursor + wait=False returns queued payload with task id.
  - non-cursor modes unaffected.
- CLI (`scripts/swarm_remote.py`):
  - `dispatch --async` invokes non-blocking path.
  - output includes follow-up status/log/cancel commands.
  - blocking default unchanged.

## Acceptance Criteria

- `dispatch --mode cursor --async ...` returns in a few seconds with `task_id`.
- `status <task_id>` transitions `queued -> running -> completed/failed`.
- `logs <task_id>` works for async-submitted tasks.
- Existing blocking dispatch still works unchanged.

## Suggested Validation Commands

```bash
pytest tests/test_cursor_worker_service.py tests/test_dispatch.py
```

If CLI tests exist for `scripts/swarm_remote.py`, include them as well.

Run lints for changed files:

```bash
python3 -m ruff check swarm/cursor_worker.py swarm/dispatch.py scripts/swarm_remote.py tests
```
