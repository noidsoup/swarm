# ruff: noqa: E402

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The repo root must be importable before loading project modules in tests.

from swarm.config import cfg


@pytest.fixture(autouse=True)
def restore_cfg() -> Iterator[None]:
    original = {
        "repo_root": cfg.repo_root,
        "auto_commit": cfg.auto_commit,
        "verbose": cfg.verbose,
        "max_review_loops": cfg.max_review_loops,
    }
    yield
    cfg.repo_root = original["repo_root"]
    cfg.auto_commit = original["auto_commit"]
    cfg.verbose = original["verbose"]
    cfg.max_review_loops = original["max_review_loops"]
