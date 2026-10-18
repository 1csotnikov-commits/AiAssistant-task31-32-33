"""Тесты задачи 32: review по diff с fake LLM."""

from __future__ import annotations

from pathlib import Path

from ai_assistant.index import Index
from ai_assistant.task32_review import REVIEW_SECTIONS, ensure_sections, review, write_review
from tests.conftest import REVIEW_RESPONSE
from tests.fakes import FakeLLM


def test_review_offline_diff_has_sections(demo_repo: Path, demo_index: Index) -> None:
    llm = FakeLLM(REVIEW_RESPONSE)
    markdown = review(demo_repo, diff_file=Path("demo/pr.diff"), llm=llm, index=demo_index)
    for section in REVIEW_SECTIONS:
        assert section in markdown
    assert "average" in llm.last_prompt
    assert "Ты — строгий" in llm.last_prompt or "ревьюер" in llm.last_prompt
    assert "## Источники" in markdown


def test_review_empty_diff() -> None:
    # review() без git и с пустым diff-файлом возвращает структурированный ответ.
    import tempfile
    from pathlib import Path as P

    with tempfile.TemporaryDirectory() as directory:
        empty = P(directory) / "empty.diff"
        empty.write_text("", encoding="utf-8")
        markdown = review(P(directory), diff_file=empty, llm=FakeLLM())
    for section in REVIEW_SECTIONS:
        assert section in markdown
    assert "Diff пуст" in markdown


def test_ensure_sections_adds_missing_and_sources() -> None:
    markdown = ensure_sections("## Потенциальные баги\n\n- Проблема.", [], [])
    assert "## Архитектурные проблемы" in markdown
    assert "## Рекомендации" in markdown
    assert "## Недостающие тесты" in markdown
    assert "## Источники" in markdown
    assert "RAG-контекст не найден" in markdown


def test_write_review(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "review.md"
    result = write_review("# Ревью\n", output)
    assert result == output
    assert output.read_text(encoding="utf-8") == "# Ревью\n"
