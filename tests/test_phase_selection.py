from __future__ import annotations

import run as run_module


def test_resolve_phase_selection_expands_worker_prerequisites() -> None:
    phases = run_module._resolve_phase_selection(only="quality", skip=None, headless=True)

    assert phases == ["build", "quality"]


def test_resolve_phase_selection_skips_requested_worker_phases() -> None:
    phases = run_module._resolve_phase_selection(only=None, skip="quality,polish", headless=True)

    assert phases == ["build", "review"]


def test_resolve_phase_selection_expands_standalone_ship_dependencies() -> None:
    phases = run_module._resolve_phase_selection(only="ship", skip=None, headless=False)

    assert phases == ["plan", "build", "review", "quality", "polish", "ship"]
