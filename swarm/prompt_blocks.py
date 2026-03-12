"""Helpers for composing bounded worker prompts from reusable sections."""

from __future__ import annotations


def _truncate(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)] + "..."


def build_context_block(context_pack: dict, max_chars: int = 350) -> str:
    if not context_pack:
        return ""

    lines = ["REPO CONTEXT:"]
    repo_summary = context_pack.get("repo_summary")
    if repo_summary:
        lines.append(f"- Summary: {repo_summary}")
    builder_hint = context_pack.get("builder_hint")
    if builder_hint:
        lines.append(f"- Builder hint: {builder_hint}")
    instructions = context_pack.get("instructions", [])
    if instructions:
        lines.append(f"- Instructions: {', '.join(instructions[:3])}")
    risk_areas = context_pack.get("risk_areas", [])
    if risk_areas:
        lines.append(f"- Risk areas: {', '.join(risk_areas[:3])}")

    if len(lines) == 1:
        return ""
    return _truncate("\n".join(lines), max_chars)


def build_retrieval_block(retrieval_pack: dict, max_chars: int = 350) -> str:
    if not retrieval_pack:
        return ""

    lines = ["RETRIEVAL HINTS:"]
    files = retrieval_pack.get("files", [])
    if files:
        lines.append("- Relevant files: " + ", ".join(item.get("path", "") for item in files[:3]))
    memories = retrieval_pack.get("memories", [])
    if memories:
        memory_text = str(memories[0].get("text", ""))
        if memory_text:
            lines.append(f"- Prior lesson: {_truncate(memory_text, 180)}")

    if len(lines) == 1:
        return ""
    return _truncate("\n".join(lines), max_chars)


def build_constraints_block(constraints: list[str], max_chars: int = 250) -> str:
    if not constraints:
        return ""
    lines = ["CONSTRAINTS:"]
    lines.extend(f"- {constraint}" for constraint in constraints[:5] if constraint)
    if len(lines) == 1:
        return ""
    return _truncate("\n".join(lines), max_chars)


def compose_task_prompt(
    *,
    task_text: str,
    context_block: str = "",
    retrieval_block: str = "",
    constraints_block: str = "",
    output_format: str = "",
    max_chars: int = 4000,
) -> str:
    sections = [f"TASK:\n{task_text.strip()}"]
    for block in (context_block, retrieval_block, constraints_block):
        if block.strip():
            sections.append(block.strip())
    if output_format.strip():
        sections.append(f"OUTPUT FORMAT:\n{output_format.strip()}")

    prompt = "\n\n".join(sections)
    return _truncate(prompt, max_chars)
