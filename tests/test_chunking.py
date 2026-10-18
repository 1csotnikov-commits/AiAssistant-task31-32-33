"""Тесты чанкинга Markdown и Python."""

from __future__ import annotations

from pathlib import Path

from ai_assistant.index import chunk_markdown, chunk_python


def test_markdown_chunks_by_headings(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    text = "# Заголовок\n\nВступление.\n\n## RAG\n\nТекст про RAG.\n\n## MCP\n\nТекст про MCP.\n"
    chunks = chunk_markdown(path, text, tmp_path)
    titles = [chunk.title for chunk in chunks]
    assert "RAG" in titles
    assert "MCP" in titles
    rag = next(chunk for chunk in chunks if chunk.title == "RAG")
    assert "Текст про RAG" in rag.text
    assert rag.start_line <= rag.end_line
    assert rag.id.startswith("doc.md:")


def test_markdown_preamble_gets_file_title(tmp_path: Path) -> None:
    path = tmp_path / "readme.md"
    text = "Вступление без заголовка.\n\n# Раздел\n\nТекст раздела.\n"
    chunks = chunk_markdown(path, text, tmp_path)
    assert chunks[0].title == "readme"
    assert "Вступление" in chunks[0].text


def test_python_chunks_functions_and_methods(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    text = """\"\"\"Module docstring.\"\"\"


def top(value: int) -> int:
    return value + 1


class Service:
    \"\"\"Service.\"\"\"

    def handle(self, value: int) -> int:
        return value * 2
"""
    chunks = chunk_python(path, text, tmp_path)
    titles = {chunk.title for chunk in chunks}
    assert "top" in titles
    assert "Service" in titles
    assert "Service.handle" in titles
    assert all(chunk.kind == "code" for chunk in chunks)
    assert all(chunk.path == "sample.py" for chunk in chunks)
