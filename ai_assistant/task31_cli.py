"""Задача 31: ассистент разработчика — ask и интерактивный чат."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from ai_assistant.index import Index, ensure_index
from ai_assistant.llm import LLM, get_llm
from ai_assistant.mcp_client import MCPClientError, ProjectMCP, format_mcp_line
from ai_assistant.models import GitBranch, RAGAnswer, RetrievedChunk
from ai_assistant.rag import answer_question as rag_answer
from ai_assistant.rag import render

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]


def branch_context(branch: GitBranch | None) -> str:
    if branch is None:
        return "Git-контекст: MCP недоступен."
    return f"Git: branch={branch.branch}, head={branch.head}, dirty={str(branch.dirty).lower()}"


def resolve_branch(repo: Path, project_client: ProjectMCP | None = None) -> tuple[GitBranch | None, str]:
    """Получает ветку через MCP, не роняя ассистента при сбое сервера."""
    client = project_client or ProjectMCP(repo)
    try:
        branch = client.git_branch()
    except MCPClientError as exc:
        return None, f"MCP: недоступен ({exc})"
    return branch, format_mcp_line(branch)


def ask_question(
    repo: Path,
    question: str,
    llm: LLM | None = None,
    index: Index | None = None,
    project_client: ProjectMCP | None = None,
    top_k: int = 5,
    use_mcp: bool = True,
) -> RAGAnswer:
    """RAG по README/docs + git-контекст через MCP + ответ с цитатами."""
    if index is None:
        index, _ = ensure_index(repo)
    chunks: Sequence[RetrievedChunk] = index.search(question, k=top_k, kind="doc")
    branch: GitBranch | None = None
    mcp_line = ""
    if use_mcp:
        branch, mcp_line = resolve_branch(repo, project_client)
    return rag_answer(
        question,
        chunks,
        llm or get_llm(),
        extra_context=branch_context(branch),
        mcp_line=mcp_line,
    )


def ask_and_print(
    repo: Path,
    question: str,
    llm: LLM | None = None,
    index: Index | None = None,
    project_client: ProjectMCP | None = None,
) -> str:
    answer = ask_question(repo, question, llm=llm, index=index, project_client=project_client)
    text = render(answer)
    print(text)
    return text


HELP_TEXT = """Команды:
  /help <вопрос>  — RAG-ответ по README/docs с цитатами и MCP-строкой
  /branch         — ветка, HEAD и dirty через MCP
  /files [glob]   — список файлов через MCP
  /diff           — diff HEAD~1..HEAD через MCP
  /exit           — выход
Простой текст без команды трактуется как вопрос к /help."""


def run_chat(
    repo: Path,
    llm: LLM | None = None,
    project_client: ProjectMCP | None = None,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
) -> None:
    """Интерактивный цикл. Зависимости инжектируются для тестов."""
    index, stats = ensure_index(repo)
    client = project_client or ProjectMCP(repo)
    output_fn(f"AiAssistant chat. Репозиторий: {repo.resolve()}")
    if stats:
        output_fn(f"Индекс построен: {stats.chunks} чанков.")
    output_fn(HELP_TEXT)
    while True:
        try:
            raw = input_fn("Вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            output_fn("\nВыход.")
            return
        if not raw:
            continue
        if raw in {"/exit", "/quit", "exit", "quit"}:
            output_fn("Выход.")
            return
        try:
            if raw.startswith("/help"):
                question = raw[5:].strip()
                if not question:
                    output_fn("Укажите вопрос: /help Что делает проект?")
                    continue
                answer = ask_question(repo, question, llm=llm, index=index, project_client=client)
                output_fn("")
                output_fn(render(answer))
                output_fn("")
            elif raw == "/branch":
                try:
                    output_fn(format_mcp_line(client.git_branch()))
                except MCPClientError as exc:
                    output_fn(f"MCP: недоступен ({exc})")
            elif raw.startswith("/files"):
                glob = raw[6:].strip() or "**/*"
                try:
                    files = client.list_files(glob)
                    output_fn("\n".join(files[:50]) if files else "(файлов не найдено)")
                except MCPClientError as exc:
                    output_fn(f"MCP: недоступен ({exc})")
            elif raw == "/diff":
                try:
                    diff = client.git_diff("HEAD~1", "HEAD")
                    output_fn(diff or "(изменений нет)")
                except MCPClientError as exc:
                    output_fn(f"MCP: недоступен ({exc})")
            else:
                answer = ask_question(repo, raw, llm=llm, index=index, project_client=client)
                output_fn("")
                output_fn(render(answer))
                output_fn("")
        except Exception as exc:  # noqa: BLE001 - чат не должен падать
            output_fn(f"Ошибка: {exc}")
