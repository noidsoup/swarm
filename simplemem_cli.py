#!/usr/bin/env python3
"""Command-line helper for SimpleMem project memory."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from simplemem_client import SimpleMemClient, load_simplemem_settings


def parse_metadata(metadata_args: list[str]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for arg in metadata_args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            metadata[key.strip()] = value.strip()
    return metadata


def import_ai_session(file_path: str, client: SimpleMemClient) -> None:
    """Import sections from AI_SESSION_MEMORY.md."""
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found: {file_path}")
        return

    content = path.read_text(encoding="utf-8")
    sections = re.findall(r"^## (.+?)\n(.*?)(?=\n## |\Z)", content, re.DOTALL | re.MULTILINE)

    if not sections:
        print(f"No sections found in {file_path}")
        return

    print(f"Found {len(sections)} sections to import...", flush=True)
    imported = 0
    for index, (title, body) in enumerate(sections, start=1):
        title = title.strip()
        body = body.strip()
        if not body:
            print(f"  - Skipped section {index}: {title[:50]} (empty body)")
            continue

        lines = body.splitlines()
        summary = "\n".join(lines[:15])
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", title)
        date = date_match.group(1) if date_match else "unknown"

        client.add_memory(
            f"AI Session: {title}\n\n{summary}",
            {
                "source": "ai_session_memory",
                "date": date,
                "session_title": title,
                "session_number": index,
            },
        )
        imported += 1
        print(f"  - Imported section {index}: {title[:60]}...", flush=True)

    print(f"Imported {imported}/{len(sections)} sections")


def import_docs(docs_dir: str, client: SimpleMemClient) -> None:
    """Import markdown files from a docs directory."""
    docs_path = Path(docs_dir)
    if not docs_path.exists():
        print(f"Error: Directory not found: {docs_dir}")
        return

    md_files = sorted(docs_path.rglob("*.md"))
    if not md_files:
        print(f"No .md files found in {docs_dir}")
        return

    print(f"Found {len(md_files)} doc files to import...", flush=True)
    imported = 0
    for index, md_file in enumerate(md_files, start=1):
        content = md_file.read_text(encoding="utf-8").strip()
        if not content:
            continue

        lines = content.splitlines()
        title = lines[0].lstrip("#").strip() if lines[0].startswith("#") else md_file.stem
        summary = "\n".join(lines[:20])
        client.add_memory(
            f"Doc: {title} ({md_file})\n\n{summary}",
            {"source": "docs", "file": str(md_file), "title": title},
        )
        imported += 1
        if index % 10 == 0 or index == len(md_files):
            print(f"  - Imported {index}/{len(md_files)} docs...", flush=True)

    print(f"Done: imported {imported}/{len(md_files)} docs", flush=True)


def sync_all(client: SimpleMemClient) -> None:
    """Clear local store and re-import known project sources."""
    local_path = Path(client.settings.local_dir) / "memories.json"
    if local_path.exists():
        local_path.write_text("[]", encoding="utf-8")
        print("Cleared local memory store", flush=True)

    for path in ("AI_SESSION_MEMORY.md", "AI_RUNBOOK.md"):
        if Path(path).exists():
            print(f"Importing {path}", flush=True)
            import_ai_session(path, client)
        else:
            print(f"Skipped {path} (not found)")

    if Path("docs").exists():
        print("Importing docs/", flush=True)
        import_docs("docs", client)

    if local_path.exists():
        memories = json.loads(local_path.read_text(encoding="utf-8"))
        print(f"Sync complete: {len(memories)} memories", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="SimpleMem CLI")
    subparsers = parser.add_subparsers(dest="cmd", help="Commands")

    add_parser = subparsers.add_parser("add", help="Add a memory entry")
    add_parser.add_argument("--text", required=True, help="Memory text")
    add_parser.add_argument("--metadata", nargs="*", default=[], help="key=value pairs")

    query_parser = subparsers.add_parser("query", help="Query memories")
    query_parser.add_argument("--question", required=True, help="Question to ask")
    query_parser.add_argument("--format", choices=["text", "json"], default="text")

    import_parser = subparsers.add_parser("import-ai-session", help="Import AI session memory")
    import_parser.add_argument("--path", required=True, help="Path to AI_SESSION_MEMORY.md")

    docs_parser = subparsers.add_parser("import-docs", help="Import markdown docs")
    docs_parser.add_argument("--dir", default="docs", help="Docs directory")

    subparsers.add_parser("sync", help="Re-import everything into the local store")

    args = parser.parse_args()
    settings = load_simplemem_settings()
    client = SimpleMemClient(settings)

    if not settings.enabled:
        print("Warning: SimpleMem is disabled. Set SIMPLEMEM_ENABLED=true in .env.")
        return

    if args.cmd == "add":
        client.add_memory(args.text, parse_metadata(args.metadata))
        print("Memory added")
    elif args.cmd == "query":
        result = client.query(args.question)
        if args.format == "json":
            print(result)
        else:
            data = json.loads(result)
            results = data.get("results", [])
            print(f"Found {len(results)} results:\n")
            for index, item in enumerate(results, start=1):
                content = item.get("content", item.get("text", str(item))) if isinstance(item, dict) else str(item)
                print(f"{index}. {content[:200]}...")
    elif args.cmd == "import-ai-session":
        import_ai_session(args.path, client)
    elif args.cmd == "import-docs":
        import_docs(args.dir, client)
    elif args.cmd == "sync":
        sync_all(client)


if __name__ == "__main__":
    main()
