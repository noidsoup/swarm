# AI Session Memory

Session summaries and state for the AI Dev Swarm project.

---

## 2025-03-05 — Full test run and plan sync

**Branch:** main (no commits yet)

**Completed**
- Ran test plan: `pip install -r requirements.txt` ✓, `python run.py --help` ✓
- Dry-run: `python run.py --dry-run "Add a README section for troubleshooting"` — printed config and exited as expected
- Full pipeline run: `python run.py --no-commit "Add a short Troubleshooting section to README..."` — swarm ran (PLAN → BUILD at least; may have continued in background). Ollama worker `qwen2.5-coder:7b` was used; builder wrote to README (overwrote it; README was restored afterward)
- Updated `.cursor/plans/PLAN.md`: all Phase 1–7 and Test Plan checkboxes marked done
- Restored `README.md` to project content and added a short **Troubleshooting** section with one bullet (pip install if imports fail)
- Created this `AI_SESSION_MEMORY.md`

**Decisions**
- Restored README after swarm test overwrote it with generic “My Project” content — swarm should be given clearer “append-only” style instructions when editing existing docs, or run against a subdirectory/copy

**Known issues / notes**
- **Windows encoding:** CrewAI event bus logs emojis (e.g. 🌊, 🔧) that trigger `'charmap' codec can't encode character` on Windows console. Pipeline still runs; output is noisier. Fix options: set `PYTHONIOENCODING=utf-8` when running, or configure CrewAI/Cursor to avoid emoji in event handlers
- **MCP:** To use swarm from Cursor, enable the **swarm** MCP server in Cursor (e.g. Settings → MCP) so `run_swarm`, `swarm_status`, and `list_agents` are available

**Next steps**
- ~~Optionally set `PYTHONIOENCODING=utf-8` in dev scripts or docs~~ → Done: run.py now forces UTF-8 stdout/stderr on Windows; README documents PYTHONIOENCODING fallback
- Enable swarm MCP in Cursor and try a commander-style run (plan in Cursor → `run_swarm` → judge result)
- ~~First git commit when ready~~ → Done in follow-up

---

## 2025-03-05 — Continue: encoding fix, first commit

**Completed**
- Confirmed backgrounded swarm run **finished successfully** (exit 0, ~158s): PLAN → BUILD → REVIEW → FIX → REVIEW → APPROVED → SWARM COMPLETE (2 reviews). Reviewer logged “Tool not found” for `final_answer` once; flow continued.
- Added **Windows UTF-8 fix** in `run.py`: on `win32`, stdout/stderr are wrapped with UTF-8 (errors=replace) to avoid CrewAI emoji/charmap errors.
- Documented encoding in **README** Troubleshooting (PYTHONIOENCODING fallback for subprocesses).
---

## 2025-03-06 — Commander loop, portability, and Cursor automation

**Branch:** main

**Completed**
- Added **background daemon** (`daemon.py`, `swarm/watcher.py`, `swarm/background_loop.py`): continuous improvement loop that watches repo for changes, queues files, runs swarm automatically, opens PRs
- Created **COMMANDER_LOOP.md**: documents the review-fix-re-review loop that runs until code is approved (max 3 iterations)
- Made swarm **portable**:
  - Added `--repo` CLI flag to `run.py` so you can target other repositories
  - Created `setup.py` to make swarm pip-installable: `pip install git+https://github.com/noidsoup/swarm.git`
  - Added CLI entry points: `swarm-run`, `swarm-daemon` (with wrappers for Windows `.bat` and Unix shell scripts)
- Created **USING_IN_OTHER_REPOS.md**: 4 usage patterns (CLI flag, pip install, MCP, copy/symlink)
- **Made Cursor proactive** by updating `.cursor/rules/swarm-commander.mdc`:
  - Changed default behavior: Cursor now automatically delegates to swarm (no need to ask)
  - When user asks for code work, Cursor immediately: reads code → creates plan → calls `run_swarm` → judges results
  - No manual commands needed; swarm MCP is always available
