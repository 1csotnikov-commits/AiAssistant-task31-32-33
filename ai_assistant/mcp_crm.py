"""MCP-сервер CRM на синтетических JSON-данных."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from ai_assistant import __version__


class CRMDataError(RuntimeError):
    """Некорректные или отсутствующие данные CRM."""


def load_crm_data(data_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Читает tickets.json + users.json или единый JSON-файл."""
    path = data_path.expanduser()
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
    elif path.is_dir():
        combined = path / "crm.json"
        if combined.is_file():
            payload = json.loads(combined.read_text(encoding="utf-8"))
        else:
            payload = {}
            tickets_file = path / "tickets.json"
            users_file = path / "users.json"
            if tickets_file.is_file():
                tickets_payload = json.loads(tickets_file.read_text(encoding="utf-8"))
                payload["tickets"] = (
                    tickets_payload.get("tickets", []) if isinstance(tickets_payload, dict) else tickets_payload
                )
            if users_file.is_file():
                users_payload = json.loads(users_file.read_text(encoding="utf-8"))
                payload["users"] = users_payload.get("users", []) if isinstance(users_payload, dict) else users_payload
    else:
        raise CRMDataError(f"Каталог/файл данных CRM не найден: {path}")
    tickets = payload.get("tickets", [])
    users = payload.get("users", [])
    if not isinstance(tickets, list) or not isinstance(users, list):
        raise CRMDataError("JSON CRM должен содержать списки tickets и users.")
    return {"tickets": tickets, "users": users}


def _find(items: list[dict[str, Any]], key: str, value: str) -> dict[str, Any] | None:
    for item in items:
        if str(item.get(key, "")).lower() == str(value).lower():
            return dict(item)
    return None


def get_ticket(data_path: Path, ticket_id: str) -> dict[str, Any] | None:
    return _find(load_crm_data(data_path)["tickets"], "id", ticket_id)


def get_user(data_path: Path, user_id: str) -> dict[str, Any] | None:
    return _find(load_crm_data(data_path)["users"], "id", user_id)


def list_user_tickets(data_path: Path, user_id: str) -> list[dict[str, Any]]:
    return [
        dict(ticket)
        for ticket in load_crm_data(data_path)["tickets"]
        if str(ticket.get("user_id", "")).lower() == str(user_id).lower()
    ]


def create_crm_server(data_path: Path) -> MCPServer:
    """Создаёт stdio MCP-сервер CRM."""
    data = data_path.expanduser()
    server = MCPServer(
        name="aiassistant-crm",
        version=__version__,
        instructions="Доступ к синтетическим тикетам и пользователям службы поддержки.",
    )

    @server.tool(name="get_ticket")
    def _get_ticket_tool(ticket_id: str) -> dict[str, Any] | None:
        """Вернуть тикет по идентификатору или null."""
        return get_ticket(data, ticket_id)

    @server.tool(name="get_user")
    def _get_user_tool(user_id: str) -> dict[str, Any] | None:
        """Вернуть пользователя по идентификатору или null."""
        return get_user(data, user_id)

    @server.tool(name="list_user_tickets")
    def _list_user_tickets_tool(user_id: str) -> list[dict[str, Any]]:
        """Вернуть все тикеты пользователя."""
        return list_user_tickets(data, user_id)

    return server


def run_crm_server(data_path: Path) -> None:
    """Запуск stdio-сервера (блокирующий вызов)."""
    create_crm_server(data_path).run("stdio")
