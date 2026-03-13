"""Tests for the swarm error hierarchy."""

from swarm.errors import (
    BuilderError,
    DispatchError,
    ExecutionTimeoutError,
    PostflightError,
    PreflightError,
    RetryableError,
    SwarmError,
    ValidationError,
)


def test_all_errors_are_swarm_errors():
    for cls in (
        ValidationError,
        PreflightError,
        PostflightError,
        DispatchError,
        ExecutionTimeoutError,
        BuilderError,
        RetryableError,
    ):
        assert issubclass(cls, SwarmError)


def test_preflight_and_postflight_are_validation_errors():
    assert issubclass(PreflightError, ValidationError)
    assert issubclass(PostflightError, ValidationError)


def test_retryable_error_wraps_cause():
    original = RuntimeError("connection reset")
    err = RetryableError("transient")
    err.__cause__ = original
    assert err.__cause__ is original


def test_dispatch_error_message():
    err = DispatchError("bad mode")
    assert "bad mode" in str(err)
