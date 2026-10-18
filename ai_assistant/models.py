"""Pydantic-модели ядра, MCP и HTTP-слоя."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ChunkKind = Literal["doc", "code"]


class Chunk(BaseModel):
    """Фрагмент документации или кода, попадающий в FTS5."""

    id: str
    path: str
    title: str
    kind: ChunkKind = "doc"
    start_line: int = 1
    end_line: int = 1
    text: str


class RetrievedChunk(Chunk):
    """Чанк с оценкой релевантности."""

    score: float = 0.0


class GitBranch(BaseModel):
    branch: str
    head: str
    dirty: bool


class IndexStats(BaseModel):
    repo: str
    index_path: str
    files: int = 0
    added_files: int = 0
    removed_files: int = 0
    unchanged_files: int = 0
    chunks: int = 0


class Ticket(BaseModel):
    id: str
    user_id: str
    subject: str = ""
    status: str = "open"
    product: str = ""
    messages: list[str] = Field(default_factory=list)


class User(BaseModel):
    id: str
    name: str = ""
    role: str = ""
    plan: str = ""


class TicketContext(BaseModel):
    ticket: Ticket | None = None
    user: User | None = None
    source: str = "mcp"


class RAGAnswer(BaseModel):
    question: str
    answer: str
    sources: list[str] = Field(default_factory=list)
    mcp_line: str = ""


class ReviewRequest(BaseModel):
    repo: str
    base: str = "main"
    head: str = "HEAD"
    diff_file: str | None = None
    output: str | None = None


class HelpRequest(BaseModel):
    ticket_id: str
    question: str
    user_id: str | None = None


class HelpResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
    ticket: dict[str, Any] | None = None
    user: dict[str, Any] | None = None
    mcp: str = ""
