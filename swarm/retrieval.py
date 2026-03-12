"""Targeted retrieval helpers for files and prior lessons."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from simplemem_client import SimpleMemClient, load_simplemem_settings


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 1}


def _path_tokens(path: Path) -> set[str]:
    return _tokenize(path.as_posix().replace("_", " ").replace("-", " "))


def _iter_candidate_files(repo_root: Path) -> list[Path]:
    candidates: list[Path] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part.startswith(".") and part not in {".cursor"} for part in path.parts):
            continue
        if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".json"}:
            continue
        candidates.append(path)
    return candidates


def _score_file(path: Path, request_tokens: set[str], context_pack: dict) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    path_token_set = _path_tokens(path)
    path_text = path.as_posix().lower()

    overlaps = request_tokens & path_token_set
    if overlaps:
        score += 4 * len(overlaps)
        reasons.append(f"token match: {', '.join(sorted(overlaps))}")

    builder_hint = context_pack.get("builder_hint", "")
    frameworks = context_pack.get("stack", {}).get("frameworks", [])

    if builder_hint == "react_dev" or any(fw in {"nextjs", "react"} for fw in frameworks):
        if path.suffix.lower() in {".tsx", ".jsx"}:
            score += 4
            reasons.append("react file type")
        if any(part in path_text for part in ("components", "pages", "app", "src")):
            score += 3
            reasons.append("react directory")

    if builder_hint == "python_dev" or "python" in frameworks:
        if path.suffix.lower() == ".py":
            score += 3
            reasons.append("python file type")
        if "swarm" in path_text or "tests" in path_text:
            score += 2
            reasons.append("python directory")

    if request_tokens & {"fix", "bug", "regression", "test", "tests"}:
        if "tests" in path.parts or path.name.startswith("test_"):
            score += 6
            reasons.append("test-focused task")

    if request_tokens & {"component", "page", "ui", "dashboard"}:
        if any(part in path_text for part in ("components", "pages", "app")):
            score += 4
            reasons.append("ui-focused task")

    if request_tokens & {"auth", "login", "session", "oauth"} and any(
        word in path_text for word in ("auth", "login", "session")
    ):
        score += 5
        reasons.append("auth-focused task")

    if path.name.lower() in {"readme.md", "agents.md"} and request_tokens & {"docs", "document", "setup"}:
        score += 3
        reasons.append("documentation task")

    return score, reasons


def retrieve_relevant_files(repo_root: str, feature_request: str, context_pack: dict, limit: int = 5) -> list[dict]:
    root = Path(repo_root)
    request_tokens = _tokenize(feature_request)
    scored: list[tuple[int, Path, list[str]]] = []
    for path in _iter_candidate_files(root):
        score, reasons = _score_file(path.relative_to(root), request_tokens, context_pack)
        if score <= 0:
            continue
        scored.append((score, path.relative_to(root), reasons))

    scored.sort(key=lambda item: (-item[0], item[1].as_posix()))
    return [
        {"path": path.as_posix(), "score": score, "reasons": reasons}
        for score, path, reasons in scored[:limit]
    ]


def retrieve_relevant_memories(
    feature_request: str,
    context_pack: dict,
    memory_client: SimpleMemClient | Any | None = None,
    limit: int = 5,
) -> tuple[list[dict], str]:
    client = memory_client
    if client is None:
        try:
            client = SimpleMemClient(load_simplemem_settings())
        except Exception:
            return [], "unavailable"

    query_terms = [feature_request]
    builder_hint = context_pack.get("builder_hint", "")
    if builder_hint:
        query_terms.append(builder_hint)
    risk_areas = context_pack.get("risk_areas", [])
    if risk_areas:
        query_terms.append(" ".join(risk_areas[:2]))

    result = client.query_json(" ".join(term for term in query_terms if term).strip())
    memories = result.get("results", []) if isinstance(result, dict) else []
    return memories[:limit], result.get("source", "unknown") if isinstance(result, dict) else "unknown"


def summarize_retrieval_pack(retrieval_pack: dict) -> str:
    file_names = ", ".join(item["path"] for item in retrieval_pack.get("files", [])[:3]) or "no file hits"
    memory_count = len(retrieval_pack.get("memories", []))
    return f"Relevant files: {file_names}. Memory hits: {memory_count}."


def build_retrieval_pack(
    repo_root: str,
    feature_request: str,
    context_pack: dict,
    memory_client: SimpleMemClient | Any | None = None,
) -> dict:
    files = retrieve_relevant_files(repo_root, feature_request, context_pack)
    memories, memory_source = retrieve_relevant_memories(feature_request, context_pack, memory_client=memory_client)
    return {
        "files": files,
        "memories": memories,
        "memory_source": memory_source,
    }
