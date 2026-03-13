"""FastAPI gateway for remote swarm task submission.

Endpoints:
    POST /tasks          — submit a new swarm task
    GET  /tasks          — list all tasks
    GET  /tasks/{id}     — task status + result
    GET  /tasks/{id}/log — stream logs (SSE)
    DELETE /tasks/{id}   — cancel a task
    GET  /health         — service health + GPU status
    GET  /models         — list available Ollama models
    GET  /gpu            — GPU utilization snapshot

Run via: uvicorn swarm.api:app --host 0.0.0.0 --port 9000
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from swarm.config import default_ollama_base_url
from swarm.task_models import TaskRequest, TaskStatus
from swarm.task_store import store

app = FastAPI(
    title="AI Dev Swarm API",
    description="Remote task submission gateway for the multi-agent coding swarm.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SWARM_API_TOKEN = os.getenv("SWARM_API_TOKEN", "")

OLLAMA_URL = default_ollama_base_url()


@app.middleware("http")
async def auth_middleware(request, call_next):
    if not SWARM_API_TOKEN:
        return await call_next(request)
    if request.url.path in ("/health", "/docs", "/openapi.json"):
        return await call_next(request)
    auth = request.headers.get("authorization", "")
    if auth != f"Bearer {SWARM_API_TOKEN}":
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


def _task_response(task) -> dict:
    payload = task.model_dump()
    for key in (
        "context_summary",
        "retrieval_summary",
        "validation_summary",
        "eval_summary",
        "adaptation_summary",
        "artifacts_dir",
    ):
        payload.setdefault(key, "")
    payload.setdefault("lessons", [])
    payload.setdefault("comparison", {})
    return payload


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@app.post("/tasks", status_code=201)
async def create_task(req: TaskRequest):
    """Submit a new swarm task. Returns the task ID immediately."""
    task = store.create(
        feature=req.feature,
        plan=req.plan,
        builder_type=req.builder_type,
        repo_url=req.repo_url,
    )
    return {"task_id": task.task_id, "status": task.status}


@app.get("/tasks")
async def list_tasks(status: Optional[str] = None):
    """List all tasks, optionally filtered by status."""
    tasks = store.list_all()
    if status:
        tasks = [t for t in tasks if t.status == status]
    return [{k: v for k, v in _task_response(t).items() if k != "log"} for t in tasks]


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get full task details including result."""
    task = store.get(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return _task_response(task)


@app.get("/tasks/{task_id}/log")
async def stream_log(task_id: str):
    """Stream task logs via Server-Sent Events."""
    task = store.get(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")

    async def event_generator():
        last_idx = 0
        while True:
            current = store.get(task_id)
            if not current:
                break
            new_lines = current.log[last_idx:]
            for line in new_lines:
                yield {"event": "log", "data": line}
            last_idx = len(current.log)
            if current.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                yield {"event": "done", "data": json.dumps({
                    "status": current.status,
                    "task_id": task_id,
                })}
                break
            await asyncio.sleep(2)

    return EventSourceResponse(event_generator())


@app.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a queued or running task."""
    task = store.get(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
        return {"message": f"Task already {task.status}"}
    task.status = TaskStatus.CANCELLED
    store.update(task)
    return {"message": f"Task {task_id} cancelled"}


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Service health including Ollama and Redis status."""
    ollama_ok = False
    ollama_models = []
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            if resp.status_code == 200:
                ollama_ok = True
                ollama_models = [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass

    redis_ok = store._use_redis
    tasks = store.list_all()
    return {
        "status": "healthy" if ollama_ok else "degraded",
        "ollama": {"connected": ollama_ok, "models": ollama_models},
        "redis": {"connected": redis_ok},
        "tasks": {
            "total": len(tasks),
            "queued": sum(1 for t in tasks if t.status == TaskStatus.QUEUED),
            "running": sum(1 for t in tasks if t.status == TaskStatus.RUNNING),
            "completed": sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in tasks if t.status == TaskStatus.FAILED),
        },
    }


@app.get("/models")
async def list_models():
    """List models available in Ollama."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise HTTPException(502, f"Cannot reach Ollama: {e}")


@app.get("/gpu")
async def gpu_status():
    """GPU utilization snapshot via nvidia-smi."""
    import subprocess
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,temperature.gpu,utilization.gpu,"
                "utilization.memory,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return {"error": "nvidia-smi failed", "stderr": result.stderr}

        gpus = []
        for line in result.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 7:
                gpus.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "temperature_c": int(parts[2]),
                    "gpu_utilization_pct": int(parts[3]),
                    "memory_utilization_pct": int(parts[4]),
                    "memory_used_mb": int(parts[5]),
                    "memory_total_mb": int(parts[6]),
                })
        return {"gpus": gpus}
    except FileNotFoundError:
        return {"error": "nvidia-smi not found (no GPU or not in PATH)"}
    except Exception as e:
        return {"error": str(e)}
