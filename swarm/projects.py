"""Project registry and project scaffolding helpers."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
import shutil


@dataclass
class ProjectRecord:
    name: str
    repo_path: str = ""
    repo_url: str = ""
    builder_type: str = ""
    execution_mode: str = ""
    active: bool = True


class ProjectRegistry:
    def __init__(self, registry_path: str = "") -> None:
        default_path = Path.home() / ".swarm" / "projects.yaml"
        self.path = Path(registry_path).expanduser() if registry_path else default_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_projects(self) -> list[dict]:
        records = self._load()
        return [asdict(records[name]) for name in sorted(records)]

    def get_project(self, name: str) -> ProjectRecord | None:
        return self._load().get(name)

    def add_project(
        self,
        name: str,
        repo_path: str = "",
        repo_url: str = "",
        builder_type: str = "",
        execution_mode: str = "",
        active: bool = True,
    ) -> ProjectRecord:
        records = self._load()
        record = ProjectRecord(
            name=name,
            repo_path=repo_path,
            repo_url=repo_url,
            builder_type=builder_type,
            execution_mode=execution_mode,
            active=active,
        )
        records[name] = record
        self._save(records)
        return record

    def remove_project(self, name: str) -> bool:
        records = self._load()
        if name not in records:
            return False
        del records[name]
        self._save(records)
        return True

    def _load(self) -> dict[str, ProjectRecord]:
        if not self.path.exists():
            return {}
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        records: dict[str, ProjectRecord] = {}
        for name, payload in data.items():
            records[name] = ProjectRecord(
                name=name,
                repo_path=payload.get("repo_path", ""),
                repo_url=payload.get("repo_url", ""),
                builder_type=payload.get("builder_type", ""),
                execution_mode=payload.get("execution_mode", ""),
                active=bool(payload.get("active", True)),
            )
        return records

    def _save(self, records: dict[str, ProjectRecord]) -> None:
        serializable = {name: asdict(rec) for name, rec in records.items()}
        self.path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")


def spawn_project_from_template(
    name: str,
    description: str = "",
    template: str = "empty",
    repo_path: str = "",
) -> str:
    root = Path(repo_path).expanduser() if repo_path else Path.cwd()
    project_dir = root / name
    if project_dir.exists():
        raise FileExistsError(f"Project path already exists: {project_dir}")

    template_root = Path(__file__).resolve().parent.parent / "templates" / "projects"
    src = template_root / template
    if not src.is_dir():
        raise ValueError(f"Unknown template: {template}")

    shutil.copytree(src, project_dir)
    description_text = description or f"{name} project scaffold"
    for path in project_dir.rglob("*"):
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            content = content.replace("__PROJECT_NAME__", name).replace("__DESCRIPTION__", description_text)
            path.write_text(content, encoding="utf-8")
    return str(project_dir)
