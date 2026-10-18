# Архитектура AiAssistant

## Что делает проект

`AiAssistant` — MVP-приложение с общим RAG/MCP-ядром и тремя режимами:

1. **Ассистент разработчика (задание 31).** Отвечает на вопросы по README и
   `docs/` с цитатами, получает текущую git-ветку через MCP и поддерживает
   интерактивные команды `/help`, `/branch`, `/files`, `/diff`.
2. **Автоматизация ревью кода (задание 32).** По diff из pull request или
   файла формирует Markdown-ревью с потенциальными багами, архитектурными
   проблемами, рекомендациями и недостающими тестами.
3. **Ассистент поддержки (задание 33).** FastAPI-сервис отвечает пользователю
   по FAQ/документации с учётом тикета и роли пользователя, полученных через
   MCP CRM.

Проект не использует embeddings, векторные БД и локальные модели. Поиск
лексический: SQLite FTS5 с fallback на подстроку. Генерация ответа — DeepSeek
через OpenAI-совместимый SDK.

## Компоненты

| Компонент | Файл | Ответственность |
|---|---|---|
| CLI | `ai_assistant/cli.py` | команды `index`, `ask`, `chat`, `review`, `support serve`, `mcp` |
| Конфигурация | `ai_assistant/config.py` | `.env`, пути `C:\DataProject\AiAssistant`, лимиты |
| Модели | `ai_assistant/models.py` | чанки, git-ветка, тикеты, пользователи, запросы/ответы |
| Индексация | `ai_assistant/index.py` | чанкинг, SHA-256, SQLite FTS5, retrieval |
| RAG | `ai_assistant/rag.py` | контекст, prompt, источники, запрет выдумывания |
| LLM | `ai_assistant/llm.py` | DeepSeek chat.completions |
| Git | `ai_assistant/git_tools.py` | `subprocess.run([...], shell=False)` |
| MCP project server | `ai_assistant/mcp_project.py` | `git_branch`, `list_files`, `git_diff` |
| MCP CRM server | `ai_assistant/mcp_crm.py` | `get_ticket`, `get_user`, `list_user_tickets` |
| MCP client | `ai_assistant/mcp_client.py` | stdio-сессия, вызов инструментов, разбор результата |
| Задача 31 | `ai_assistant/task31_cli.py` | `ask`, чат, `/help` |
| Задача 32 | `ai_assistant/task32_review.py` | diff, контекст docs/code, review.md |
| Задача 33 | `ai_assistant/task33_support.py` | FastAPI `/health`, `/help` |

**MCP-клиент находится в `ai_assistant/mcp_client.py`.** Основные классы:
`ProjectMCP` (метод `git_branch()`), `MCPCRMClient` (`get_ticket()`,
`get_user()`), функция `call_mcp_tool()` и строка `format_mcp_line()`.

## Поток данных

```text
Пользователь
   │  aiassist ask/chat
   ▼
task31_cli.ask_question
   ├── ensure_index(repo) ──► index.build() ──► SQLite FTS5
   ├── ProjectMCP.git_branch() ──► stdio ──► mcp_project server ──► git
   ├── index.search(question, k=5, kind="doc")
   └── rag.answer_question ──► DeepSeek ──► ответ + «Источники» + MCP-строка
```

Для задачи 32 вместо вопроса используется запрос, собранный из имён изменённых
файлов и начала diff; отдельно достаются 5 чанков документации и 5 чанков кода.
Для задачи 33 вопрос дополняется темой, продуктом и сообщениями тикета.

## Хранение

| Данные | Путь | В Git |
|---|---|---|
| Индексы | `C:\DataProject\AiAssistant\indexes\<repo-slug>.sqlite` | нет |
| Ревью | `C:\DataProject\AiAssistant\review\` | нет |
| Логи | `C:\DataProject\AiAssistant\logs\` | нет |
| Синтетические демо-данные | `demo/tickets.json`, `demo/users.json` | да |
| Секреты | `.env` | нет |

Индекс содержит таблицы `files` (путь, SHA-256, время), `chunks` (id, path,
title, kind, start_line, end_line, text) и виртуальную таблицу `chunks_fts`.

## Обработка ошибок

- Нет `DEEPSEEK_API_KEY` → `LLMError` с инструкцией, CLI завершается с кодом 1.
- MCP-сервер не отвечает → `MCPClientError`; в чате печатается
  `MCP: недоступен (...)`, чат продолжает работу.
- Нет релевантных чанков → LLM не вызывается, ответ «В документации этого нет».
- Тикет не найден → HTTP 404; CRM/MCP недоступен → HTTP 503.
- Пустой diff → структурированное ревью с явной пометкой, что изменений нет.

## Безопасность

- Git вызывается только списком аргументов, без `shell=True`; ссылки
  валидируются, запись и удаление запрещены.
- MCP-серверы предоставляют только чтение.
- `DEEPSEEK_API_KEY` не логируется и не коммитится.
- В репозитории только синтетические тикеты и пользователи.
