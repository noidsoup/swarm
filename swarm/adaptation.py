"""Deterministic adaptation rules derived from prior run artifacts."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 1}


def load_prior_run_signals(repo_root: str, feature_request: str, context_pack: dict) -> dict:
    del feature_request, context_pack
    runs_dir = Path(repo_root) / ".swarm" / "runs"
    signals = {
        "validation_failures": 0,
        "runner_timeouts": 0,
        "successful_runs": 0,
        "successful_files": [],
    }
    successful_files: set[str] = set()

    if not runs_dir.exists():
        return signals

    for eval_path in runs_dir.glob("*/eval.json"):
        try:
            report = json.loads(eval_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        inputs = report.get("inputs", {})
        validation_status = inputs.get("validation_status", "")
        failure_kind = inputs.get("failure_kind", "")
        final_status = report.get("final_status", "")

        if validation_status == "fail":
            signals["validation_failures"] += 1
        if failure_kind == "ollama_runner_startup_timeout":
            signals["runner_timeouts"] += 1
        if final_status == "completed":
            signals["successful_runs"] += 1
            retrieval_path = eval_path.with_name("retrieval.json")
            if retrieval_path.exists():
                try:
                    retrieval = json.loads(retrieval_path.read_text(encoding="utf-8"))
                except Exception:
                    retrieval = {}
                for file_hit in retrieval.get("files", []):
                    path = file_hit.get("path")
                    if path:
                        successful_files.add(path)

    signals["successful_files"] = sorted(successful_files)
    return signals


def choose_adaptation_strategy(
    feature_request: str,
    context_pack: dict,
    prior_signals: dict,
    failure_kind: str = "",
) -> dict:
    request_tokens = _tokenize(feature_request)
    strategy_hints: list[str] = []
    retrieval_biases: list[str] = []

    strict_validation = prior_signals.get("validation_failures", 0) >= 2
    if strict_validation:
        strategy_hints.append("Repeated validation failures detected; keep validation strict.")

    if request_tokens & {"fix", "regression", "test", "tests"}:
        retrieval_biases.append("tests")
    if prior_signals.get("successful_files"):
        retrieval_biases.append("successful_examples")

    fallback_model = ""
    retry_budget = 0
    if failure_kind == "ollama_runner_startup_timeout" or prior_signals.get("runner_timeouts", 0) > 0:
        fallback_model = os.getenv("WORKER_FALLBACK_MODEL", "ollama/gemma3:4b")
        retry_budget = 1
        strategy_hints.append("Known runner timeout pattern; prefer fallback model on retry.")

    builder_override = ""
    builder_hint = context_pack.get("builder_hint", "")
    if builder_hint == "react_dev" and request_tokens & {"component", "page", "dashboard"}:
        builder_override = "react_dev"

    return {
        "fallback_model": fallback_model,
        "strict_validation": strict_validation,
        "retrieval_biases": retrieval_biases,
        "builder_override": builder_override,
        "strategy_hints": strategy_hints,
        "retry_budget": retry_budget,
        "prior_signals": prior_signals,
    }


def max_retry_budget(strategy: dict) -> int:
    try:
        retry_budget = int(strategy.get("retry_budget", 0))
    except Exception:
        retry_budget = 0
    return max(0, min(retry_budget, 2))


def summarize_adaptation_strategy(strategy: dict) -> str:
    hints = "; ".join(strategy.get("strategy_hints", [])[:3]) or "No adaptation hints"
    biases = ", ".join(strategy.get("retrieval_biases", [])) or "no retrieval bias"
    fallback_model = strategy.get("fallback_model") or "none"
    return (
        f"Adaptation: fallback={fallback_model}; "
        f"strict_validation={strategy.get('strict_validation', False)}; "
        f"retrieval_biases={biases}; {hints}."
    )