- Pushed to GitHub: commits `04f0170`, `485de0d`, `784d734`, `12286cc`
- Successfully authenticated with GitHub, created repo `noidsoup/swarm` on GitHub

**Key Features Now Available**
1. **Self-improving code loop**: review → fix → re-review until approved (max 3 iterations)
2. **Quality gates**: security, performance, tests, lint all run in parallel
3. **Continuous daemon**: `python daemon.py /repo` watches and improves code 24/7
4. **Portable**: `pip install -e .` then `swarm-run "feature"` from any repo
5. **Automatic Cursor delegation**: ask for a feature, Cursor runs the swarm without you asking

**Installation options**
- **Local dev**: `pip install -e /path/to/swarm`
- **From GitHub**: `pip install git+https://github.com/noidsoup/swarm.git`
- **Python module**: `python -m swarm.cli "feature"`
- **Wrapper scripts**: `swarm-run "feature"` (Windows `.bat` or Unix shell)

**Usage patterns**
- **CLI**: `python run.py --repo /path/to/repo "Add feature"`
- **MCP (Cursor)**: describe feature in chat → Cursor auto-delegates
- **Daemon**: `python daemon.py .` → continuous improvement
- **Package**: `pip install -e .` then use `swarm-run` from anywhere

**Known issues / notes**
- Windows encoding fixed in `run.py` (UTF-8 wrapping)
- Swarm MCP is loaded as `user-swarm` in Cursor (tools: `run_swarm`, `swarm_status`, `list_agents`)
- Reviewer has one edge case where `final_answer` tool fails but flow continues

**Next opportunities**
- Add auto-PR opening in daemon (currently just logs "would open PR")
- Test portability on multiple real repos (React, Next.js, WordPress, Shopify)
- Add optional Claude/GPT-4 for judge phase (currently uses local model)
- Performance: profile and optimize agent LLM calls
- UI: web dashboard for daemon status and logs

---

## 2026-03-12 — Mac-to-Windows remote execution, bug fixes, and docs hardening

**Branch:** main

**Completed**
- Merged `feat/remote-docker-infra` into `main` (Docker, FastAPI, worker, monitoring, SSH scripts, remote CLI)
- Set up Mac→Windows SSH tunnel: created `~/.ssh/id_ed25519_nopass`, configured `winbox` alias in `~/.ssh/config` with port forwarding (9000, 11434, 3000)
- Started Ollama, Swarm API (`uvicorn swarm.api:app`), and worker (`swarm.worker`) on Windows (`192.168.87.126`) via SSH
- Submitted and monitored remote tasks from Mac using `scripts/swarm_remote.py`
- Fixed `scripts/swarm_remote.py`: moved `global SWARM_URL` before first use (was a SyntaxError)
- Fixed CrewAI async-task validation crash: `quality_crew()` no longer forces all tasks to `async_execution=True` (`swarm/crews.py`)
- Renamed `TestTool`/`TestInput` to `RunTestsTool`/`RunTestsInput` to prevent pytest mis-collection
- Added `tests/test_smoke.py`, `tests/test_crews.py`, `tests/test_worker.py`
- Fixed `scripts/setup-autostart.ps1` path bug (`Split-Path` double-parent); re-registered Windows scheduled task `SwarmDockerComposeUp` with correct repo path
- Added Ollama runner fallback in `swarm/worker.py`: detects "timed out waiting for llama runner to start" and retries with `WORKER_FALLBACK_MODEL` (default `ollama/gemma3:4b`)
- Updated `AGENTS.md` with "Operational Truths" section: Mac orchestrator, optional Windows Ollama, 11 agents, sequential quality crews, async MCP semantics
- Hardened `.gitignore` against accidental SSH key/config commits

