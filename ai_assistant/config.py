"""Настройки приложения: пути к данным, DeepSeek, лимиты."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


def default_data_dir() -> Path:
    """Каталог пользовательских данных (индексы, ревью, логи)."""
    env_value = os.getenv("AIASSIST_DATA_DIR")
    if env_value:
        return Path(env_value).expanduser()
    if os.name == "nt":
        return Path(r"C:\DataProject\AiAssistant")
    return Path.home() / ".aiassistant"


def repo_slug(repo: Path) -> str:
    """Безопасное имя индекса для репозитория."""
    resolved = repo.resolve()
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", resolved.name).strip("-._").lower()
    return slug or "repo"


class Settings(BaseModel):
    """Настройки, собранные из окружения и `.env`."""

    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    data_dir: Path = Field(default_factory=default_data_dir)
    top_k: int = 5
    review_top_k: int = 5
    max_diff_chars: int = 100_000
    llm_timeout_seconds: float = 120.0
    mcp_timeout_seconds: float = 30.0

    @property
    def indexes_dir(self) -> Path:
        return self.data_dir / "indexes"

    @property
    def review_dir(self) -> Path:
        return self.data_dir / "review"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    def index_path(self, repo: Path) -> Path:
        return self.indexes_dir / f"{repo_slug(repo)}.sqlite"

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.indexes_dir, self.review_dir, self.logs_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Читает `.env` (если есть) и переменные окружения."""
    load_dotenv(override=False)
    return Settings(
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY") or None,
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        data_dir=default_data_dir(),
        top_k=int(os.getenv("AIASSIST_TOP_K", "5")),
        max_diff_chars=int(os.getenv("AIASSIST_MAX_DIFF_CHARS", "100000")),
    )
