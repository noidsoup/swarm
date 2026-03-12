"""Redis-backed task store for the swarm queue.

Falls back to an in-memory dict if Redis is unavailable — useful for
local dev without Docker.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from swarm.task_models import TaskResult, TaskStatus, new_task_id, utcnow_iso


class TaskStore:
    """Manages task state in Redis (or in-memory fallback)."""

    def __init__(self) -> None:
        self._redis = None
        self._memory: dict[str, dict] = {}
        redis_url = os.getenv("REDIS_URL", "")
        if redis_url:
            try:
                import redis
                self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
            except Exception:
                self._redis = None

    @property
    def _use_redis(self) -> bool:
        return self._redis is not None

    def _key(self, task_id: str) -> str:
        return f"swarm:task:{task_id}"

    def create(self, feature: str, plan: str = "", builder_type: str = "",
               repo_url: str = "") -> TaskResult:
        task_id = new_task_id()
        task = TaskResult(
            task_id=task_id,
            status=TaskStatus.QUEUED,
            feature=feature,
            plan=plan,
            builder_type=builder_type,
            repo_url=repo_url,
            created_at=utcnow_iso(),
        )
        self._save(task)
        if self._use_redis:
            self._redis.rpush("swarm:queue", task_id)
        return task

    def get(self, task_id: str) -> Optional[TaskResult]:
        if self._use_redis:
            raw = self._redis.get(self._key(task_id))
            if raw:
                return TaskResult(**json.loads(raw))
            return None
        data = self._memory.get(task_id)
        return TaskResult(**data) if data else None

    def list_all(self) -> list[TaskResult]:
        if self._use_redis:
            keys = self._redis.keys("swarm:task:*")
            tasks = []
            for k in sorted(keys):
                raw = self._redis.get(k)
                if raw:
                    tasks.append(TaskResult(**json.loads(raw)))
            return tasks
        return [TaskResult(**d) for d in self._memory.values()]

    def update(self, task: TaskResult) -> None:
        self._save(task)

    def append_log(self, task_id: str, message: str) -> None:
        task = self.get(task_id)
        if task:
            task.log.append(message)
            self._save(task)

    def next_queued(self) -> Optional[str]:
        if self._use_redis:
            return self._redis.lpop("swarm:queue")
        for tid, data in self._memory.items():
            status = data.get("status")
            if status in (TaskStatus.QUEUED, TaskStatus.QUEUED.value):
                return tid
        return None

    def _save(self, task: TaskResult) -> None:
        data = task.model_dump()
        if self._use_redis:
            self._redis.set(self._key(task.task_id), json.dumps(data))
        else:
            self._memory[task.task_id] = data


store = TaskStore()
