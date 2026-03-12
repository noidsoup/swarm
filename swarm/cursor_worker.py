"""Cursor-to-Cursor task transport via SSH inbox/outbox files."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from typing import Any

from swarm.task_models import new_task_id, utcnow_iso


class CursorWorkerClient:
    def __init__(self, connection: Any) -> None:
        self.connection = connection
        self.remote_root = os.getenv("WINDOWS_CURSOR_QUEUE_ROOT", "~/.swarm")

    def submit_and_wait(self, payload: dict[str, Any]) -> dict[str, Any]:
        task_id = new_task_id()
        envelope = {
            "task_id": task_id,
            "created_at": utcnow_iso(),
            "plan": payload.get("plan", ""),
            "feature_name": payload.get("feature_name", ""),
            "builder_type": payload.get("builder_type", ""),
            "repo_path": payload.get("repo_path", ""),
            "repo_url": payload.get("repo_url", ""),
            "status": "queued",
        }
        self._ensure_remote_dirs()
        self._upload_task(task_id, envelope)
        return self._poll_result(task_id)

    def _ssh_base(self) -> list[str]:
        cmd = ["ssh"]
        if getattr(self.connection, "ssh_key_path", ""):
            cmd.extend(["-i", self.connection.ssh_key_path])
        cmd.append(f"{self.connection.user}@{self.connection.host}")
        return cmd

    def _scp_base(self) -> list[str]:
        cmd = ["scp"]
        if getattr(self.connection, "ssh_key_path", ""):
            cmd.extend(["-i", self.connection.ssh_key_path])
        return cmd

    def _run_ssh(self, remote_cmd: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            self._ssh_base() + [remote_cmd],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def _ensure_remote_dirs(self) -> None:
        py = (
            "from pathlib import Path;"
            "root=Path('~/.swarm').expanduser();"
            "(root/'inbox').mkdir(parents=True, exist_ok=True);"
            "(root/'outbox').mkdir(parents=True, exist_ok=True)"
        )
        self._run_ssh(f'python -c "{py}"', timeout=30)

    def _upload_task(self, task_id: str, envelope: dict[str, Any]) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tmp:
            json.dump(envelope, tmp, indent=2)
            tmp_path = tmp.name
        try:
            remote_path = f"{self.connection.user}@{self.connection.host}:{self.remote_root}/inbox/{task_id}.json"
            subprocess.run(
                self._scp_base() + [tmp_path, remote_path],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    def _poll_result(self, task_id: str) -> dict[str, Any]:
        timeout_seconds = int(os.getenv("WINDOWS_CURSOR_TIMEOUT", "7200"))
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            outbox_path = f"{self.remote_root}/outbox/{task_id}.json"
            py = (
                "from pathlib import Path; import sys;"
                "p=Path(sys.argv[1]).expanduser();"
                "print(p.read_text(encoding='utf-8') if p.exists() else '')"
            )
            proc = self._run_ssh(f'python -c "{py}" "{outbox_path}"', timeout=30)
            body = proc.stdout.strip()
            if body:
                result = json.loads(body)
                result.setdefault("execution_mode", "cursor")
                return result
            time.sleep(5)
        raise TimeoutError(f"Timed out waiting for Cursor worker result: {task_id}")
