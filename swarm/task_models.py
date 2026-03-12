"""Shared data models for the task queue and API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskRequest(BaseModel):
    feature: str = Field(..., description="Feature request or task description")
    plan: str = Field("", description="Optional implementation plan (markdown)")
    builder_type: str = Field(
        "",
        description="Force builder: python_dev, react_dev, wordpress_dev, shopify_dev",
    )
    repo_url: str = Field("", description="Git repo URL to clone into workspace")


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
    context_summary: str = ""
    retrieval_summary: str = ""
    validation_summary: str = ""
    eval_summary: str = ""
    adaptation_summary: str = ""
    build_summary: str = ""
    review_feedback: str = ""
    quality_report: str = ""
    polish_report: str = ""
    artifacts_dir: str = ""
    failure_kind: str = ""
    error: str = ""
    log: list[str] = Field(default_factory=list)
    lessons: list[dict[str, Any]] = Field(default_factory=list, description="Extracted lessons from eval report")
    comparison: dict[str, Any] = Field(default_factory=dict, description="Comparison vs recent runs")


def new_task_id() -> str:
    return f"swarm-{uuid.uuid4().hex[:12]}"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
