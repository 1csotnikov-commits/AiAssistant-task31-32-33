"""Тесты задачи 31: /help с fake LLM и фиксированными чанками."""

from __future__ import annotations

from pathlib import Path

from ai_assistant import task31_cli
from ai_assistant.index import Index
from ai_assistant.models import GitBranch
from ai_assistant.task31_cli import ask_question, run_chat
from tests.fakes import FakeLLM


class FakeProjectMCP:
    def git_branch(self) -> GitBranch:
        return GitBranch(branch="main", head="abc1234", dirty=False)

    def list_files(self, glob: str = "**/*") -> list[str]:
        return ["README.md", "docs/rag.md"]

    def git_diff(self, base: str, head: str = "HEAD") -> str:
        return "diff --git a/README.md b/README.md"


def test_ask_question_returns_citations_and_mcp_line(demo_repo: Path, demo_index: Index) -> None:
    llm = FakeLLM("Проект делает RAG по документации.")
    answer = ask_question(
        demo_repo,
        "Что делает проект?",
        llm=llm,
        index=demo_index,
        project_client=FakeProjectMCP(),
    )
    assert "Источники:" in answer.answer
    assert any(item.startswith("README.md") for item in answer.sources)
    assert answer.mcp_line == "MCP: branch=main, head=abc1234, dirty=false"
    assert "branch=main" in llm.last_prompt


def test_chat_help_prints_sources_and_mcp(
    demo_repo: Path, demo_index: Index, monkeypatch
) -> None:
    monkeypatch.setattr(task31_cli, "ensure_index", lambda repo: (demo_index, None))
    answers = iter(["/help Как устроен RAG?", "/exit"])
    output: list[str] = []
    run_chat(
        demo_repo,
        llm=FakeLLM("RAG использует FTS5."),
        project_client=FakeProjectMCP(),
        input_fn=lambda prompt: next(answers),
        output_fn=output.append,
    )
    text = "\n".join(output)
    assert "Источники:" in text
    assert "MCP: branch=main" in text


def test_chat_branch_command(demo_repo: Path, demo_index: Index, monkeypatch) -> None:
    monkeypatch.setattr(task31_cli, "ensure_index", lambda repo: (demo_index, None))
    answers = iter(["/branch", "/exit"])
    output: list[str] = []
    run_chat(
        demo_repo,
        llm=FakeLLM(),
        project_client=FakeProjectMCP(),
        input_fn=lambda prompt: next(answers),
        output_fn=output.append,
    )
    assert any("MCP: branch=main, head=abc1234, dirty=false" in line for line in output)