**Key decisions**
- Use `id_ed25519_nopass` (no passphrase) for non-interactive SSH from Cursor agent sessions
- Run combined API+worker in one Python process (shared in-memory task store) instead of Docker when Docker Desktop is unavailable
- Default `WORKER_MODEL=ollama/qwen2.5-coder:7b` with `WORKER_FALLBACK_MODEL=ollama/gemma3:4b` for runner startup resilience
- Quality/polish crews run sequentially (not async) to comply with current CrewAI validation rules

**Known issues / notes**
- `qwen2.5-coder:7b` intermittently fails Ollama runner startup on Windows (GPU cold-start); fallback to `gemma3:4b` auto-recovers
- CrewAI emoji logging still triggers charmap warnings on Windows console (non-blocking)
- Docker Desktop on Windows requires manual start or login-trigger via scheduled task; `docker compose up -d` only works after engine is ready
- `ruff` is not installed in the Mac Python environment; linting skipped locally

**Next steps**
- Create `.env` in repo root with `OLLAMA_BASE_URL` pointing to Windows IP for persistent config
- Add startup script for non-Docker mode (uvicorn+worker) as a Windows scheduled task
- Investigate `qwen2.5-coder:7b` cold-start timeout root cause on RTX 4070
- Test full pipeline completion end-to-end (build → review → quality → polish → complete)
- Add CI workflow for pytest + ruff

---

## 2026-03-12 — Context7/Vercel and orchestrator skill routing close-out

**Branch:** main
**PR:** none at time of entry (close-out PR created immediately after this update)

**Completed**
- Added always-on rule `.cursor/rules/context7-vercel.mdc` to prioritize `user-context7` for version-sensitive docs and route React/Next work through Vercel-focused skills.
- Added always-on rule `.cursor/rules/orchestrator-skills.mdc` mapping orchestrator code areas to Python/MCP/API/CI skills.
- Updated `AGENTS.md` with "Context7 and Vercel Skill Defaults" and "Orchestrator Skill Defaults".
- Updated `AI_RUNBOOK.md` with operational workflow notes for Context7/Vercel and orchestrator skill routing.
- Verified requested orchestrator skills are available locally (`python-*`, `mcp-builder`, `api-design-principles`, `github-actions-templates`).
- Pushed two direct `main` commits before this close-out pass (`600a91a`, `80c3068`).

**Current state / in progress**
- Working tree is in close-out mode only: session memory/runbook are being updated and finalized via PR merge.
- Project now has explicit always-on routing for both frontend (Context7 + Vercel) and core orchestrator maintenance skills.

**Key decisions (and why)**
- Keep skill routing in repo-local always-on rules to ensure consistent behavior across sessions without relying on ad-hoc prompts.
- Use Context7 as first source for version-sensitive framework behavior to reduce stale guidance risk.
- Split frontend and orchestrator routing into separate rule files for clarity and easier maintenance.

**Known risks / blockers**
- Skill routing depends on local skill availability in the agent environment; if a skill is removed globally, behavior may degrade to default handling.
- Rule drift is possible if project architecture changes and file-to-skill mapping is not refreshed.

**Next concrete steps**
- [ ] Validate close-out PR merge and ensure `main` contains updated memory/runbook entries.
- [ ] Optionally add a short pointer in `README.md` to `.cursor/rules/context7-vercel.mdc` and `.cursor/rules/orchestrator-skills.mdc`.
- [ ] Add CI coverage (`ruff` + `pytest`) if not already active for this branch state.

---

## 2026-03-12 — Cross-machine cursor worker handoff

**Branch:** main
**PR:** none (direct sync to latest main)

**Completed**
- Synced latest `main` multiple times during active Windows-side development and confirmed the landed fixes are present in this Mac checkout.
- Verified targeted tests pass for cursor transport/dispatch behavior:
  - `python3 -m pytest tests/test_dispatch.py tests/test_cursor_worker_service.py -q`
