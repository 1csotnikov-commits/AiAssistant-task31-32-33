"""MCP-сервер проекта: git_branch, list_files, git_diff."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from ai_assistant import __version__
from ai_assistant.config import get_settings
from ai_assistant.git_tools import git_branch as read_git_branch
from ai_assistant.git_tools import git_diff as read_git_diff
from ai_assistant.git_tools import list_files as read_list_files


def create_project_server(repo: Path) -> MCPServer:
    """Создаёт stdio MCP-сервер, привязанный к каталогу repo."""
    root = repo.resolve()
    server = MCPServer(
        name="aiassistant-project",
        version=__version__,
        instructions="Инструменты чтения git-контекста проекта AiAssistant.",
    )

    @server.tool()
    def git_branch() -> dict[str, Any]:
        """Вернуть текущую ветку, короткий HEAD и наличие незакоммиченных изменений."""
        branch = read_git_branch(root)
        return {"branch": branch.branch, "head": branch.head, "dirty": branch.dirty}

    @server.tool()
    def list_files(glob: str = "**/*") -> list[str]:
        """Список файлов внутри репозитория по glob-шаблону (не более 500)."""
        return read_list_files(root, glob)

    @server.tool()
    def git_diff(base: str, head: str = "HEAD") -> str:
        """Unified diff base...head, ограниченный по размеру."""
        limit = get_settings().max_diff_chars
        return read_git_diff(root, base, head, max_chars=limit)

    return server


def run_project_server(repo: Path) -> None:
    """Запуск stdio-сервера (блокирующий вызов)."""
    create_project_server(repo).run("stdio")
