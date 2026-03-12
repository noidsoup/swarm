"""Shared data models for the task queue and API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

_ALLOWED_BUILDER_TYPES = {"", "python_dev", "react_dev", "wordpress_dev", "shopify_dev"}
_ALLOWED_REPO_SCHEMES = {"https", "http", "ssh", "git"}


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskRequest(BaseModel):
    feature: str = Field(..., min_length=1, max_length=2000, description="Feature request or task description")
    plan: str = Field("", max_length=50000, description="Optional implementation plan (markdown)")
    builder_type: str = Field(
        "",
        description="Force builder: python_dev, react_dev, wordpress_dev, shopify_dev",
    )
    repo_url: str = Field("", max_length=500, description="Git repo URL to clone into workspace")

    @field_validator("builder_type")
    @classmethod
    def validate_builder_type(cls, v: str) -> str:
        if v not in _ALLOWED_BUILDER_TYPES:
            raise ValueError(
                f"Invalid builder_type '{v}'. Must be one of: "
                + ", ".join(sorted(t for t in _ALLOWED_BUILDER_TYPES if t))
            )
        return v

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v: str) -> str:
        if not v:
            return v
        if v.startswith("git@"):
            return v
        parsed = urlparse(v)
        if parsed.scheme not in _ALLOWED_REPO_SCHEMES:
            raise ValueError(
                f"Invalid repo_url scheme '{parsed.scheme}'. Must be https, http, ssh, or git."
            )
        if not parsed.hostname:
            raise ValueError("Invalid repo_url: missing hostname.")
        return v


class TaskResult(BaseModel):
    task_id: str
    status: TaskStatus
    feature: str
    plan: str = ""
    builder_type: str = ""
    repo_url: str = ""
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    build_summary: str = ""
    review_feedback: str = ""
    quality_report: str = ""
    polish_report: str = ""
    error: str = ""
    log: list[str] = Field(default_factory=list)


def new_task_id() -> str:
    return f"swarm-{uuid.uuid4().hex[:12]}"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
