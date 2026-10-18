"""Общие фикстуры: временный репозиторий, fake LLM, настройки."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ai_assistant.config import Settings
from ai_assistant.index import Index

REVIEW_RESPONSE = """## Потенциальные баги

- `average()` делит на `len(values)` без проверки пустого списка.

## Архитектурные проблемы

- Утилиты аналитики смешаны с инфраструктурным кодом.

## Рекомендации

- Добавить guard-clauses и использовать `statistics.fmean`.

## Недостающие тесты

- Тест на пустой список и нулевой знаменатель.
"""


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", deepseek_api_key=None)


@pytest.fixture
def demo_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "ai_assistant").mkdir(parents=True)
    (repo / "demo").mkdir(parents=True)
    (repo / "README.md").write_text(
        "# Demo project\n\n"
        "## Назначение\n\n"
        "Demo project делает RAG по документации и отвечает с цитатами.\n\n"
        "## RAG\n\n"
        "RAG использует SQLite FTS5 и DeepSeek.\n",
        encoding="utf-8",
    )
    (repo / "docs" / "rag.md").write_text(
        "# RAG\n\n"
        "## Как устроен RAG\n\n"
        "Markdown режется на чанки, чанки попадают в SQLite FTS5, затем top-K "
        "передаётся в DeepSeek. Ответ содержит источники.\n\n"
        "## Ограничения\n\n"
        "Векторный поиск не используется.\n",
        encoding="utf-8",
    )
    (repo / "docs" / "faq.md").write_text(
        "# FAQ\n\n"
        "## Авторизация и SSO\n\n"
        "Для входа через SSO нужна роль admin. Роль viewer не имеет доступа к SSO. "
        "Если у пользователя viewer, администратор должен изменить роль.\n",
        encoding="utf-8",
    )
    (repo / "ai_assistant" / "sample.py").write_text(
        '"""Sample module."""\n\n\n'
        "def add(left: int, right: int) -> int:\n"
        '    """Сложить два числа."""\n'
        "    return left + right\n\n\n"
        "class Counter:\n"
        '    """Счётчик."""\n\n'
        "    def increment(self, value: int) -> int:\n"
        "        return value + 1\n",
        encoding="utf-8",
    )
    source_diff = Path(__file__).resolve().parents[1] / "demo" / "pr.diff"
    (repo / "demo" / "pr.diff").write_text(source_diff.read_text(encoding="utf-8"), encoding="utf-8")
    return repo


@pytest.fixture
def demo_index(demo_repo: Path, settings: Settings) -> Index:
    index = Index(demo_repo, index_path=settings.data_dir / "indexes" / "demo.sqlite", settings=settings)
    index.build()
    return index


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "gitrepo"
    repo.mkdir()

    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        return completed.stdout

    git("init", "-b", "main")
    git("config", "user.name", "Test User")
    git("config", "user.email", "test@example.com")
    (repo / "README.md").write_text("# Git repo\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-m", "initial")
    return repo
