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
- **Initial git commit** (see below).
