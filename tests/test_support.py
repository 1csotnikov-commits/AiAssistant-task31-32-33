"""Тесты задачи 33: FastAPI /health и /help через TestClient."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ai_assistant.config import Settings
from ai_assistant.index import Index
from ai_assistant.models import Ticket, User
from ai_assistant.task33_support import create_app
from tests.fakes import FakeLLM


class FakeCRM:
    def __init__(self) -> None:
        self.ticket = Ticket(
            id="T-1001",
            user_id="U-001",
            subject="Не работает авторизация",
            status="open",
            product="AiAssistant",
            messages=["Пользователь не может войти после смены роли"],
        )
        self.user = User(id="U-001", name="Тестовый пользователь", role="viewer", plan="basic")

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        return self.ticket if ticket_id == "T-1001" else None

    def get_user(self, user_id: str) -> User | None:
        return self.user if user_id == "U-001" else None


def build_client(
    demo_repo: Path,
    demo_index: Index,
    settings: Settings,
    llm: FakeLLM | None = None,
    index: Index | None = None,
) -> tuple[TestClient, FakeLLM]:
    fake_llm = llm or FakeLLM("Проверьте роль пользователя: viewer не имеет доступа к SSO.")
    app = create_app(
        repo=demo_repo,
        data=settings.data_dir / "crm",
        llm=fake_llm,
        crm=FakeCRM(),
        index=index or demo_index,
        settings=settings,
    )
    return TestClient(app), fake_llm


def test_health(demo_repo: Path, demo_index: Index, settings: Settings) -> None:
    client, _ = build_client(demo_repo, demo_index, settings)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["chunks"] > 0
    assert payload["service"] == "aiassistant-support"


def test_help_uses_ticket_and_user_context(
    demo_repo: Path, demo_index: Index, settings: Settings
) -> None:
    client, llm = build_client(demo_repo, demo_index, settings)
    response = client.post(
        "/help",
        json={"ticket_id": "T-1001", "question": "Почему не работает авторизация?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ticket"]["id"] == "T-1001"
    assert payload["user"]["role"] == "viewer"
    assert payload["mcp"] == "MCP CRM: ticket=T-1001, user=U-001"
    assert any(source.startswith("docs/faq.md") for source in payload["sources"])
    assert "Источники:" in payload["answer"]
    prompt = llm.last_prompt
    assert "роль=viewer" in prompt
    assert "Тикет: id=T-1001" in prompt
    assert "docs/faq.md" in prompt
    assert "admin" in prompt


def test_help_unknown_ticket_returns_404(
    demo_repo: Path, demo_index: Index, settings: Settings
) -> None:
    client, _ = build_client(demo_repo, demo_index, settings)
    response = client.post("/help", json={"ticket_id": "T-9999", "question": "Что делать?"})
    assert response.status_code == 404


def test_help_without_docs_does_not_call_llm(
    demo_repo: Path, settings: Settings
) -> None:
    empty_index = Index(demo_repo, index_path=settings.data_dir / "empty.sqlite", settings=settings)
    client, llm = build_client(demo_repo, empty_index, settings, index=empty_index)
    response = client.post(
        "/help",
        json={"ticket_id": "T-1001", "question": "Есть ли квантовый модуль?"},
    )
    assert response.status_code == 200
    assert llm.calls == []
    assert "В документации этого нет" in response.json()["answer"]


def test_default_crm_data_falls_back_to_demo(tmp_path: Path, settings: Settings) -> None:
    from ai_assistant.config import crm_data_path

    repo = tmp_path / "repo"
    (repo / "demo").mkdir(parents=True)
    (repo / "demo" / "tickets.json").write_text('{"tickets": []}', encoding="utf-8")
    assert crm_data_path(repo, settings) == repo / "demo"


def test_help_empty_question_returns_422(
    demo_repo: Path, demo_index: Index, settings: Settings
) -> None:
    client, _ = build_client(demo_repo, demo_index, settings)
    response = client.post("/help", json={"ticket_id": "T-1001", "question": "   "})
    assert response.status_code == 422
