"""Задача 32: автоматическое ревью diff с RAG по документации и коду."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from ai_assistant.config import get_settings
from ai_assistant.git_tools import changed_files, diff_file_paths, git_diff, read_diff_file
from ai_assistant.index import Index, ensure_index
from ai_assistant.llm import LLM, get_llm
from ai_assistant.models import Chunk
from ai_assistant.rag import build_context, source_list

REVIEW_SECTIONS = [
    "## Потенциальные баги",
    "## Архитектурные проблемы",
    "## Рекомендации",
    "## Недостающие тесты",
    "## Источники",
]

SYSTEM_PROMPT = """Ты — строгий, но прагматичный ревьюер Python-кода.
Анализируй ТОЛЬКО предоставленный diff и предоставленный контекст документации/кода.
Не выдумывай баги и не требуй контекста, которого нет.
Если проблем нет — прямо напиши «существенных проблем не найдено».
Отвечай по-русски в Markdown. Не добавляй раздел «Источники»: его добавит система."""

REVIEW_INSTRUCTIONS = """Верни Markdown строго с разделами:
## Потенциальные баги
## Архитектурные проблемы
## Рекомендации
## Недостающие тесты

В каждом разделе — конкретные пункты с путями и строками diff, если это возможно.
Не повторяй diff целиком. Не добавляй вступление и раздел «Источники»."""


def load_diff(
    repo: Path,
    base: str = "main",
    head: str = "HEAD",
    diff_file: Path | None = None,
) -> tuple[str, list[str]]:
    """Читает diff из файла или из git; возвращает (текст, изменённые файлы)."""
    settings = get_settings()
    if diff_file is not None:
        path = diff_file if diff_file.is_absolute() else repo / diff_file
        text = read_diff_file(path, max_chars=settings.max_diff_chars)
        return text, diff_file_paths(text)
    text = git_diff(repo, base, head, max_chars=settings.max_diff_chars)
    return text, changed_files(repo, base, head)


def retrieval_query(diff_text: str, files: Sequence[str]) -> str:
    names = " ".join(Path(name).stem.replace("_", " ") for name in files)
    tail = "\n".join(diff_text.splitlines()[:120])
    return f"архитектура RAG MCP ревью {names}\n{tail}"


def collect_context(
    index: Index,
    diff_text: str,
    files: Sequence[str],
    top_k: int = 5,
) -> tuple[list[Chunk], list[Chunk]]:
    """top-K документации и top-K кода из изменённых файлов."""
    query = retrieval_query(diff_text, files)
    docs = list(index.search(query, k=top_k, kind="doc"))
    code_paths = [name for name in files if name.endswith(".py") and not name.startswith("tests/")]
    code: list[Chunk] = []
    if code_paths:
        code = list(index.search(query, k=top_k, kind="code", paths=code_paths))
    if not code:
        code = list(index.search(query, k=top_k, kind="code"))
    return docs, code


def build_review_prompt(diff_text: str, files: Sequence[str], docs: Sequence[Chunk], code: Sequence[Chunk]) -> str:
    file_lines = "\n".join(f"- {name}" for name in files) or "- (не определены)"
    prompt_diff = diff_text
    if len(prompt_diff) > 30_000:
        prompt_diff = prompt_diff[:30_000] + f"\n\n[diff обрезан для prompt: {len(diff_text)} символов]"
    return "\n\n".join(
        [
            REVIEW_INSTRUCTIONS,
            f"Изменённые файлы:\n{file_lines}",
            f"Diff:\n```diff\n{prompt_diff}\n```",
            f"Контекст документации:\n{build_context(docs)}",
            f"Контекст кода:\n{build_context(code)}",
        ]
    )


def _strip_sources(text: str) -> str:
    match = re.search(r"^##\s+Источники\s*$", text, flags=re.MULTILINE)
    if match:
        return text[: match.start()].rstrip()
    return text.rstrip()


def ensure_sections(markdown: str, docs: Sequence[Chunk], code: Sequence[Chunk]) -> str:
    """Гарантирует обязательные разделы и добавляет источники."""
    body = _strip_sources(markdown)
    for section in REVIEW_SECTIONS[:-1]:
        if section not in body:
            body += f"\n\n{section}\n\nСущественных проблем не найдено."
    sources: list[str] = []
    for item in [*source_list(docs), *source_list(code)]:
        if item not in sources:
            sources.append(item)
    source_lines = "\n".join(f"- {item}" for item in sources) or "- нет: RAG-контекст не найден"
    return f"{body}\n\n## Источники\n\n{source_lines}\n"


def review(
    repo: Path,
    base: str = "main",
    head: str = "HEAD",
    diff_file: Path | None = None,
    llm: LLM | None = None,
    index: Index | None = None,
    top_k: int = 5,
) -> str:
    """Возвращает Markdown-ревью по diff."""
    diff_text, files = load_diff(repo, base=base, head=head, diff_file=diff_file)
    if not diff_text.strip():
        empty = (
            "# Ревью изменений\n\n"
            f"Diff пуст для `{base}...{head}`.\n\n"
            "## Потенциальные баги\n\nСущественных проблем не найдено.\n\n"
            "## Архитектурные проблемы\n\nСущественных проблем не найдено.\n\n"
            "## Рекомендации\n\nНет изменений — ревью не требуется.\n\n"
            "## Недостающие тесты\n\nНет изменений — тесты не требуются.\n\n"
            "## Источники\n\n- нет: diff пуст\n"
        )
        return empty
    if index is None:
        index, _ = ensure_index(repo)
    docs, code = collect_context(index, diff_text, files, top_k=top_k)
    prompt = build_review_prompt(diff_text, files, docs, code)
    response = (llm or get_llm()).chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=1800,
    )
    title = "# Ревью изменений\n\n" + (f"Файлы: {', '.join(files)}" if files else "Файлы не определены")
    return f"{title}\n\n{ensure_sections(response, docs, code)}"


def write_review(markdown: str, output: Path) -> Path:
    output = output.expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    return output
