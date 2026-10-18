"""RAG: контекст из чанков, prompt, ответ с обязательными цитатами."""

from __future__ import annotations

from collections.abc import Sequence

from ai_assistant.llm import LLM
from ai_assistant.models import Chunk, RAGAnswer, RetrievedChunk

SYSTEM_PROMPT = """Ты — AiAssistant, помощник по документации проекта.
Отвечай по-русски, кратко и по делу.
Используй ТОЛЬКО предоставленные фрагменты документации и git-контекст.
Если ответа в документации нет, честно напиши: «В документации этого нет» и не выдумывай.
Не ссылайся на файлы, которых нет во фрагментах.
Если уместно, указывай пути и названия разделов."""

NO_CONTEXT_ANSWER = (
    "В документации этого нет: в индексе не найдено релевантных фрагментов. "
    "Уточните вопрос или переиндексируйте проект командой `aiassist index --repo <path>`."
)


def build_context(chunks: Sequence[Chunk]) -> str:
    """Формирует блок фрагментов с путями, строками и заголовками."""
    if not chunks:
        return "(фрагменты не найдены)"
    blocks: list[str] = []
    for number, chunk in enumerate(chunks, start=1):
        blocks.append(
            f"[{number}] {chunk.path}, строки {chunk.start_line}-{chunk.end_line}, "
            f"раздел «{chunk.title}»\n{chunk.text}"
        )
    return "\n\n".join(blocks)


def format_sources(chunks: Sequence[Chunk], limit: int = 5) -> str:
    """Markdown-блок «Источники» без дублей."""
    lines: list[str] = ["Источники:"]
    seen: set[tuple[str, str]] = set()
    for chunk in chunks:
        key = (chunk.path, chunk.title)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- {chunk.path} → «{chunk.title}»")
        if len(seen) >= limit:
            break
    if len(lines) == 1:
        lines.append("- нет: в индексе не найдено подходящих фрагментов")
    return "\n".join(lines)


def source_list(chunks: Sequence[Chunk], limit: int = 5) -> list[str]:
    seen: set[tuple[str, str]] = set()
    result: list[str] = []
    for chunk in chunks:
        key = (chunk.path, chunk.title)
        if key in seen:
            continue
        seen.add(key)
        result.append(f"{chunk.path} → «{chunk.title}»")
        if len(result) >= limit:
            break
    return result


def build_messages(
    question: str,
    chunks: Sequence[Chunk],
    extra_context: str = "",
) -> list[dict[str, str]]:
    user_parts = [f"Вопрос: {question}", "", "Фрагменты документации:", build_context(chunks)]
    if extra_context.strip():
        user_parts.extend(["", "Дополнительный контекст:", extra_context.strip()])
    user_parts.extend(["", "Ответь по-русски, опираясь только на фрагменты выше."])
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def answer_question(
    question: str,
    chunks: Sequence[RetrievedChunk] | Sequence[Chunk],
    llm: LLM,
    extra_context: str = "",
    mcp_line: str = "",
) -> RAGAnswer:
    """Вызывает LLM и гарантированно добавляет блок источников."""
    if not chunks:
        answer = NO_CONTEXT_ANSWER
        if extra_context.strip():
            answer += "\n\nКонтекст тикета учтён, но документация по вопросу не найдена."
        return RAGAnswer(question=question, answer=answer, sources=[], mcp_line=mcp_line)
    response = llm.chat(build_messages(question, chunks, extra_context))
    if "Источники:" not in response:
        response = f"{response.rstrip()}\n\n{format_sources(chunks)}"
    return RAGAnswer(
        question=question,
        answer=response,
        sources=source_list(chunks),
        mcp_line=mcp_line,
    )


def render(answer: RAGAnswer) -> str:
    """Текст для CLI: ответ, MCP-строка, источники уже внутри."""
    parts = [answer.answer.rstrip()]
    if answer.mcp_line:
        parts.append(answer.mcp_line)
    return "\n\n".join(parts)
