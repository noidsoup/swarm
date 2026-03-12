"""Tests for TaskRequest validation and ListDirectoryTool max_depth capping."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from swarm.task_models import TaskRequest
from swarm.tools.file_tool import ListDirectoryTool, _MAX_DEPTH_LIMIT
from swarm.config import cfg


# ---------------------------------------------------------------------------
# TaskRequest validation
# ---------------------------------------------------------------------------


def test_task_request_rejects_empty_feature() -> None:
    with pytest.raises(ValidationError):
        TaskRequest(feature="")


def test_task_request_rejects_feature_too_long() -> None:
    with pytest.raises(ValidationError):
        TaskRequest(feature="x" * 2001)


def test_task_request_rejects_plan_too_long() -> None:
    with pytest.raises(ValidationError):
        TaskRequest(feature="valid feature", plan="x" * 50001)


def test_task_request_rejects_invalid_builder_type() -> None:
    with pytest.raises(ValidationError, match="Invalid builder_type"):
        TaskRequest(feature="test feature", builder_type="evil_hacker")


def test_task_request_accepts_valid_builder_types() -> None:
    for bt in ("", "python_dev", "react_dev", "wordpress_dev", "shopify_dev"):
        req = TaskRequest(feature="test feature", builder_type=bt)
        assert req.builder_type == bt


def test_task_request_rejects_invalid_repo_url_scheme() -> None:
    with pytest.raises(ValidationError, match="Invalid repo_url scheme"):
        TaskRequest(feature="test", repo_url="ftp://example.com/repo.git")


def test_task_request_rejects_repo_url_missing_hostname() -> None:
    with pytest.raises(ValidationError, match="missing hostname"):
        TaskRequest(feature="test", repo_url="https:///no-host")


def test_task_request_accepts_valid_https_repo_url() -> None:
    req = TaskRequest(feature="test", repo_url="https://github.com/user/repo.git")
    assert req.repo_url == "https://github.com/user/repo.git"


def test_task_request_accepts_ssh_repo_url() -> None:
    req = TaskRequest(feature="test", repo_url="git@github.com:user/repo.git")
    assert req.repo_url == "git@github.com:user/repo.git"


def test_task_request_accepts_empty_repo_url() -> None:
    req = TaskRequest(feature="test", repo_url="")
    assert req.repo_url == ""


def test_task_request_rejects_repo_url_too_long() -> None:
    with pytest.raises(ValidationError):
        TaskRequest(feature="test", repo_url="https://example.com/" + "a" * 490)


# ---------------------------------------------------------------------------
# ListDirectoryTool max_depth capping
# ---------------------------------------------------------------------------


def test_list_directory_caps_max_depth_above_limit(tmp_path) -> None:
    cfg.repo_root = str(tmp_path)
    tool = ListDirectoryTool()
    # Should not raise; depth is capped internally
    result = tool._run(path=".", max_depth=999)
    assert "[ERROR]" not in result


def test_list_directory_caps_max_depth_to_constant(tmp_path) -> None:
    """Verify _MAX_DEPTH_LIMIT is a sensible positive integer."""
    assert isinstance(_MAX_DEPTH_LIMIT, int)
    assert 1 <= _MAX_DEPTH_LIMIT <= 20


def test_list_directory_minimum_depth_is_one(tmp_path) -> None:
    cfg.repo_root = str(tmp_path)
    tool = ListDirectoryTool()
    # max_depth=0 should be clamped to 1 and still work
    result = tool._run(path=".", max_depth=0)
    assert "[ERROR]" not in result
