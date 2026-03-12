"""Configuration for the swarm -- models, timeouts, git settings."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def default_ollama_base_url() -> str:
    """Default Ollama URL; use 127.0.0.1 on Windows to avoid empty localhost listener."""
    if os.getenv("OLLAMA_BASE_URL"):
        return os.environ["OLLAMA_BASE_URL"]
    return "http://127.0.0.1:11434" if sys.platform == "win32" else "http://localhost:11434"


ROLE_MODEL_MAP = {
    "planner":  "PLANNER_MODEL",
    "reviewer": "REVIEWER_MODEL",
    "builder":  "BUILDER_MODEL",
    "security": "SECURITY_MODEL",
    "performance": "PERFORMANCE_MODEL",
    "tester":   "TESTER_MODEL",
    "refactorer": "REFACTORER_MODEL",
    "docs":     "DOCS_MODEL",
    "linter":   "LINTER_MODEL",
}


@dataclass
class SwarmConfig:
    worker_model: str = field(
        default_factory=lambda: os.getenv("WORKER_MODEL", "ollama/qwen2.5-coder:7b")
    )
    ollama_base_url: str = field(default_factory=default_ollama_base_url)
    auto_commit: bool = field(
        default_factory=lambda: os.getenv("AUTO_COMMIT", "false").lower() == "true"
    )
    branch_prefix: str = field(
        default_factory=lambda: os.getenv("BRANCH_PREFIX", "swarm/")
    )
    shell_timeout: int = field(
        default_factory=lambda: int(os.getenv("SHELL_TIMEOUT", "60"))
    )
    adaptation_max_retries: int = field(
        default_factory=lambda: int(os.getenv("ADAPTATION_MAX_RETRIES", "2"))
    )
    max_review_loops: int = 3
    verbose: bool = True
    repo_root: str = field(default_factory=lambda: os.getcwd())
    mode: str = field(
        default_factory=lambda: os.getenv("SWARM_MODE", "headless")
    )
    windows_host: str = field(default_factory=lambda: os.getenv("WINDOWS_HOST", ""))
    windows_user: str = field(default_factory=lambda: os.getenv("WINDOWS_USER", ""))
    windows_ssh_key: str = field(default_factory=lambda: os.getenv("WINDOWS_SSH_KEY", ""))
    windows_swarm_api: str = field(
        default_factory=lambda: os.getenv("WINDOWS_SWARM_API", "http://localhost:9000")
    )
    windows_cursor_workspace: str = field(
        default_factory=lambda: os.getenv("WINDOWS_CURSOR_WORKSPACE", "")
    )
    default_execution_mode: str = field(
        default_factory=lambda: os.getenv("DEFAULT_EXECUTION_MODE", "local")
    )

    def _make_llm(self, model: str):
        from crewai import LLM

        kwargs = {"model": model}
        if model.startswith("ollama/"):
            kwargs["base_url"] = self.ollama_base_url
        return LLM(**kwargs)

    def worker_llm(self):
        return self._make_llm(self.worker_model)

    def llm_for_role(self, role: str):
        """Return a role-specific LLM if configured, otherwise the default worker LLM.

        Set per-role models via env vars (e.g. PLANNER_MODEL=ollama/qwen2.5-coder:14b).
        If unset, falls back to WORKER_MODEL.
        """
        env_key = ROLE_MODEL_MAP.get(role)
        model = os.getenv(env_key, "") if env_key else ""
        if not model:
            model = self.worker_model
        return self._make_llm(model)


cfg = SwarmConfig()
