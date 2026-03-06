# The Commander Loop (Self-Improving Code)

Your swarm has a **feedback loop** that keeps improving code until it passes all checks.

## How It Works

```
          ┌─────────────┐
          │   BUILDER   │
          │  writes code│
          └──────┬──────┘
                 │
                 ▼
          ┌─────────────┐
          │  REVIEWER   │
          │ critiques   │
          └──────┬──────┘
                 │
          ┌──────┴──────┐
          │             │
       APPROVED?      NO (issues found)
          │             │
         YES            ▼
          │        ┌─────────────┐
          │        │  FIX PHASE  │
          │        │ builder     │
          │        │ fixes issues│
          │        └──────┬──────┘
          │               │
          │        ┌──────▼──────┐
          │        │ RE-REVIEW   │
          │        │ goes back up│
          │        └──────┬──────┘
          │               │
          │        (loop back or APPROVED)
          │               │
          └───────┬───────┘
                  │
                  ▼
          ┌─────────────────┐
          │  QUALITY GATES  │
          │  Security       │
          │  Performance    │
          │  Tests          │
          │  Lint           │
          └─────────────────┘
```

## The Loop is Already Implemented

In `swarm/flow.py`:

- **`review_phase()`** (line 98): Reviewer critiques the code
- **`review_router()`** (line 111): Decision point — "APPROVED" or "needs_fix"?
- **`fix_phase()`** (line 120): Builder fixes issues
- **`re_review()`** (line 130): Loops back to review
- **Max iterations**: 3 (configurable in `swarm/config.py`)

## Example: Commander Loop in Action

**Command:**
```bash
python run.py "Add product filtering to homepage"
```

**What happens:**

```
PLAN          → Architect breaks task into steps
BUILD         → Builder writes React component
REVIEW #1     → Reviewer: "Missing memoization, uses wrong hook"
FIX #1        → Builder adds useMemo, fixes hook
REVIEW #2     → Reviewer: "Good! But missing PropTypes"
FIX #2        → Builder adds PropTypes validation
REVIEW #3     → Reviewer: "APPROVED ✓"
QUALITY GATES → Security ✓, Perf ✓, Tests ✓, Lint ✓
POLISH        → Refactor + Docs
SHIPPED       → Code committed
```

## How to Trigger the Loop

### CLI (Standalone)
```bash
python run.py "Add filtering to product page"
```
Runs full loop: PLAN → BUILD → REVIEW LOOP → QUALITY → POLISH → SHIP

### Via Cursor (Headless - Recommended)
```
You (in Cursor): "Add filtering to product page"
      ↓
Cursor plans: Creates detailed implementation plan
      ↓
Cursor calls: run_swarm(plan, feature_name)
      ↓
Swarm: BUILD → REVIEW LOOP → QUALITY → POLISH
      ↓
Returns: build_summary, review_feedback, quality_report
      ↓
You judge: Approve or send back for changes
```

## Configure Loop Behavior

In `swarm/config.py`:

```python
max_review_loops = 3  # Default: try up to 3 times
auto_commit = True    # Default: commit when done
verbose = True        # Default: show agent output
```

## The "Never Sleeps" Option (Bonus)

The daemon files I just added (`daemon.py`, `background_loop.py`) extend this to continuous:

```bash
python daemon.py /path/to/repo
```

Runs continuously:
- Watches for file changes
- Queues files for improvement
- Triggers loop on each file
- Opens PRs automatically

This becomes **always-on AI CI**: every code change is reviewed, tested, and improved by the swarm.

## Real Example Output

```
============================================================
  PHASE: REVIEW (iteration 1/3)
============================================================

[REVIEW RESULT]
Issues found:
- useEffect missing dependency array (line 42)
- Re-render on every keystroke (performance issue)
- No PropTypes validation

============================================================
  PHASE: FIX (iteration 1)
============================================================

[BUILD RESULT]
Fixed:
✓ Added dependency array
✓ Wrapped in useMemo
✓ Added PropTypes

============================================================
  PHASE: REVIEW (iteration 2/3)
============================================================

[REVIEW RESULT]
Excellent! Code looks good.
APPROVED ✓
```

## What's Next

1. **Use it from Cursor** — enable swarm MCP and ask for features
2. **Let it loop** — let the agents argue and improve code automatically
3. **Optional: Run daemon** — continuous background improvement
4. **Watch it work** — agent-to-agent communication happens until all checks pass

The loop never gives up until code is good. 🤖
