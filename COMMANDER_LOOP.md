# Commander Loop

How the swarm review loop actually behaves today.

## Overview

The commander loop is the BUILD + REVIEW/FIX cycle that runs before quality and polish.

```text
BUILD
  -> REVIEW
      -> APPROVED? yes -> QUALITY
      -> no -> FIX -> REVIEW (repeat)
```

## Where It Lives

- Shared phase implementations: `swarm/flow.py` (`BaseSwarmFlow`)
- Worker orchestration graph: `WorkerSwarmFlow` in `swarm/flow.py`
- Standalone orchestration graph: `FullSwarmFlow` in `swarm/flow.py`

## Routing Rules

Review routing logic:

- If review feedback contains `APPROVED` (case-insensitive), route to approved.
- Else if review iteration reached `cfg.max_review_loops`, force approved route.
- Else route to `needs_fix`.

This means a task always exits the loop, either through explicit approval or max-loop cutoff.

## Worker Phase Sequence

`WorkerSwarmFlow` wiring:

1. `build_phase`
2. `review_phase`
3. `review_router`
4. if `needs_fix`: `fix_phase` -> `re_review` -> `re_review_router` (loop)
5. if `approved`: `quality_phase`
6. `polish_phase`
7. `finish_phase` (returns structured result JSON)

## Quality and Polish Behavior

- Quality runs with four tasks: security, performance, tests, lint.
- Polish runs with two tasks: refactor, docs.
- Both use `quality_crew(..., process=Process.sequential)` in current code.

So quality/polish are deterministic and sequential, not parallel.

## Standalone Differences

`FullSwarmFlow` adds:

- `planning_phase` at start.
- `ship_phase` at end.

`ship_phase` behavior:

- If `AUTO_COMMIT=false` (default), run ends as complete with no commit.
- If `AUTO_COMMIT=true`, creates branch + commit via git helper.

## Builder Selection in Loop

Before build starts, builder is selected by:

1. Explicit `builder_type` if provided.
2. Keyword-based auto-routing (`_pick_builder`) by request/plan:
   - WordPress/PHP -> `wordpress_dev`
   - Shopify/Liquid/theme -> `shopify_dev`
   - React/Next/frontend keywords -> `react_dev`
   - Fallback -> `python_dev`

## Loop Inputs and Outputs

Loop inputs:

- plan text
- optional context pack JSON
- optional retrieval pack JSON

Loop outputs:

- `build_summary`
- `review_feedback`
- `quality_report`
- `polish_report`
- `review_iteration` count

These are returned by worker flow and persisted in task records/artifacts.

## Operational Notes

- `max_review_loops` defaults to 3.
- Worker execution always sets `auto_commit` off.
- Build phase traces are appended to `build_phase.log` in run artifacts.
- In worker runtime, the loop is surrounded by adaptation/retrieval/validation/eval stages.

## Practical Guidance

- Use `--max-reviews` for CLI control of loop depth.
- Use `--only build,review` for focused loop debugging.
- Inspect `events.jsonl` and `build_phase.log` first when loop behavior looks wrong.
