"""Background continuous improvement loop.

Runs optimization and improvement tasks on a schedule:
- Code review and refactoring
- Performance optimization
- Security audits
- Auto-fix lint and test issues
- Open PRs for improvements
"""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime
from pathlib import Path

from swarm.logging_utils import configure_logging


logger = logging.getLogger(__name__)


class ContinuousImprover:
    """Background agent that continuously improves code."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.queue: list[str] = []

    def on_file_changed(self, filepath: str):
        """Queue a file for improvement."""
        if filepath not in self.queue:
            self.queue.append(filepath)
            logger.info("Queued file for improvement path=%s", filepath)

    def run_improvement_loop(self):
        """Main loop: process queue, run quality gates, open PRs."""
        iteration = 0
        while True:
            iteration += 1
            logger.info(
                "Improvement loop iteration=%s queued_files=%s started_at=%s",
                iteration,
                len(self.queue),
                datetime.now().isoformat(),
            )

            if not self.queue:
                logger.info("Improvement loop idle queue empty")
                import time
                time.sleep(5)
                continue

            # Process one file at a time
            filepath = self.queue.pop(0)
            logger.info("Improving file path=%s", filepath)

            try:
                # Run swarm on this file
                cmd = f"python run.py --no-commit 'Improve and optimize {filepath}'"
                logger.info("Executing improvement command=%s", cmd)
                result = subprocess.run(cmd, shell=True, cwd=str(self.repo_path), capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info("Improvement succeeded path=%s", filepath)
                    self._maybe_open_pr(filepath)
                else:
                    logger.error("Improvement failed path=%s stderr=%s", filepath, result.stderr)

            except Exception as e:
                logger.exception("Improvement loop exception path=%s error=%s", filepath, e)

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
                logger.info("Creating PR command=%s", cmd)
                pr_result = subprocess.run(cmd, shell=True, cwd=str(self.repo_path), capture_output=True, text=True)
                
                if pr_result.returncode == 0:
                    logger.info("PR created url=%s", pr_result.stdout.strip())
                else:
                    logger.error("PR creation failed stderr=%s", pr_result.stderr)

        except Exception as e:
            logger.exception("PR creation exception path=%s error=%s", filepath, e)


def start_background_daemon(repo_path: str):
    """Start the continuous improvement daemon."""
    configure_logging()
    from swarm.watcher import watch_repo

    improver = ContinuousImprover(repo_path)

    # Start file watcher (blocking)
    watch_repo(repo_path, improver.on_file_changed)
