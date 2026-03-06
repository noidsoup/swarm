"""Configuration for the swarm -- models, timeouts, git settings."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class SwarmConfig:
    worker_model: str = field(
        default_factory=lambda: os.getenv("WORKER_MODEL", "ollama/qwen2.5-coder:7b")
    )
    ollama_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    auto_commit: bool = field(
        default_factory=lambda: os.getenv("AUTO_COMMIT", "false").lower() == "true"
    )
    branch_prefix: str = field(
        default_factory=lambda: os.getenv("BRANCH_PREFIX", "swarm/")
    )
    shell_timeout: int = field(
        default_factory=lambda: int(os.getenv("SHELL_TIMEOUT", "60"))
    )
    max_review_loops: int = 3
    verbose: bool = True
    repo_root: str = field(default_factory=lambda: os.getcwd())
    mode: str = field(
        default_factory=lambda: os.getenv("SWARM_MODE", "headless")
    )

    def worker_llm(self):
        from crewai import LLM

        kwargs = {"model": self.worker_model}
        if self.worker_model.startswith("ollama/"):
            kwargs["base_url"] = self.ollama_base_url
        return LLM(**kwargs)


cfg = SwarmConfig()
