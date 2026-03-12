#!/usr/bin/env python3
"""
SimpleMem client for persistent project memory.

Supports:
- MCP backend for cloud storage
- local JSON fallback storage under uncommitted/simplemem/
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


@dataclass
class SimpleMemSettings:
    enabled: bool
    backend: str
    mcp_url: str
    token: str | None
    user_id: str | None
    namespace: str
    local_dir: str
    dry_run: bool


def load_simplemem_settings() -> SimpleMemSettings:
    """Load settings from the repo-local .env."""
    load_dotenv()
    return SimpleMemSettings(
        enabled=os.getenv("SIMPLEMEM_ENABLED", "false").lower() == "true",
        backend=os.getenv("SIMPLEMEM_BACKEND", "mcp"),
        mcp_url=os.getenv("SIMPLEMEM_MCP_URL", "https://mcp.simplemem.cloud/mcp"),
        token=os.getenv("SIMPLEMEM_TOKEN"),
        user_id=os.getenv("SIMPLEMEM_USER_ID"),
        namespace=os.getenv("SIMPLEMEM_NAMESPACE", "my-project"),
        local_dir=os.getenv("SIMPLEMEM_LOCAL_DIR", "uncommitted/simplemem"),
        dry_run=os.getenv("SIMPLEMEM_DRY_RUN", "false").lower() == "true",
    )


def _unwrap_mcp_tool_text(tool_result: dict[str, Any]) -> str | None:
    content = tool_result.get("content")
    if not isinstance(content, list) or not content:
        return None
    first = content[0]
    if not isinstance(first, dict) or first.get("type") != "text":
        return None
    text = first.get("text")
    return text if isinstance(text, str) else None


def _parse_json_if_possible(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _to_fact_like_content(
    text: str,
    namespace: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Format content as a concrete fact sentence for better extraction."""
    del metadata
    now = time.strftime("%Y-%m-%d", time.gmtime())
    if not text.strip():
        return f"On {now} {namespace} recorded an event with no details."
    if " | " in text:
        return f"On {now} {namespace}: {text.replace(' | ', ', ')}."
    return f"On {now} {namespace} recorded: {text}"


class SimpleMemClient:
    """Simple client for storing and retrieving project memory."""

    def __init__(self, settings: SimpleMemSettings):
        self.settings = settings
        self._session_id: str | None = None
        self._local_db_path = Path(self.settings.local_dir) / "memories.json"
        self._local_db_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._local_db_path.exists():
            self._local_db_path.write_text("[]", encoding="utf-8")

    def _ensure_mcp_session(self) -> None:
        if self._session_id or not self.settings.token:
            return

        headers = {
            "Authorization": f"Bearer {self.settings.token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {"roots": {"listChanged": True}, "sampling": {}},
                "clientInfo": {
                    "name": f"{self.settings.namespace}-simplemem-client",
                    "version": "1.0.0",
                },
            },
        }
        response = requests.post(self.settings.mcp_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        session_id = response.headers.get("Mcp-Session-Id") or response.headers.get("mcp-session-id")
        if not session_id:
            raise RuntimeError("SimpleMem MCP initialize did not return Mcp-Session-Id")

        self._session_id = session_id
        requests.post(
            self.settings.mcp_url,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers={**headers, "Mcp-Session-Id": self._session_id},
            timeout=30,
        )

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.token:
            raise RuntimeError("SIMPLEMEM_TOKEN not set for MCP backend")

        self._ensure_mcp_session()
        response = requests.post(
            self.settings.mcp_url,
            json={"jsonrpc": "2.0", "id": "1", "method": method, "params": params},
            headers={
                "Authorization": f"Bearer {self.settings.token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": self._session_id or "",
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise RuntimeError(f"SimpleMem MCP error: {payload['error']}")
        return payload.get("result", {})

    def _read_local_memories(self) -> list[dict[str, Any]]:
        return json.loads(self._local_db_path.read_text(encoding="utf-8"))

    def _write_local_memories(self, memories: list[dict[str, Any]]) -> None:
        self._local_db_path.write_text(json.dumps(memories, indent=2), encoding="utf-8")

    def _add_local(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        memories = self._read_local_memories()
        memories.append(
            {
                "id": f"local_{int(time.time() * 1000)}",
                "text": text,
                "metadata": metadata or {},
                "namespace": self.settings.namespace,
                "timestamp": time.time(),
            }
        )
        self._write_local_memories(memories)

    def _query_local(self, question: str) -> str:
        words = question.lower().split()
        memories = self._read_local_memories()

        def matches(memory: dict[str, Any]) -> bool:
            haystack = memory.get("text", "").lower()
            metadata = memory.get("metadata", {})
            for value in metadata.values():
                haystack += f" {value}".lower()
            return all(word in haystack for word in words)

        results = [memory for memory in memories if matches(memory)]
        return json.dumps({"results": results[:10], "total": len(results), "source": "local"})

    def add_memory(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Add memory, falling back to local storage on failures."""
        if not self.settings.enabled:
            return
        if self.settings.dry_run:
            print(f"[SimpleMem DRY RUN] Would add memory: {text[:100]}...", flush=True)
            return

        if self.settings.backend == "local":
            self._add_local(text, metadata)
            return

        try:
            content = _to_fact_like_content(text, self.settings.namespace, metadata)
            result = self._rpc(
                "tools/call",
                {
                    "name": "memory_add",
                    "arguments": {
                        "speaker": self.settings.namespace,
                        "content": content,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                },
            )
            parsed = _parse_json_if_possible(_unwrap_mcp_tool_text(result))
            if isinstance(parsed, dict) and parsed.get("entries_created") == 0:
                self._add_local(text, metadata)
        except Exception as exc:
            print(f"[SimpleMem WARNING] Failed cloud add, storing locally: {exc}", flush=True)
            self._add_local(text, metadata)

    def query(self, question: str) -> str:
        """Query memory store, falling back to local results."""
        if not self.settings.enabled:
            return json.dumps({"results": [], "message": "SimpleMem disabled"})

        if self.settings.backend == "local":
            return self._query_local(question)

        try:
            result = self._rpc(
                "tools/call",
                {"name": "memory_retrieve", "arguments": {"query": question, "top_k": 10}},
            )
            text = _unwrap_mcp_tool_text(result)
            parsed = _parse_json_if_possible(text)
            if isinstance(parsed, dict) and parsed.get("total", 0) == 0:
                return self._query_local(question)
            return text or json.dumps(result)
        except Exception as exc:
            print(f"[SimpleMem WARNING] Query failed, using local fallback: {exc}", flush=True)
            return self._query_local(question)

    def log_run(self, summary: dict[str, Any]) -> None:
        """Log a run summary after sanitizing obviously sensitive fields."""
        sensitive = {"token", "password", "secret", "api_key", "auth"}
        sanitized: dict[str, Any] = {}
        for key, value in summary.items():
            if any(marker in key.lower() for marker in sensitive):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, (dict, list)):
                sanitized[key] = f"{type(value).__name__}({len(value) if hasattr(value, '__len__') else '?'})"
            else:
                sanitized[key] = value

        parts = [f"Run: {summary.get('operation', 'unknown')}"]
        if "count" in summary:
            parts.append(f"Processed {summary['count']} items")
        if "errors" in summary:
            parts.append(f"Errors: {summary['errors']}")
        if "duration" in summary:
            parts.append(f"Duration: {summary['duration']}s")

        self.add_memory(
            " | ".join(parts),
            {
                "type": "run_log",
                "namespace": self.settings.namespace,
                "timestamp": time.time(),
                **sanitized,
            },
        )
