"""Cursor-to-Cursor task transport via SSH inbox/outbox files."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any

from swarm.task_models import new_task_id, utcnow_iso

logger = logging.getLogger(__name__)

# Retries for outbox replace (Windows can raise PermissionError when file is read over SSH)
_WRITE_RESULT_RETRIES = 3
_WRITE_RESULT_RETRY_SLEEP = 0.2


def _atomic_replace(src: Path, dst: Path) -> None:
    """Replace dst with src, with retries for Windows PermissionError (e.g. reader has handle)."""
    last: BaseException | None = None
    for attempt in range(_WRITE_RESULT_RETRIES):
        try:
            src.replace(dst)
            return
        except OSError as e:
            last = e
            if attempt < _WRITE_RESULT_RETRIES - 1:
                time.sleep(_WRITE_RESULT_RETRY_SLEEP)
    # Final attempt: unlink target then replace (helps if reader held handle)
    try:
        dst.unlink(missing_ok=True)
        src.replace(dst)
        return
    except OSError as e:
        last = e
    raise last  # type: ignore[misc]


class CursorWorkerClient:
    def __init__(self, connection: Any) -> None:
        self.connection = connection
        self.remote_root = os.getenv("WINDOWS_CURSOR_QUEUE_ROOT", "~/.swarm")

    def submit(self, payload: dict[str, Any]) -> str:
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
        return task_id

    def wait(self, task_id: str) -> dict[str, Any]:
        return self._poll_result(task_id)

    def submit_and_wait(self, payload: dict[str, Any]) -> dict[str, Any]:
        task_id = self.submit(payload)
        return self.wait(task_id)

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
            "from pathlib import Path; import sys;"
            "root=Path(sys.argv[1]).expanduser();"
            "(root/'inbox').mkdir(parents=True, exist_ok=True);"
            "(root/'outbox').mkdir(parents=True, exist_ok=True)"
        )
        self._run_ssh(f'python -c "{py}" "{self.remote_root}"', timeout=30)

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

    def _remote_file_exists(self, path: str) -> bool:
        py = (
            "from pathlib import Path; import sys;"
            "p=Path(sys.argv[1]).expanduser();"
            "print('1' if p.exists() else '0')"
        )
        proc = self._run_ssh(f'python -c "{py}" "{path}"', timeout=30)
        return proc.stdout.strip() == "1"

    def _read_remote_json(self, path: str) -> dict[str, Any] | None:
        py = (
            "from pathlib import Path; import sys;"
            "p=Path(sys.argv[1]).expanduser();"
            "print(p.read_text(encoding='utf-8') if p.exists() else '')"
        )
        proc = self._run_ssh(f'python -c "{py}" "{path}"', timeout=30)
        body = proc.stdout.strip()
        if not body:
            return None
        return json.loads(body)

    @staticmethod
    def _is_terminal_status(status: str) -> bool:
        return status.lower() in {"complete", "completed", "error", "failed", "cancelled"}

    def get_result(self, task_id: str) -> dict[str, Any] | None:
        outbox_path = f"{self.remote_root}/outbox/{task_id}.json"
        result = self._read_remote_json(outbox_path)
        if result is None:
            return None
        result.setdefault("execution_mode", "cursor")
        return result

    def get_status(self, task_id: str) -> dict[str, Any]:
        result = self.get_result(task_id)
        if result is not None:
            status = str(result.get("status", "")).lower()
            if not status:
                status = "running"
            result["status"] = status
            return result

        inbox_path = f"{self.remote_root}/inbox/{task_id}.json"
        if self._remote_file_exists(inbox_path):
            return {
                "status": "queued",
                "task_id": task_id,
                "execution_mode": "cursor",
            }
        return {
            "status": "not_found",
            "task_id": task_id,
            "execution_mode": "cursor",
        }

    def cancel(self, task_id: str) -> dict[str, Any]:
        status_payload = self.get_status(task_id)
        status = str(status_payload.get("status", "")).lower()
        if status == "queued":
            py = (
                "from pathlib import Path; import json, sys, datetime;"
                "root=Path(sys.argv[1]).expanduser();"
                "task_id=sys.argv[2];"
                "inbox=root/'inbox'/f'{task_id}.json';"
                "outbox=root/'outbox'/f'{task_id}.json';"
                "inbox.unlink(missing_ok=True);"
                "now=datetime.datetime.now(datetime.timezone.utc).isoformat();"
                "payload={'status':'cancelled','task_id':task_id,'execution_mode':'cursor',"
                "'error':'Cancelled before execution','started_at':now,'completed_at':now};"
                "outbox.parent.mkdir(parents=True, exist_ok=True);"
                "outbox.write_text(json.dumps(payload, indent=2), encoding='utf-8');"
            )
            self._run_ssh(f'python -c "{py}" "{self.remote_root}" "{task_id}"', timeout=30)
            return {
                "status": "cancelled",
                "task_id": task_id,
                "execution_mode": "cursor",
                "message": "Cancelled before execution.",
            }
        if status == "running":
            return {
                "status": "cancel_requested",
                "task_id": task_id,
                "execution_mode": "cursor",
                "message": "Task is already running; cooperative cancellation is not yet supported.",
            }
        if self._is_terminal_status(status):
            return {
                "status": "already_finished",
                "task_id": task_id,
                "execution_mode": "cursor",
                "result": status_payload,
            }
        return {
            "status": "not_found",
            "task_id": task_id,
            "execution_mode": "cursor",
            "message": "Task not found in cursor inbox/outbox.",
        }

    def _poll_result(self, task_id: str) -> dict[str, Any]:
        timeout_seconds = int(os.getenv("WINDOWS_CURSOR_TIMEOUT", "7200"))
        heartbeat_grace_seconds = float(
            os.getenv("WINDOWS_CURSOR_HEARTBEAT_TIMEOUT", str(max(timeout_seconds, 30)))
        )
        deadline = time.time() + timeout_seconds
        last_progress_ts = time.time()
        last_heartbeat = ""
        seen_running_output = False
        while time.time() < deadline:
            result = self.get_result(task_id)
            if result:
                status = str(result.get("status", "")).lower()
                if self._is_terminal_status(status):
                    return result

                seen_running_output = True
                heartbeat = str(result.get("heartbeat_at", "") or result.get("started_at", ""))
                if heartbeat and heartbeat != last_heartbeat:
                    last_heartbeat = heartbeat
                    last_progress_ts = time.time()
                    deadline = time.time() + timeout_seconds
            elif seen_running_output and time.time() - last_progress_ts > heartbeat_grace_seconds:
                raise TimeoutError(f"Cursor worker heartbeat stalled for task: {task_id}")
            time.sleep(5)
        raise TimeoutError(f"Timed out waiting for Cursor worker result: {task_id}")


class CursorWorkerService:
    """Process queued cursor-worker tasks from inbox to outbox."""

    def __init__(
        self,
        root: str | Path | None = None,
        dispatcher: Any | None = None,
        task_timeout_seconds: float | None = None,
        heartbeat_interval: float = 5.0,
    ) -> None:
        self.root = Path(root or Path.home() / ".swarm").expanduser()
        self.inbox = self.root / "inbox"
        self.outbox = self.root / "outbox"
        self.dispatcher = dispatcher or self._build_dispatcher()
        self.task_timeout_seconds = (
            float(task_timeout_seconds)
            if task_timeout_seconds is not None
            else float(os.getenv("WINDOWS_CURSOR_TASK_TIMEOUT", "3600"))
        )
        self.heartbeat_interval = max(float(heartbeat_interval), 0.1)
        self._write_lock = threading.Lock()
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.outbox.mkdir(parents=True, exist_ok=True)

    def _build_dispatcher(self) -> Any:
        from swarm.config import cfg
        from swarm.dispatch import Dispatcher

        return Dispatcher(cfg)

    def process_once(self) -> bool:
        task_path = self._next_task_path()
        if task_path is None:
            return False

        try:
            payload = self._read_task(task_path)
        except Exception as exc:
            result = {
                "status": "error",
                "error": str(exc),
                "build_summary": "",
                "review_feedback": "",
                "quality_report": "",
                "polish_report": "",
            }
            if self._safe_finalize_result(task_path.stem, result):
                task_path.unlink(missing_ok=True)
                return True
            return False

        task_id = str(payload.get("task_id") or task_path.stem)
        started_at = utcnow_iso()
        stop_heartbeat = threading.Event()
        heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(task_id, payload, started_at, stop_heartbeat),
            daemon=True,
        )
        heartbeat_thread.start()

        result_holder: dict[str, Any] = {}
        error_holder: dict[str, BaseException] = {}
        worker_thread = threading.Thread(
            target=self._dispatch_task,
            args=(payload, result_holder, error_holder),
            daemon=True,
        )
        worker_thread.start()
        worker_thread.join(timeout=self.task_timeout_seconds if self.task_timeout_seconds > 0 else None)
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=1)

        if worker_thread.is_alive():
            result = {
                "status": "error",
                "error": f"Cursor worker task timed out after {self.task_timeout_seconds:.0f}s",
                "build_summary": "",
                "review_feedback": "",
                "quality_report": "",
                "polish_report": "",
            }
        elif error_holder:
            exc = next(iter(error_holder.values()))
            result = {
                "status": "error",
                "error": str(exc),
                "build_summary": "",
                "review_feedback": "",
                "quality_report": "",
                "polish_report": "",
            }
        else:
            result = dict(result_holder.get("result") or {})
            result.setdefault("status", "complete")

        if self._safe_finalize_result(task_id, result, started_at=started_at):
            task_path.unlink(missing_ok=True)
            return True
        return False

    def run_forever(self, poll_interval: float = 2.0) -> None:
        while True:
            try:
                processed = self.process_once()
            except KeyboardInterrupt:
                raise
            except Exception:
                logger.exception("Cursor worker loop iteration crashed")
                processed = False
            if not processed:
                time.sleep(poll_interval)

    def _next_task_path(self) -> Path | None:
        tasks = sorted(self.inbox.glob("*.json"))
        return tasks[0] if tasks else None

    def _read_task(self, task_path: Path) -> dict[str, Any]:
        try:
            return json.loads(task_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid task payload: {task_path.name}") from exc

    def _dispatch_task(
        self,
        payload: dict[str, Any],
        result_holder: dict[str, Any],
        error_holder: dict[str, BaseException],
    ) -> None:
        try:
            result_holder["result"] = self.dispatcher.dispatch(
                plan=str(payload.get("plan", "")),
                feature_name=str(payload.get("feature_name", "")),
                builder_type=str(payload.get("builder_type", "")),
                repo_path=str(payload.get("repo_path", "")),
                repo_url=str(payload.get("repo_url", "")),
                execution_mode="local",
            )
        except Exception as exc:
            error_holder["error"] = exc

    def _heartbeat_loop(
        self,
        task_id: str,
        payload: dict[str, Any],
        started_at: str,
        stop_event: threading.Event,
    ) -> None:
        while not stop_event.is_set():
            try:
                self._write_result(
                    task_id,
                    {
                        "status": "running",
                        "task_id": task_id,
                        "feature_name": str(payload.get("feature_name", "")),
                        "started_at": started_at,
                        "heartbeat_at": utcnow_iso(),
                        "execution_mode": "cursor",
                    },
                )
            except Exception:
                logger.exception("Failed to write cursor worker heartbeat task_id=%s", task_id)
            stop_event.wait(self.heartbeat_interval)

    def _finalize_result(self, task_id: str, result: dict[str, Any], started_at: str = "") -> None:
        result.setdefault("build_summary", "")
        result.setdefault("review_feedback", "")
        result.setdefault("quality_report", "")
        result.setdefault("polish_report", "")
        result["task_id"] = task_id
        if started_at:
            result.setdefault("started_at", started_at)
        result["completed_at"] = utcnow_iso()
        result["execution_mode"] = "cursor"
        self._write_result(task_id, result)

    def _safe_finalize_result(self, task_id: str, result: dict[str, Any], started_at: str = "") -> bool:
        try:
            self._finalize_result(task_id, result, started_at=started_at)
            return True
        except Exception:
            logger.exception("Failed to write cursor worker result task_id=%s", task_id)
            return False

    def _write_result(self, task_id: str, result: dict[str, Any]) -> None:
        outbox_path = self.outbox / f"{task_id}.json"
        self.outbox.mkdir(parents=True, exist_ok=True)
        with self._write_lock:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                suffix=".tmp",
                prefix=f"{task_id}-",
                dir=self.outbox,
                delete=False,
            ) as tmp:
                json.dump(result, tmp, indent=2)
                temp_path = Path(tmp.name)
            _atomic_replace(temp_path, outbox_path)


def build_cursor_worker_daemon_command(
    *,
    script_path: str | Path,
    root: str | Path | None = None,
    poll_interval: float = 2.0,
    task_timeout_seconds: float | None = None,
    log_file: str | Path | None = None,
    pid_file: str | Path | None = None,
) -> list[str]:
    command = [sys.executable, str(Path(script_path)), "--daemon-child", "--poll-interval", str(poll_interval)]
    if root:
        command.extend(["--root", str(Path(root))])
    if task_timeout_seconds is not None:
        command.extend(["--task-timeout", str(task_timeout_seconds)])
    if log_file:
        command.extend(["--log-file", str(Path(log_file))])
    if pid_file:
        command.extend(["--pid-file", str(Path(pid_file))])
    return command


def spawn_cursor_worker_daemon(
    *,
    script_path: str | Path,
    root: str | Path | None = None,
    poll_interval: float = 2.0,
    task_timeout_seconds: float | None = None,
    log_file: str | Path | None = None,
    pid_file: str | Path | None = None,
) -> int:
    command = build_cursor_worker_daemon_command(
        script_path=script_path,
        root=root,
        poll_interval=poll_interval,
        task_timeout_seconds=task_timeout_seconds,
        log_file=log_file,
        pid_file=pid_file,
    )
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")

    log_handle = subprocess.DEVNULL
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = open(log_path, "a", encoding="utf-8")

    popen_kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
        "env": env,
        "close_fds": True,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        popen_kwargs["start_new_session"] = True

    process = subprocess.Popen(command, **popen_kwargs)
    if log_file and log_handle is not subprocess.DEVNULL:
        log_handle.close()
    if pid_file:
        pid_path = Path(pid_file)
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(process.pid), encoding="utf-8")
    return process.pid
