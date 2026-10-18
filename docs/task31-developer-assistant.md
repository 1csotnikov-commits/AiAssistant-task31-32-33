# Задание 31 — ассистент разработчика

## Цель

Ответить на вопросы по проекту через RAG и показать git-контекст, полученный
через MCP. Минимальный результат: `/help` отвечает о структуре проекта,
`/branch` получает ветку через MCP, ответы содержат цитаты.

## Команды

```powershell
aiassist index --repo C:\AiAssistant

aiassist ask --repo C:\AiAssistant "Что делает проект?"

aiassist chat --repo C:\AiAssistant
```

В чате:

```text
/help Что делает проект?
/help Как устроен RAG?
/help Где находится MCP-клиент?
/branch
/files
/diff
/exit
```

## Как работает /help

1. `ProjectMCP(repo).git_branch()` запускает `ai_assist mcp project` как
   subprocess, открывает stdio-сессию и вызывает инструмент `git_branch`.
2. `Index.search(question, k=5, kind="doc")` достаёт пять фрагментов README и
   docs через FTS5; при необходимости срабатывает substring fallback.
3. `rag.answer_question()` формирует prompt с вопросом, фрагментами, веткой,
   HEAD и признаком dirty.
4. DeepSeek возвращает ответ по-русски.
5. К ответу добавляются «Источники» и строка
   `MCP: branch=main, head=..., dirty=false`.

Если MCP недоступен, чат не падает: печатается `MCP: недоступен (...)`.
Если в индексе нет фрагментов, ассистент отвечает «В документации этого нет».

## Демо-вопросы и ожидаемые ответы

- **Что делает проект?** — AiAssistant объединяет RAG по README/docs и MCP;
  реализует ассистента разработчика, ревью PR и поддержку пользователей.
- **Как устроен RAG?** — Markdown/Python → чанки → SQLite FTS5 → top-K →
  DeepSeek → ответ с цитатами.
- **Где находится MCP-клиент?** — `ai_assistant/mcp_client.py`, классы
  `ProjectMCP`, `MCPCRMClient`, функция `call_mcp_tool()`.

## Ограничения

- Ответ зависит от качества индекса; после изменения docs нужен
  `aiassist index`.
- Без `DEEPSEEK_API_KEY` `ask` и `/help` завершаются понятной ошибкой.
- `/diff` показывает `HEAD~1..HEAD` и требует минимум двух коммитов.
