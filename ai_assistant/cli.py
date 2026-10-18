"""CLI `aiassist`: index, ask, chat, review, support serve, mcp project/crm."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ai_assistant import APP_NAME, __version__
from ai_assistant.config import get_settings
from ai_assistant.index import Index
from ai_assistant.llm import LLMError
from ai_assistant.mcp_client import MCPClientError
from ai_assistant.task31_cli import ask_and_print, run_chat
from ai_assistant.task32_review import review, write_review

app = typer.Typer(add_completion=False, no_args_is_help=True, help="AiAssistant: RAG + MCP ассистент (задания 31-33).")
support_app = typer.Typer(help="Задача 33: FastAPI-сервис поддержки.")
mcp_app = typer.Typer(help="MCP stdio-серверы (project, crm).")
app.add_typer(support_app, name="support")
app.add_typer(mcp_app, name="mcp")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"{APP_NAME} {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Показать версию и выйти."),
    ] = False,
) -> None:
    """Общие команды AiAssistant."""


@app.command("index")
def index_command(
    repo: Annotated[Path, typer.Option("--repo", help="Корень репозитория.")] = Path("."),
    force: Annotated[bool, typer.Option("--force", help="Переиндексировать всё.")] = False,
) -> None:
    """Построить/обновить SQLite FTS5-индекс README, docs и кода."""
    repo_path = repo.resolve()
    if not repo_path.is_dir():
        typer.echo(f"Каталог не найден: {repo_path}", err=True)
        raise typer.Exit(1)
    settings = get_settings()
    settings.ensure_dirs()
    index = Index(repo_path)
    stats = index.build(force=force)
    typer.echo(f"Индекс: {stats.index_path}")
    typer.echo(
        f"Файлов: {stats.files}; обновлено: {stats.added_files}; без изменений: {stats.unchanged_files}; "
        f"удалено: {stats.removed_files}; чанков: {stats.chunks}"
    )


@app.command("ask")
def ask_command(
    question: Annotated[str, typer.Argument(help="Вопрос по документации проекта.")],
    repo: Annotated[Path, typer.Option("--repo", help="Корень репозитория.")] = Path("."),
) -> None:
    """RAG-ответ по README/docs с цитатами и MCP-строкой."""
    try:
        ask_and_print(repo.resolve(), question)
    except (LLMError, MCPClientError) as exc:
        typer.echo(f"Ошибка: {exc}", err=True)
        raise typer.Exit(1) from exc


@app.command("chat")
def chat_command(
    repo: Annotated[Path, typer.Option("--repo", help="Корень репозитория.")] = Path("."),
) -> None:
    """Интерактивный чат: /help, /branch, /files, /diff, /exit."""
    run_chat(repo.resolve())


@app.command("review")
def review_command(
    repo: Annotated[Path, typer.Option("--repo", help="Корень репозитория.")] = Path("."),
    base: Annotated[str, typer.Option("--base", help="Базовая git-ссылка.")] = "main",
    head: Annotated[str, typer.Option("--head", help="HEAD-ссылка для сравнения.")] = "HEAD",
    diff_file: Annotated[Path | None, typer.Option("--diff-file", help="Готовый diff вместо git.")] = None,
    output: Annotated[Path | None, typer.Option("--output", help="Куда сохранить review.md.")] = None,
) -> None:
    """Автоматическое Markdown-ревью diff (задача 32)."""
    try:
        markdown = review(repo.resolve(), base=base, head=head, diff_file=diff_file)
    except (LLMError, MCPClientError) as exc:
        typer.echo(f"Ошибка: {exc}", err=True)
        raise typer.Exit(1) from exc
    except Exception as exc:  # noqa: BLE001 - git и файловые ошибки
        typer.echo(f"Ошибка ревью: {exc}", err=True)
        raise typer.Exit(1) from exc
    if output is not None:
        path = write_review(markdown, output)
        typer.echo(f"Ревью сохранено: {path}")
        typer.echo(markdown)
    else:
        typer.echo(markdown)


@support_app.command("serve")
def support_serve(
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port")] = 8000,
    repo: Annotated[Path, typer.Option("--repo", help="Корень репозитория с docs.")] = Path("."),
    data: Annotated[Path | None, typer.Option("--data", help="Каталог JSON CRM.")] = None,
) -> None:
    """Поднять FastAPI-сервис поддержки (задача 33)."""
    from ai_assistant.task33_support import serve

    settings = get_settings()
    data_path = data or (settings.data_dir / "data")
    typer.echo(f"Support service: http://{host}:{port}/docs")
    serve(host=host, port=port, repo=repo.resolve(), data=data_path)


@mcp_app.command("project")
def mcp_project(
    repo: Annotated[Path, typer.Option("--repo", help="Корень репозитория.")] = Path("."),
) -> None:
    """stdio MCP-сервер проекта: git_branch, list_files, git_diff."""
    from ai_assistant.mcp_project import run_project_server

    run_project_server(repo.resolve())


@mcp_app.command("crm")
def mcp_crm(
    data: Annotated[Path | None, typer.Option("--data", help="Каталог/файл JSON CRM.")] = None,
) -> None:
    """stdio MCP-сервер CRM: get_ticket, get_user, list_user_tickets."""
    from ai_assistant.mcp_crm import run_crm_server

    data_path = data or (get_settings().data_dir / "data")
    run_crm_server(data_path.expanduser().resolve())


if __name__ == "__main__":
    app()
