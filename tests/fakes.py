"""Тестовые дублёры без сетевых вызовов."""

from __future__ import annotations

from typing import Any


class FakeLLM:
    """Fake LLM, записывающий prompt и не делающий сетевых вызовов."""

    def __init__(self, response: str = "Ответ по документации.") -> None:
        self.response = response
        self.calls: list[list[dict[str, str]]] = []

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        self.calls.append(messages)
        return self.response

    @property
    def last_prompt(self) -> str:
        return "\n".join(message["content"] for message in self.calls[-1])
