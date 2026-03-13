"""Domain exception hierarchy for the swarm orchestrator."""

from __future__ import annotations


class SwarmError(Exception):
    """Base for all swarm-specific exceptions."""


class ValidationError(SwarmError):
    """A validation gate (preflight or postflight) failed."""


class PreflightError(ValidationError):
    """Preflight validation failed; the run should not proceed."""


class PostflightError(ValidationError):
    """Postflight validation failed; the run completed but output is suspect."""


class DispatchError(SwarmError):
    """Could not dispatch a task to the requested execution backend."""


class ExecutionTimeoutError(SwarmError):
    """A flow or phase exceeded its time budget."""


class BuilderError(SwarmError):
    """A builder agent failed during execution."""


class RetryableError(SwarmError):
    """Marker for transient failures that may succeed on retry.

    Wrap the original exception: ``raise RetryableError("msg") from original``.
    """
