from __future__ import annotations

from pathlib import Path

from swarm.retrieval import build_retrieval_pack, retrieve_relevant_files


class FakeMemoryClient:
    def query_json(self, question: str) -> dict:
        assert "auth" in question.lower()
        return {
            "results": [
                {
                    "text": "Previous auth fix required stronger session validation.",
                    "metadata": {"type": "lesson", "repo_kind": "nextjs"},
                }
            ],
            "total": 1,
            "source": "local",
        }


def test_retrieve_relevant_files_favors_component_examples_for_react_tasks(tmp_path: Path) -> None:
    (tmp_path / "src" / "components").mkdir(parents=True)
    (tmp_path / "src" / "components" / "DashboardCard.tsx").write_text("export const X = 1\n", encoding="utf-8")
    (tmp_path / "src" / "pages").mkdir(parents=True)
    (tmp_path / "src" / "pages" / "index.tsx").write_text("export default function Page() {}\n", encoding="utf-8")
    (tmp_path / "server.py").write_text("print('hello')\n", encoding="utf-8")

    files = retrieve_relevant_files(
        str(tmp_path),
        "Add a dashboard card component",
        {"builder_hint": "react_dev", "stack": {"frameworks": ["nextjs", "react"]}},
    )

    assert files
    assert files[0]["path"].endswith("src/components/DashboardCard.tsx")
    assert len(files) <= 5


def test_retrieve_relevant_files_favors_test_files_for_fix_regression_tasks(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_auth.py").write_text("def test_login(): pass\n", encoding="utf-8")
    (tmp_path / "auth_service.py").write_text("def login(): return True\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("misc\n", encoding="utf-8")

    files = retrieve_relevant_files(
        str(tmp_path),
        "Fix auth regression and add a test",
        {"builder_hint": "python_dev", "stack": {"frameworks": ["python"]}},
    )

    assert files
    assert files[0]["path"].endswith("tests/test_auth.py")


def test_build_retrieval_pack_includes_structured_memory_hits(tmp_path: Path) -> None:
    (tmp_path / "auth_service.py").write_text("def login(): return True\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_auth.py").write_text("def test_login(): pass\n", encoding="utf-8")

    pack = build_retrieval_pack(
        str(tmp_path),
        "Fix auth bug",
        {
            "builder_hint": "python_dev",
            "stack": {"frameworks": ["python"]},
        },
        memory_client=FakeMemoryClient(),
    )

    assert pack["files"]
    assert pack["memories"]
    assert pack["memories"][0]["text"].startswith("Previous auth fix")
    assert pack["memory_source"] == "local"