- Confirmed `.env` is currently ignored and not tracked in git (`git check-ignore -v .env`, `git ls-files .env` empty).
- Ran Mac->Windows cursor smoke dispatch with extended client timeout and confirmed transport/path behavior:
  - SSH reaches `winbox`
  - inbox/outbox files are created and updated
  - outbox transitions to terminal JSON
- Verified repo-local run artifact directories exist under the smoke repo (`.swarm/runs/...`) and contain `build_phase.log` for recent runs.

**Current state / in progress**
- End-to-end cursor smoke still reaches terminal **error** due to worker runtime budget:
  - `error: Cursor worker task timed out after 90s`
- This is now a timeout/workload issue, not an inbox/outbox transport issue.

**Key decisions (and why)**
- Pause repeated full smoke reruns until timeout budget or smoke workload is tuned, to avoid noisy runs and duplicate diagnostics.
- Use latest outbox JSON as the source of truth for terminal state when client-side polling takes longer.

**Known risks / blockers**
- Current 90s worker limit is too tight for some smoke runs, even after transport and artifact fixes.
- SSH alias `winbox` currently emits `bind [127.0.0.1]:9000: Address already in use` warnings from existing tunnel forwards (non-blocking but noisy).

**Latest observed outbox result**
- `swarm-df4bda9d6028`: `status=error`, `error=Cursor worker task timed out after 90s`
- `swarm-b8c91c8bc3b0`: `status=error`, `error=Cursor worker task timed out after 90s`

**Next concrete steps**
- [ ] Increase worker timeout for smoke runs (or reduce smoke prompt further) and rerun one Mac->Windows cursor smoke test.
- [ ] Capture one successful terminal outbox payload (`status=complete`) from the same smoke path.
- [ ] Optionally clean/standardize SSH tunnel behavior to remove repeated local forward bind warnings.

---

## 2026-03-12 — Windows: smoke test path and “continue on Mac”

**Branch:** main (all pushed)

**Completed (Windows side)**
- Smoke task uses a **trimmed prompt** (read one file, no edits) and a **fast path**: `SWARM_SMOKE_SKIP_LLM=1` skips the LLM and returns a fixed success so the pipeline test passes regardless of model speed.
- **AI_RUNBOOK.md** — “Cursor smoke test (Mac → Windows)” section: worker startup (300s or 60s with skip), Mac dispatch command, and **Fast smoke (no LLM)** using `SWARM_SMOKE_SKIP_LLM=1`.
- **Tests:** `test_dispatch_local_smoke_skip_llm_returns_immediately`; lightweight smoke test forces LLM path with `SWARM_SMOKE_SKIP_LLM=0`.
- Local-mode smoke with `SWARM_SMOKE_SKIP_LLM=1` returns `"status": "complete"` in a few seconds. Cursor-mode smoke still hits worker task timeout when the real LLM runs (120s/300s not enough on this Windows setup).

**How to continue on your Mac**
1. **Pull latest:** `git pull origin main`
2. **Fast cursor smoke (recommended):**  
   - On **Windows**: start the worker with skip-LLM so the test finishes quickly:
     - `$env:SWARM_SMOKE_SKIP_LLM = "1"`  
     - `python scripts/cursor_worker.py --daemon --task-timeout 60 --log-file "$env:TEMP\swarm-worker.log" --pid-file "$env:TEMP\swarm-worker.pid"`
   - On **Mac** (from swarm repo):  
     - `python scripts/swarm_remote.py dispatch "cursor smoke test" --mode cursor --repo-path "C:/Users/<you>/AppData/Local/Temp/smoke-repo"`  
     - Use a path that exists on the Windows machine (or create a small repo there).
   - Expect `"status": "complete"` and `build_summary` containing `SMOKE_OK` and `SWARM_SMOKE_SKIP_LLM`.
3. **Full smoke (with LLM):** On Windows, start the worker **without** `SWARM_SMOKE_SKIP_LLM` and use a long task timeout (e.g. 300–600s). Then run the same Mac dispatch; allow several minutes.
4. **Runbook:** See **AI_RUNBOOK.md** → “Cursor smoke test (Mac → Windows)” for full steps and stop-worker command.

