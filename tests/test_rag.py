"""Тесты RAG: контекст, цитаты, запрет галлюцинаций без контекста."""

from __future__ import annotations

from ai_assistant.models import RetrievedChunk
from ai_assistant.rag import NO_CONTEXT_ANSWER, answer_question, format_sources
from tests.fakes import FakeLLM


def make_chunk(path: str = "docs/rag.md", title: str = "Как устроен RAG") -> RetrievedChunk:
    return RetrievedChunk(
        id=f"{path}:1-5",
        path=path,
        title=title,
        kind="doc",
        start_line=1,
        end_line=5,
        text="RAG использует FTS5.",
    )


def test_format_sources_deduplicates() -> None:
    block = format_sources([make_chunk(), make_chunk()])
    assert block.count("docs/rag.md") == 1
    assert "«Как устроен RAG»" in block


def test_answer_appends_sources() -> None:
    llm = FakeLLM("RAG использует SQLite FTS5.")
    result = answer_question("Как устроен RAG?", [make_chunk()], llm, mcp_line="MCP: branch=main")
    assert "Источники:" in result.answer
    assert "docs/rag.md" in result.answer
    assert result.sources == ["docs/rag.md → «Как устроен RAG»"]
    assert llm.last_prompt.find("Как устроен RAG?") >= 0


def test_no_context_does_not_call_llm() -> None:
    llm = FakeLLM()
    result = answer_question("Есть ли квантовый модуль?", [], llm)
    assert llm.calls == []
    assert result.answer.startswith(NO_CONTEXT_ANSWER.split(":")[0])
    assert result.sources == []


def test_prompt_contains_extra_context() -> None:
    llm = FakeLLM("Ответ.")
    answer_question("Вопрос", [make_chunk()], llm, extra_context="Git: branch=main")
    assert "Git: branch=main" in llm.last_prompt
