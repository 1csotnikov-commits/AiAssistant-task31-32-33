"""Интеграционные тесты реального stdio MCP (без сети)."""

from __future__ import annotations

from pathlib import Path

from ai_assistant.mcp_client import MCPCRMClient, ProjectMCP

DEMO_DATA = Path(__file__).resolve().parents[1] / "demo"


def test_project_mcp_stdio_git_branch(git_repo: Path) -> None:
    branch = ProjectMCP(git_repo, timeout=60).git_branch()
    assert branch.branch == "main"
    assert len(branch.head) >= 7
    assert branch.dirty is False


def test_crm_mcp_stdio_get_ticket() -> None:
    client = MCPCRMClient(DEMO_DATA, timeout=60)
    ticket = client.get_ticket("T-1001")
    user = client.get_user("U-001")
    assert ticket is not None and ticket.subject == "Не работает авторизация"
    assert user is not None and user.role == "viewer"