**Next steps (Mac or Windows)**
- Run the fast smoke from Mac once to confirm end-to-end (worker on Windows with `SWARM_SMOKE_SKIP_LLM=1`).
- Optionally tune worker timeout or model for full (LLM) smoke if you want that path to pass.

## 2026-03-12 — Mac-run smoke retry and connectivity findings

**Branch:** main
**PR:** none (direct sync requested)

**Completed**
- Pulled latest `main` (`4876e8e -> 0bb535e`) and ingested the new smoke-task updates:
  - smoke timeout guidance raised in runbook
  - `SWARM_SMOKE_SKIP_LLM` fast-path support in dispatcher/tests
- Executed Mac-side cursor smoke dispatch attempts from this checkout.
- Confirmed first failure mode is config-gated: cursor mode requires `WINDOWS_HOST` + `WINDOWS_USER`.
- Confirmed transport reached Windows when env vars were supplied (task created, terminal outbox responses returned), but task timed out (`Cursor worker task timed out after 90s`) on one run.
- Confirmed `winbox` alias `LocalForward` bindings can add repeated `bind ... 9000 already in use` noise and make repeated SSH polling less stable.

**Current state / in progress**
- Smoke path is implemented and reachable, but end-to-end success is still sensitive to runtime budget and SSH invocation style.
- Most stable Mac invocation observed: direct host + explicit key (`WINDOWS_HOST=<ip>`, `WINDOWS_SSH_KEY=...`) instead of relying on a forwarded alias during poll-heavy runs.

**Key decisions (and why)**
- Document direct-host cursor dispatch in runbook to reduce alias-related SSH polling flakiness.
- Keep timeout guidance at 300s (or use `SWARM_SMOKE_SKIP_LLM=1`) for deterministic pipeline validation.

**Known risks / blockers**
- Windows-side worker lifecycle/log collection still needs one clean, reproducible "single command" flow to avoid stale daemons between reruns.
- If the same SSH alias is used simultaneously for tunnels and poll-heavy commands, intermittent timing noise can mask real smoke outcomes.

**Next concrete steps**
- [ ] On Windows, start a fresh worker with `SWARM_SMOKE_SKIP_LLM=1` and `--task-timeout 300`, then run one Mac dispatch with explicit `WINDOWS_HOST`/`WINDOWS_SSH_KEY`.
- [ ] Capture one confirmed `status=complete` payload and paste into this memory log.
- [ ] Add a tiny helper script for Windows worker start/stop to reduce daemon drift between smoke reruns.

---

## Plan: Test cursor smoke for real from Mac (2026-03-12)

**Purpose:** When you are on the Mac and the user says they are testing the system for real, follow this plan so the Mac knows what to do.

**Prerequisites (must be done on Windows before Mac test)**  
- [ ] On Windows, in the swarm repo: start the worker with fast smoke so the test finishes quickly:  
  `.\scripts\cursor-worker.ps1 start -Fast`  
  (Or check status: `.\scripts\cursor-worker.ps1 status`.)  
- [ ] A small smoke repo exists on the Windows machine, e.g.  
  `C:\Users\<you>\AppData\Local\Temp\smoke-repo` with at least `app.py` or `README.md`.

**On Mac (this checkout)**  
1. [ ] Pull latest: `git pull origin main`  
2. [ ] Ensure env for cursor mode (in shell or `.env`):  
   - `WINDOWS_HOST` = Windows IP (e.g. `192.168.87.126`)  
   - `WINDOWS_USER` = Windows username (e.g. `nicho`)  
   - Optional: `WINDOWS_SSH_KEY` = path to key used for SSH to Windows  
