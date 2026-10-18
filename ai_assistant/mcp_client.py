"""MCP-клиент: запускает stdio-сервер и вызывает инструменты."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from ai_assistant.config import get_settings
from ai_assistant.models import GitBranch, Ticket, User


class MCPClientError(RuntimeError):
    """MCP-сервер недоступен или вернул ошибку."""


def _environment() -> dict[str, str]:
    env = os.environ.copy()
    package_root = str(Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"] = package_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def project_server_params(repo: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "ai_assistant", "mcp", "project", "--repo", str(repo.resolve())],
        env=_environment(),
    )


def crm_server_params(data_path: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "ai_assistant", "mcp", "crm", "--data", str(data_path.expanduser())],
        env=_environment(),
    )


def parse_tool_result(result: Any) -> Any:
    """Достаёт dict/list из structured_content или JSON-текста."""
    if getattr(result, "is_error", False):
        text = _result_text(result)
        raise MCPClientError(text or "MCP-инструмент вернул ошибку.")
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        if set(structured) == {"result"}:
            return structured["result"]
        return structured
    text = _result_text(result)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _result_text(result: Any) -> str:
    parts: list[str] = []
    for item in getattr(result, "content", None) or []:
        text = getattr(item, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def format_mcp_line(branch: GitBranch) -> str:
    return f"MCP: branch={branch.branch}, head={branch.head}, dirty={str(branch.dirty).lower()}"


async def call_mcp_tool_async(
    params: StdioServerParameters,
    tool: str,
    arguments: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> Any:
    """Открывает stdio-сессию, вызывает инструмент и закрывает её."""
    settings = get_settings()
    limit = timeout or settings.mcp_timeout_seconds

    async def _run() -> Any:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=limit) as session:
                await session.initialize()
                result = await session.call_tool(tool, arguments or {})
                return parse_tool_result(result)

    try:
        return await asyncio.wait_for(_run(), timeout=limit)
    except TimeoutError as exc:
        raise MCPClientError(f"MCP-сервер не ответил за {limit:.0f} с (инструмент {tool}).") from exc
    except MCPClientError:
        raise
    except Exception as exc:  # noqa: BLE001 - единая ошибка клиента
        raise MCPClientError(f"Ошибка MCP ({tool}): {exc}") from exc


def call_mcp_tool(
    params: StdioServerParameters,
    tool: str,
    arguments: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> Any:
    """Синхронная обёртка; не вызывать из работающего event loop."""
    return asyncio.run(call_mcp_tool_async(params, tool, arguments, timeout))


class ProjectMCP:
    """Высокоуровневый клиент MCP project server."""

    def __init__(self, repo: Path, timeout: float | None = None) -> None:
        self.repo = repo.resolve()
        self.timeout = timeout

    def git_branch(self) -> GitBranch:
        payload = call_mcp_tool(project_server_params(self.repo), "git_branch", timeout=self.timeout)
        if not isinstance(payload, dict):
            raise MCPClientError(f"Неожиданный ответ git_branch: {payload!r}")
        return GitBranch(
            branch=str(payload.get("branch", "")),
            head=str(payload.get("head", "")),
            dirty=bool(payload.get("dirty", False)),
        )

    def list_files(self, glob: str = "**/*") -> list[str]:
        payload = call_mcp_tool(
            project_server_params(self.repo), "list_files", {"glob": glob}, timeout=self.timeout
        )
        return [str(item) for item in payload] if isinstance(payload, list) else []

    def git_diff(self, base: str, head: str = "HEAD") -> str:
        payload = call_mcp_tool(
            project_server_params(self.repo), "git_diff", {"base": base, "head": head}, timeout=self.timeout
        )
        return payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)


class MCPCRMClient:
    """Высокоуровневый клиент MCP CRM server."""

    def __init__(self, data_path: Path, timeout: float | None = None) -> None:
        self.data_path = data_path.expanduser()
        self.timeout = timeout

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        payload = call_mcp_tool(
            crm_server_params(self.data_path), "get_ticket", {"ticket_id": ticket_id}, timeout=self.timeout
        )
        return Ticket.model_validate(payload) if isinstance(payload, dict) else None

    def get_user(self, user_id: str) -> User | None:
        payload = call_mcp_tool(
            crm_server_params(self.data_path), "get_user", {"user_id": user_id}, timeout=self.timeout
        )
        return User.model_validate(payload) if isinstance(payload, dict) else None

    def list_user_tickets(self, user_id: str) -> list[Ticket]:
        payload = call_mcp_tool(
            crm_server_params(self.data_path), "list_user_tickets", {"user_id": user_id}, timeout=self.timeout
        )
        if not isinstance(payload, list):
            return []
        return [Ticket.model_validate(item) for item in payload]
