from __future__ import annotations

import json
from pathlib import Path

from swarm.adaptation import (
    choose_adaptation_strategy,
    load_prior_run_signals,
    max_retry_budget,
)


def _write_run(root: Path, run_id: str, eval_payload: dict, retrieval_payload: dict | None = None) -> None:
    run_dir = root / ".swarm" / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "eval.json").write_text(json.dumps(eval_payload), encoding="utf-8")
    if retrieval_payload is not None:
        (run_dir / "retrieval.json").write_text(json.dumps(retrieval_payload), encoding="utf-8")


def test_load_prior_run_signals_collects_failures_timeouts_and_successful_files(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        "swarm-one",
        {
            "final_status": "failed",
            "inputs": {
                "validation_status": "fail",
                "failure_kind": "ollama_runner_startup_timeout",
            },
        },
    )
    _write_run(
        tmp_path,
        "swarm-two",
        {
            "final_status": "completed",
            "inputs": {
                "validation_status": "pass",
                "failure_kind": "",
            },
        },
        retrieval_payload={
            "files": [{"path": "tests/test_auth.py"}, {"path": "auth_service.py"}],
            "memories": [],
            "memory_source": "local",
        },
    )

    signals = load_prior_run_signals(
        str(tmp_path),
        "Fix auth bug",
        {"builder_hint": "python_dev", "stack": {"frameworks": ["python"]}},
    )

    assert signals["validation_failures"] == 1
    assert signals["runner_timeouts"] == 1
    assert "tests/test_auth.py" in signals["successful_files"]
    assert signals["successful_runs"] == 1


def test_choose_adaptation_strategy_uses_fallback_model_for_runner_timeout(monkeypatch) -> None:
    monkeypatch.setenv("WORKER_FALLBACK_MODEL", "ollama/gemma3:4b")

    strategy = choose_adaptation_strategy(
        "Fix flaky generation",
        {"builder_hint": "python_dev", "stack": {"frameworks": ["python"]}},
        {"validation_failures": 0, "runner_timeouts": 1, "successful_files": [], "successful_runs": 0},
        failure_kind="ollama_runner_startup_timeout",
    )

    assert strategy["fallback_model"] == "ollama/gemma3:4b"
    assert strategy["retry_budget"] == 1
    assert "runner timeout" in " ".join(strategy["strategy_hints"]).lower()


def test_choose_adaptation_strategy_enables_strict_validation_and_test_bias_after_repeated_failures() -> None:
    strategy = choose_adaptation_strategy(
        "Fix auth regression and add a test",
        {"builder_hint": "python_dev", "stack": {"frameworks": ["python"]}},
        {
            "validation_failures": 3,
            "runner_timeouts": 0,
            "successful_files": ["tests/test_auth.py"],
            "successful_runs": 1,
        },
    )

    assert strategy["strict_validation"] is True
    assert "tests" in strategy["retrieval_biases"]
    assert "successful_examples" in strategy["retrieval_biases"]
    assert "repeated validation failures" in " ".join(strategy["strategy_hints"]).lower()


def test_max_retry_budget_is_bounded() -> None:
    assert max_retry_budget({"retry_budget": 99}) == 2
    assert max_retry_budget({"retry_budget": 1}) == 1
    assert max_retry_budget({"retry_budget": -5}) == 0
