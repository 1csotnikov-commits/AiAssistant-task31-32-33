"""Тесты индекса FTS5 и инкрементальной переиндексации."""

from __future__ import annotations

from pathlib import Path

from ai_assistant.config import Settings
from ai_assistant.index import Index


def test_index_builds_and_retrieves_docs(demo_repo: Path, settings: Settings) -> None:
    index = Index(demo_repo, index_path=settings.data_dir / "idx.sqlite", settings=settings)
    stats = index.build()
    assert stats.files >= 4
    assert stats.chunks > 0
    results = index.search("Как устроен RAG?", k=5, kind="doc")
    assert results
    assert any(item.path == "docs/rag.md" for item in results)


def test_index_reindexes_only_changed_files(demo_repo: Path, settings: Settings) -> None:
    index = Index(demo_repo, index_path=settings.data_dir / "idx.sqlite", settings=settings)
    first = index.build()
    second = index.build()
    assert second.added_files == 0
    assert second.unchanged_files == first.files
    assert second.chunks == first.chunks

    (demo_repo / "docs" / "rag.md").write_text("# RAG\n\n## Новый раздел\n\nОбновлённый текст.\n", encoding="utf-8")
    third = index.build()
    assert third.added_files == 1
    assert third.removed_files == 0

    (demo_repo / "docs" / "faq.md").unlink()
    fourth = index.build()
    assert fourth.removed_files == 1


def test_index_code_search_and_substring_fallback(demo_repo: Path, settings: Settings) -> None:
    index = Index(demo_repo, index_path=settings.data_dir / "idx.sqlite", settings=settings)
    index.build()
    code = index.search("increment", k=5, kind="code")
    assert code
    assert all(item.kind == "code" for item in code)

    # Слово с нестандартным написанием не найдётся FTS, но сработает LIKE-fallback.
    fallback = index.search("АвторизацияSSO", k=5, kind="doc")
    assert isinstance(fallback, list)


def test_empty_index_search_returns_nothing(tmp_path: Path, settings: Settings) -> None:
    repo = tmp_path / "empty"
    repo.mkdir()
    index = Index(repo, index_path=settings.data_dir / "empty.sqlite", settings=settings)
    assert index.search("что угодно") == []