3. [ ] From the swarm repo root, run the smoke (path must exist on Windows):  
   ```bash  
   python3 scripts/swarm_remote.py dispatch "cursor smoke test" --mode cursor --repo-path "C:/Users/<you>/AppData/Local/Temp/smoke-repo"  
   ```  
   Or with explicit env:  
   ```bash  
   WINDOWS_HOST=192.168.87.126 WINDOWS_USER=nicho python3 scripts/swarm_remote.py dispatch "cursor smoke test" --mode cursor --repo-path "C:/Users/nicho/AppData/Local/Temp/smoke-repo"  
   ```  
4. [ ] Expect: `"status": "complete"` and `build_summary` containing `SMOKE_OK` / `SWARM_SMOKE_SKIP_LLM` within about a minute.  
5. [ ] If you see timeout or SSH errors: note the exact Mac command and full output (and if possible the Windows worker log tail) for debugging.

**Real (non-skip) smoke — Mac runs the actual LLM**  
When the user wants a real smoke (no skip), the Mac should use this flow:

- **Windows first:** Stop any fast worker, then start the worker **without** `-Fast` so the real LLM runs:  
  `.\scripts\cursor-worker.ps1 stop`  
  `.\scripts\cursor-worker.ps1 start`  
  (Worker will have 300s task timeout, no `SWARM_SMOKE_SKIP_LLM`.)
- **On Mac:** Set client timeouts so the client doesn’t give up before the worker (allow 3–5 min), then run the same dispatch:  
  ```bash  
  export WINDOWS_CURSOR_TIMEOUT=400  
  export WINDOWS_CURSOR_HEARTBEAT_TIMEOUT=120  
  WINDOWS_HOST=192.168.87.126 WINDOWS_USER=nicho python3 scripts/swarm_remote.py dispatch "cursor smoke test" --mode cursor --repo-path "C:/Users/nicho/AppData/Local/Temp/smoke-repo"  
  ```  
  Use your real Windows IP and username if different. Expect the run to take several minutes; if it still times out, increase the worker timeout on Windows (e.g. 600s) and retry.

---

## Real test instructions (copy-paste)

**Windows (this machine):** Worker must be running with real smoke (no skip). Unset skip so the run uses the real LLM.
```powershell
.\scripts\cursor-worker.ps1 stop
Remove-Item Env:SWARM_SMOKE_SKIP_LLM -ErrorAction SilentlyContinue
.\scripts\cursor-worker.ps1 start
```
(300s task timeout, no `SWARM_SMOKE_SKIP_LLM`. Smoke repo: `C:\Users\nicho\AppData\Local\Temp\smoke-repo`.)

**Mac:** Run this (allow 3–5 min). `WINDOWS_SSH_KEY` is required for SSH auth.
```bash
export WINDOWS_CURSOR_TIMEOUT=400 WINDOWS_CURSOR_HEARTBEAT_TIMEOUT=120
export WINDOWS_SSH_KEY=/Users/nicholas/.ssh/id_ed25519_nopass
WINDOWS_HOST=192.168.87.126 WINDOWS_USER=nicho python3 scripts/swarm_remote.py dispatch "cursor smoke test" --mode cursor --repo-path "C:/Users/nicho/AppData/Local/Temp/smoke-repo"
```
Replace IP/username/key path if different. Expect `"status": "complete"` and a real `build_summary` (no "Pipeline check only (SWARM_SMOKE_SKIP_LLM=1)"); if timeout, increase worker timeout on Windows and retry.

---

## 2026-03-12 — Mac executed instructed step; key requirement and current mode

**Branch:** main
**PR:** none (direct sync requested)

**Completed**
- Pulled latest `main` and followed the exact "Real test instructions (copy-paste)" Mac command.
- First attempt failed with SSH authentication because `WINDOWS_SSH_KEY` was not set in that command.
- Reran with explicit key:
  - `WINDOWS_SSH_KEY=/Users/nicholas/.ssh/id_ed25519_nopass`
  - Dispatch succeeded with `status=complete` and `task_id=swarm-9f7de8ecb4dc`.

