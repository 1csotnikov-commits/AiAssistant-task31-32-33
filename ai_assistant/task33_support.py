"""Задача 33: FastAPI-ассистент поддержки с контекстом тикета и пользователя."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import uvicorn
from fastapi import FastAPI, HTTPException

from ai_assistant import APP_NAME, __version__
from ai_assistant.config import Settings, get_settings
from ai_assistant.index import Index, ensure_index
from ai_assistant.llm import LLM, get_llm
from ai_assistant.mcp_client import MCPCRMClient
from ai_assistant.models import HelpRequest, HelpResponse, Ticket, User
from ai_assistant.rag import answer_question

SERVICE_DESCRIPTION = (
    "Ассистент поддержки: отвечает по FAQ/документации с учётом тикета и пользователя. "
    "Контекст тикета и пользователя получается через MCP CRM."
)


class CRMClientProtocol(Protocol):
    def get_ticket(self, ticket_id: str) -> Ticket | None: ...

    def get_user(self, user_id: str) -> User | None: ...


def ticket_prompt_context(ticket: Ticket, user: User | None) -> str:
    messages = "\n".join(f"- {message}" for message in ticket.messages) or "- нет сообщений"
    user_line = (
        f"Пользователь: id={user.id}, имя={user.name}, роль={user.role}, тариф={user.plan}"
        if user
        else "Пользователь: не найден"
    )
    return "\n".join(
        [
            f"Тикет: id={ticket.id}, статус={ticket.status}, тема={ticket.subject}, продукт={ticket.product}",
            "Сообщения тикета:",
            messages,
            user_line,
        ]
    )


def create_app(
    repo: Path | None = None,
    data: Path | None = None,
    llm: LLM | None = None,
    crm: CRMClientProtocol | None = None,
    index: Index | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """Фабрика приложения с внедряемыми зависимостями для тестов."""
    config = settings or get_settings()
    repo_path = (repo or Path.cwd()).resolve()
    data_path = (data or (config.data_dir / "data")).expanduser().resolve()
    crm_client: CRMClientProtocol = crm or MCPCRMClient(data_path)
    rag_index, _ = (index, None) if index is not None else ensure_index(repo_path, config)

    app = FastAPI(title=f"{APP_NAME} Support", version=__version__, description=SERVICE_DESCRIPTION)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "aiassistant-support",
            "version": __version__,
            "repo": str(repo_path),
            "data": str(data_path),
            "index": str(rag_index.path),
            "chunks": rag_index.count(),
        }

    @app.post("/help", response_model=HelpResponse)
    def help_endpoint(request: HelpRequest) -> HelpResponse:
        if not request.question.strip():
            raise HTTPException(status_code=422, detail="question не должен быть пустым")
        try:
            ticket = crm_client.get_ticket(request.ticket_id)
        except Exception as exc:  # noqa: BLE001 - MCP/CRM недоступен
            raise HTTPException(status_code=503, detail=f"MCP CRM недоступен: {exc}") from exc
        if ticket is None:
            raise HTTPException(status_code=404, detail=f"Тикет {request.ticket_id} не найден")
        user_id = request.user_id or ticket.user_id
        user: User | None = None
        if user_id:
            try:
                user = crm_client.get_user(user_id)
            except Exception as exc:  # noqa: BLE001 - тикет важнее пользователя
                user = None
                app.state.last_crm_error = str(exc)

        query = " ".join([request.question, ticket.subject, ticket.product, *ticket.messages])
        chunks = rag_index.search(query, k=config.top_k, kind="doc")
        mcp_line = f"MCP CRM: ticket={ticket.id}, user={user.id if user else 'не найден'}"
        result = answer_question(
            request.question,
            chunks,
            llm or get_llm(),
            extra_context=ticket_prompt_context(ticket, user),
            mcp_line=mcp_line,
        )
        return HelpResponse(
            answer=result.answer,
            sources=result.sources,
            ticket=ticket.model_dump(),
            user=user.model_dump() if user else None,
            mcp=mcp_line,
        )

    return app


def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    repo: Path | None = None,
    data: Path | None = None,
) -> None:
    """Запуск uvicorn с фабрикой приложения."""
    app = create_app(repo=repo, data=data)
    uvicorn.run(app, host=host, port=port, log_level="info")
