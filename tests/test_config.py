from __future__ import annotations

import sys
from unittest.mock import Mock, patch

from swarm.config import SwarmConfig, default_ollama_base_url


def test_make_llm_adds_base_url_for_ollama_models() -> None:
    config = SwarmConfig(ollama_base_url="http://ollama.internal:11434")

    with patch("crewai.LLM") as mock_llm:
        config._make_llm("ollama/qwen2.5-coder:7b")

    mock_llm.assert_called_once_with(
        model="ollama/qwen2.5-coder:7b",
        base_url="http://ollama.internal:11434",
    )


def test_llm_for_role_prefers_role_specific_override(monkeypatch: Mock) -> None:
    monkeypatch.setenv("REVIEWER_MODEL", "custom-reviewer")
    config = SwarmConfig(worker_model="default-worker")
    config._make_llm = Mock(return_value="reviewer-llm")

    result = config.llm_for_role("reviewer")

    assert result == "reviewer-llm"
    config._make_llm.assert_called_once_with("custom-reviewer")


def test_llm_for_role_falls_back_to_worker_model(monkeypatch: Mock) -> None:
    monkeypatch.delenv("REVIEWER_MODEL", raising=False)
    config = SwarmConfig(worker_model="default-worker")
    config._make_llm = Mock(return_value="worker-llm")

    result = config.llm_for_role("reviewer")

    assert result == "worker-llm"
    config._make_llm.assert_called_once_with("default-worker")


def test_default_ollama_base_url_uses_env_when_set(monkeypatch: Mock) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://custom:11434")
    assert default_ollama_base_url() == "http://custom:11434"


def test_default_ollama_base_url_uses_127_on_windows_when_unset(monkeypatch: Mock) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    with patch.object(sys, "platform", "win32"):
        assert default_ollama_base_url() == "http://127.0.0.1:11434"


def test_default_ollama_base_url_uses_localhost_on_non_windows_when_unset(monkeypatch: Mock) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    with patch.object(sys, "platform", "darwin"):
        assert default_ollama_base_url() == "http://localhost:11434"
