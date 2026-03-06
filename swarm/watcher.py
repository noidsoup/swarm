"""File watcher for continuous code improvement.

Watches the repo for changes and triggers the swarm to:
- Review new code
- Run quality gates
- Auto-optimize performance
- Fix bugs and lint issues
- Open PRs for improvements
"""

from __future__ import annotations

import time
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    raise ImportError("pip install watchdog")


class CodeChangeHandler(FileSystemEventHandler):
    """Triggers swarm on code changes."""

    def __init__(self, callback, debounce_ms=2000):
        self.callback = callback
        self.debounce_ms = debounce_ms
        self.last_trigger = defaultdict(lambda: None)

    def on_modified(self, event):
        if event.is_directory or not self._should_watch(event.src_path):
            return

        now = datetime.now()
        last = self.last_trigger[event.src_path]

        if last and (now - last).total_seconds() < (self.debounce_ms / 1000):
            return

        self.last_trigger[event.src_path] = now
        self.callback(event.src_path)

    @staticmethod
    def _should_watch(path: str) -> bool:
        """Skip certain paths."""
        ignore = {
            "__pycache__",
            ".git",
            ".cursor",
            "node_modules",
            ".env",
            ".swp",
            ".log",
        }
        return not any(ig in path for ig in ignore)


def watch_repo(repo_path: str, callback, patterns: list[str] | None = None):
    """Watch repo for changes and trigger callback.

    Args:
        repo_path: Path to monitor
        callback: Function(filepath) to call on change
        patterns: File patterns to watch (default: all code files)
    """
    if patterns is None:
        patterns = ["*.py", "*.ts", "*.tsx", "*.js", "*.jsx", "*.css"]

    observer = Observer()
    handler = CodeChangeHandler(callback)
    observer.schedule(handler, repo_path, recursive=True)

    print(f"[WATCHER] Monitoring {repo_path}")
    print(f"[WATCHER] Patterns: {', '.join(patterns)}")

    try:
        observer.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[WATCHER] Stopping...")
        observer.stop()
    observer.join()
