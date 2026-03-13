"""Tests for worker graceful shutdown."""

import threading
import swarm.worker as worker


def test_shutdown_event_stops_main_loop(monkeypatch):
    """Setting the shutdown event should cause main loop to exit."""
    poll_count = {"n": 0}
    original_event = worker._shutdown_event

    def fake_next_queued():
        poll_count["n"] += 1
        if poll_count["n"] >= 2:
            worker._shutdown_event.set()
        return None

    monkeypatch.setattr(worker, "POLL_INTERVAL", 0.01)
    monkeypatch.setattr(worker, "WORKSPACE", "/tmp/swarm-test-workspace")
    monkeypatch.setattr(worker.store, "next_queued", fake_next_queued)
    monkeypatch.setattr(worker, "configure_logging", lambda: None)

    worker._shutdown_event = threading.Event()
    try:
        worker.main()
    finally:
        worker._shutdown_event = original_event

    assert poll_count["n"] >= 2
