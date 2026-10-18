"""Тесты MCP-клиента (fake/mock) и MCP CRM на демо-данных."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import ai_assistant.mcp_client as mcp_client
from ai_assistant.mcp_client import MCPCRMClient, ProjectMCP, format_mcp_line, parse_tool_result
from ai_assistant.mcp_crm import get_ticket, get_user, list_user_tickets
from ai_assistant.models import GitBranch

DEMO_DATA = Path(__file__).resolve().parents[1] / "demo"


def test_parse_structured_content() -> None:
    result = SimpleNamespace(structured_content={"branch": "main", "head": "abc1234", "dirty": False}, content=[])
    assert parse_tool_result(result)["branch"] == "main"


def test_parse_text_json() -> None:
    result = SimpleNamespace(
        structured_content=None,
        content=[SimpleNamespace(text='{"id": "T-1001"}')],
        is_error=False,
    )
    assert parse_tool_result(result) == {"id": "T-1001"}


def test_project_mcp_git_branch_with_mock(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        mcp_client,
        "call_mcp_tool",
        lambda *args, **kwargs: {"branch": "main", "head": "abc1234", "dirty": False},
    )
    branch = ProjectMCP(tmp_path).git_branch()
    assert branch == GitBranch(branch="main", head="abc1234", dirty=False)
    assert format_mcp_line(branch) == "MCP: branch=main, head=abc1234, dirty=false"


def test_crm_client_with_mock(monkeypatch, tmp_path: Path) -> None:
    def fake_call(params, tool, arguments=None, timeout=None):
        if tool == "get_ticket":
            return {
                "id": "T-1001",
                "user_id": "U-001",
                "subject": "Не работает авторизация",
                "status": "open",
                "product": "AiAssistant",
                "messages": ["Не может войти"],
            }
        if tool == "get_user":
            return {"id": "U-001", "name": "Тест", "role": "viewer", "plan": "basic"}
        return []

    monkeypatch.setattr(mcp_client, "call_mcp_tool", fake_call)
    client = MCPCRMClient(tmp_path)
    ticket = client.get_ticket("T-1001")
    user = client.get_user("U-001")
    assert ticket is not None and ticket.status == "open"
    assert user is not None and user.role == "viewer"
    assert client.list_user_tickets("U-001") == []


def test_crm_data_layer() -> None:
    ticket = get_ticket(DEMO_DATA, "T-1001")
    user = get_user(DEMO_DATA, "U-001")
    tickets = list_user_tickets(DEMO_DATA, "U-001")
    assert ticket is not None
    assert ticket["subject"] == "Не работает авторизация"
    assert user is not None and user["role"] == "viewer"
    assert [item["id"] for item in tickets] == ["T-1001"]
    assert get_ticket(DEMO_DATA, "T-9999") is None
