"""Background continuous improvement loop.

Runs optimization and improvement tasks on a schedule:
- Code review and refactoring
- Performance optimization
- Security audits
- Auto-fix lint and test issues
- Open PRs for improvements
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path


class ContinuousImprover:
    """Background agent that continuously improves code."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.queue: list[str] = []

    def on_file_changed(self, filepath: str):
        """Queue a file for improvement."""
        if filepath not in self.queue:
            self.queue.append(filepath)
            print(f"[QUEUE] Added {filepath}")

    def run_improvement_loop(self):
        """Main loop: process queue, run quality gates, open PRs."""
        iteration = 0
        while True:
            iteration += 1
            print(f"\n{'='*60}")
            print(f"[LOOP {iteration}] {datetime.now().isoformat()}")
            print(f"[QUEUE] {len(self.queue)} files pending")
            print(f"{'='*60}")

            if not self.queue:
                print("[LOOP] Queue empty, waiting for changes...")
                import time
                time.sleep(5)
                continue

            # Process one file at a time
            filepath = self.queue.pop(0)
            print(f"\n[IMPROVING] {filepath}")

            try:
                # Run swarm on this file
                cmd = f"python run.py --no-commit 'Improve and optimize {filepath}'"
                print(f"[EXEC] {cmd}")
                result = subprocess.run(cmd, shell=True, cwd=str(self.repo_path), capture_output=True, text=True)
                
                if result.returncode == 0:
                    print(f"[SUCCESS] Swarm improved {filepath}")
                    self._maybe_open_pr(filepath)
                else:
                    print(f"[ERROR] Swarm failed on {filepath}")
                    print(result.stderr)

            except Exception as e:
                print(f"[ERROR] Exception: {e}")

    def _maybe_open_pr(self, filepath: str):
        """Open PR if there are uncommitted changes."""
        try:
            # Check for staged changes
            result = subprocess.run(
                "git diff --cached --name-only",
                shell=True,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
            )

            if result.stdout.strip():
                # Create PR
                msg = f"AI: improve {Path(filepath).name}"
                cmd = f'gh pr create --title "{msg}" --body "Automated improvement by AI swarm"'
                print(f"[PR] {cmd}")
                pr_result = subprocess.run(cmd, shell=True, cwd=str(self.repo_path), capture_output=True, text=True)
                
                if pr_result.returncode == 0:
                    print(f"[PR] Created: {pr_result.stdout.strip()}")
                else:
                    print(f"[PR] Failed: {pr_result.stderr}")

        except Exception as e:
            print(f"[PR] Error: {e}")


def start_background_daemon(repo_path: str):
    """Start the continuous improvement daemon."""
    from watcher import watch_repo

    improver = ContinuousImprover(repo_path)

    # Start file watcher (blocking)
    watch_repo(repo_path, improver.on_file_changed)