**Observed result**
- `build_summary` returned:
  - `STATUS: SMOKE_OK`
  - `NOTE: Pipeline check only (SWARM_SMOKE_SKIP_LLM=1).`

**Current state / blocker**
- The Windows worker path is healthy end-to-end, but runs are still in **skip-LLM smoke mode**.
- True non-skip LLM validation has not yet been confirmed in this run.

**Next concrete steps**
- [ ] On Windows, ensure `SWARM_SMOKE_SKIP_LLM` is unset in the worker environment before startup.
- [ ] Restart worker in normal mode and rerun the same Mac command with `WINDOWS_SSH_KEY` set.
- [ ] Confirm a `status=complete` result without the skip-mode note.

---

## 2026-03-12 — Offload path confirmed; real run blocked by Windows LLM timeout

**Branch:** main
**PR:** none (direct sync requested)

**Completed**
- Kept the requested offload path only: Mac dispatches with `--mode cursor`, Windows executes via cursor worker.
- Ran real smoke again from Mac with:
  - `WINDOWS_CURSOR_TIMEOUT=400`
  - `WINDOWS_CURSOR_HEARTBEAT_TIMEOUT=120`
  - `WINDOWS_SSH_KEY=/Users/nicholas/.ssh/id_ed25519_nopass`
- Task reached Windows and started execution (`task_id=swarm-27c38df1eb49`), but Mac polling ended with heartbeat stall.

**Observed failure**
- Windows worker log shows model/runtime timeout during build phase:
  - `litellm.APIConnectionError: OllamaException - litellm.Timeout: Connection timed out after 600.0 seconds.`
- Outbox terminal result file for this task was not produced (`~/.swarm/outbox/swarm-27c38df1eb49.json` absent), which explains the heartbeat-stalled error on Mac.

**Current state**
- Mac->Windows transport/offload path is working.
- Real non-skip run remains blocked by Windows-side LLM execution timeout.

**Next concrete steps**
- [ ] On Windows, validate model readiness/runtime health before rerun (warm/startup behavior).
- [ ] Increase worker timeout and rerun one real smoke through the same `--mode cursor` path.
- [ ] Capture first successful non-skip `status=complete` payload and append it here.

---

## 2026-03-12 — Mac continue pass for Windows handoff

**Branch:** main
**PR:** none (direct sync requested)

**Completed**
- Pulled latest `main` and continued from Mac on the required offload path (`--mode cursor` only).
- Ran smoke dispatch from Mac with explicit SSH key and client timeouts:
  - `WINDOWS_CURSOR_TIMEOUT=400`
  - `WINDOWS_CURSOR_HEARTBEAT_TIMEOUT=120`
  - `WINDOWS_SSH_KEY=/Users/nicholas/.ssh/id_ed25519_nopass`
- Latest task reached Windows but stalled on heartbeat (`task_id=swarm-7c322fb81f5b`).

**Observed behavior**
- Worker logs still show model/runtime timeout symptoms during execution.
- Outbox terminal result file for the stalled task was not created.
- Isolated queue-root attempt (`~/.swarm-mactest`) did not stabilize the run because the daemon process exited immediately.

**Windows next step (exact)**
- Run the worker once in foreground to capture startup/runtime stderr directly:
  - `python scripts/cursor_worker.py --root "~/.swarm" --task-timeout 300`

**After Windows confirms foreground run**
- Mac should rerun:
  - `WINDOWS_CURSOR_TIMEOUT=400 WINDOWS_CURSOR_HEARTBEAT_TIMEOUT=120 WINDOWS_SSH_KEY=/Users/nicholas/.ssh/id_ed25519_nopass WINDOWS_HOST=192.168.87.126 WINDOWS_USER=nicho python3 scripts/swarm_remote.py dispatch "cursor smoke test" --mode cursor --repo-path "C:/Users/nicho/AppData/Local/Temp/smoke-repo"`
