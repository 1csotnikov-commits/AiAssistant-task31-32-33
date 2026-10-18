"""DeepSeek через OpenAI-совместимый SDK. Ключ никогда не логируется."""

from __future__ import annotations

from typing import Protocol

from openai import OpenAI

from ai_assistant.config import Settings, get_settings


class LLMError(RuntimeError):
    """Ошибка LLM или отсутствие ключа."""


class LLM(Protocol):
    def chat(self, messages: list[dict[str, str]], **kwargs: object) -> str: ...


class DeepSeekLLM:
    """Минимальный клиент chat.completions для DeepSeek."""

    def __init__(self, settings: Settings | None = None, client: OpenAI | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client

    def _get_client(self) -> OpenAI:
        if self._client is not None:
            return self._client
        if not self.settings.deepseek_api_key:
            raise LLMError(
                "DEEPSEEK_API_KEY не задан. Скопируйте .env.example в .env и укажите ключ "
                "или задайте переменную окружения DEEPSEEK_API_KEY."
            )
        self._client = OpenAI(
            api_key=self.settings.deepseek_api_key,
            base_url=self.settings.deepseek_base_url,
            timeout=self.settings.llm_timeout_seconds,
        )
        return self._client

    def chat(self, messages: list[dict[str, str]], **kwargs: object) -> str:
        client = self._get_client()
        temperature = float(kwargs.get("temperature", 0.2))
        max_tokens = int(kwargs.get("max_tokens", 1400))
        try:
            response = client.chat.completions.create(
                model=self.settings.deepseek_model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - наружу отдаём единый LLMError
            raise LLMError(f"Ошибка вызова DeepSeek: {exc}") from exc
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise LLMError("DeepSeek вернул пустой ответ.")
        return content.strip()


def get_llm(settings: Settings | None = None) -> DeepSeekLLM:
    return DeepSeekLLM(settings=settings)
