# AiAssistant — RAG + MCP ассистент (задания 31–33)

`AiAssistant` — самостоятельный MVP-проект с общим ядром **RAG** (SQLite FTS5 +
DeepSeek) и **MCP** (stdio), в котором реализованы три режима:

| Задание | Режим | Что показывает |
|---|---|---|
| 31 | Ассистент разработчика | RAG по README/docs, git-ветка через MCP, `/help` в чате |
| 32 | Автоматизация ревью кода | GitHub Action на PR, diff, RAG по docs и коду, Markdown-ревью |
| 33 | Ассистент поддержки | FastAPI-сервис, RAG по FAQ/docs, тикет и пользователь через MCP CRM |

Репозиторий: <https://github.com/1csotnikov-commits/AiAssistant-task31-32-33>.

## Назначение

Проект отвечает на вопросы по документации, получает git-контекст через
MCP-сервер и не выдумывает ответы, если в проиндексированных документах нет
нужных сведений. Ответы всегда содержат блок **Источники** с путями и
названиями разделов.

## Архитектура кратко

```text
README/docs + ai_assistant/**/*.py
        │
        ▼
  chunking (Markdown по заголовкам, Python по функциям/классам)
        │
        ▼
  SQLite FTS5  C:\DataProject\AiAssistant\indexes\<repo-slug>.sqlite
        │
        ▼
  top-K retrieval ──► prompt + DeepSeek ──► ответ с цитатами
        ▲
        │
  MCP client (stdio) ──► MCP project server (git_branch)
                    └──► MCP CRM server (ticket/user)
```

Подробнее: [docs/architecture.md](docs/architecture.md), [docs/rag.md](docs/rag.md),
[docs/mcp.md](docs/mcp.md).

## Требования

- Python **3.11+** (проверено на Python 3.14.7).
- Git в `PATH` для задачи 31 и 32.
- Ключ DeepSeek для живых ответов. Без ключа индекс, MCP и тесты работают,
  а `ask`, `review`, `support /help` возвращают понятную ошибку.
- Внешние embeddings, векторные БД и локальные модели **не используются**.

## Установка

```powershell
cd C:\AiAssistant
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Заполните `.env`:

```text
DEEPSEEK_API_KEY=ваш_ключ
DEEPSEEK_MODEL=deepseek-chat
AIASSIST_DATA_DIR=C:\DataProject\AiAssistant
```

`.env` в Git не попадает. Ключ читается только из окружения/`.env` и никогда
не выводится в логи.

Проверка установки:

```powershell
aiassist --version
aiassist --help
```

## Индексация

```powershell
aiassist index --repo C:\AiAssistant
```

Индексируются:

- `README.md`;
- `docs/**/*.md`, `docs/**/*.yaml`, `docs/**/*.yml`, `docs/**/*.json`;
- `ai_assistant/**/*.py` — для RAG по коду в задаче 32.

Индекс хранится в `C:\DataProject\AiAssistant\indexes\aiassistant.sqlite` и не
коммитится. Повторная индексация сравнивает SHA-256 файлов и обновляет только
изменённые; удалённые файлы удаляются из индекса. `--force` переиндексирует всё.

## Задание 31 — ассистент разработчика

```powershell
aiassist ask --repo C:\AiAssistant "Что делает проект?"
aiassist chat --repo C:\AiAssistant
```

Команды чата:

```text
/help Что делает проект?
/help Как устроен RAG?
/help Где находится MCP-клиент?
/branch
/files
/diff
/exit
```

`/help` выполняет три шага:


## Задание 32 — автоматизация ревью кода

Локальный запуск по веткам:

```powershell
aiassist review `
  --repo C:\AiAssistant `
  --base main `
  --head demo/task32-bug `
  --output C:\DataProject\AiAssistant\review\review.md
```

Офлайн-демо без веток (удобно для проверки на одном коммите):

```powershell
aiassist review --repo C:\AiAssistant --diff-file demo\pr.diff --output review.md
```

Логика:

1. diff берётся из `git diff base...head` или из `--diff-file`; размер ограничен
   100 000 символов (`AIASSIST_MAX_DIFF_CHARS`);
2. RAG ищет top-5 фрагментов документации и top-5 чанков кода из изменённых
   Python-файлов;
3. DeepSeek получает только diff и найденный контекст;
4. результат содержит разделы `## Потенциальные баги`,
   `## Архитектурные проблемы`, `## Рекомендации`, `## Недостающие тесты`,
   `## Источники`; отсутствующие разделы добавляются детерминированно;
5. если проблем нет, явно пишется «существенных проблем не найдено».

GitHub Action `.github/workflows/ai-review.yml` запускается на
`pull_request` (opened/synchronize/reopened), делает checkout с
`fetch-depth: 0`, устанавливает пакет, запускает `python -m ai_assistant review`
и публикует `review.md` комментарием через `gh pr comment`. Нужны
`permissions: contents: read, pull-requests: write` и секрет
`DEEPSEEK_API_KEY`; `GITHUB_TOKEN` встроенный.

Если GitHub отклонит push workflow-файла из-за отсутствия scope `workflow`,
добавьте файл через веб-интерфейс GitHub. Локальный `aiassist review` от этого
не зависит.

## Задание 33 — ассистент поддержки

```powershell
aiassist support serve --host 127.0.0.1 --port 8000 --repo C:\AiAssistant --data C:\AiAssistant\demo
```

Swagger: <http://127.0.0.1:8000/docs>.

Эндпоинты:

- `GET /health` — статус, версия, путь к индексу и число чанков;
- `POST /help` — ответ по FAQ/docs с контекстом тикета и пользователя.

Пример запроса:

```json
{
  "ticket_id": "T-1001",
  "question": "Почему не работает авторизация?"
}
```

Логика `/help`:

1. MCP CRM достаёт тикет `T-1001` и пользователя `U-001`;
2. RAG ищет top-5 фрагментов `docs/faq.md` и остальной документации;
3. в prompt передаются вопрос, статус, тема и сообщения тикета, роль и тариф
   пользователя, найденные фрагменты;
4. ответ содержит краткий ответ, что проверить, источники и MCP-строку.

Демо-тикет: пользователь с ролью `viewer` не может войти через SSO; FAQ
говорит, что для SSO нужна роль `admin`. Ассистент должен предложить проверить
роль, а не выдумывать сбой сервера.

## MCP-серверы

```powershell
# Сервер проекта: git_branch, list_files, git_diff
aiassist mcp project --repo C:\AiAssistant

# Сервер CRM: get_ticket, get_user, list_user_tickets
aiassist mcp crm --data C:\AiAssistant\demo
```

Серверы общаются по stdio (JSON-RPC) через официальный Python SDK `mcp` 2.x.
Клиент `ai_assistant/mcp_client.py` запускает сервер как subprocess, открывает
`stdio_client` + `ClientSession`, вызывает инструмент и разбирает
`structured_content` или JSON-текст.

## Данные

```text
C:\DataProject\AiAssistant\
├── indexes\   # SQLite FTS5, не коммитится
├── review\    # review.md, не коммитится
├── logs\      # локальные логи
└── data\      # при необходимости tickets.json/users.json
```

Синтетические демо-данные лежат в `demo/tickets.json` и `demo/users.json`.
Реальные персональные данные не используются.

## Тесты и проверки

```powershell
cd C:\AiAssistant
.\.venv\Scripts\Activate.ps1
python -m pytest -q
python -m ruff check ai_assistant tests
```

Тесты не делают сетевых вызовов: LLM заменяется fake-объектом, MCP-клиент —
mock/fake; git-тесты используют временный репозиторий.

1. MCP client запускает `aiassist mcp project --repo ...` и вызывает `git_branch`;
2. RAG достаёт top-5 фрагментов README/docs через FTS5;
3. DeepSeek получает вопрос, фрагменты, ветку и HEAD и возвращает ответ.

В конце ответа печатается строка:

```text
MCP: branch=main, head=abc1234, dirty=false
```

`/branch` вызывает MCP отдельно. `/files` и `/diff` тоже идут через MCP.

## Ограничения MVP

- нет embeddings и векторной БД: поиск лексический (FTS5 + substring fallback),
  поэтому синонимы без общих корней могут не находиться;
- нет веб-чата и аутентификации;
- CRM — синтетический JSON, не реальная система;
- DeepSeek обязателен для генерации ответа; офлайн работают только индекс,
  MCP-инструменты и тесты;
- GitHub Action требует `DEEPSEEK_API_KEY` в secrets репозитория;
- анализ ревью ограничен diff и найденным контекстом, это не заменяет
  полноценный SAST.

## Структура проекта

```text
C:\AiAssistant\
├── ai_assistant\
│   ├── cli.py              # Typer: index/ask/chat/review/support/mcp
│   ├── config.py           # .env, пути данных, лимиты
│   ├── models.py           # Pydantic-модели
│   ├── llm.py              # DeepSeek через openai SDK
│   ├── index.py            # chunking + SQLite FTS5
│   ├── rag.py              # контекст, prompt, цитаты
│   ├── git_tools.py        # безопасные git-команды
│   ├── mcp_project.py      # MCP project server
│   ├── mcp_crm.py          # MCP CRM server
│   ├── mcp_client.py       # stdio MCP client
│   ├── task31_cli.py       # ask/chat, /help
│   ├── task32_review.py    # review по diff
│   └── task33_support.py   # FastAPI /health, /help
├── docs\                   # документация = содержимое RAG
├── demo\                   # синтетические тикеты, пользователи, pr.diff
├── tests\
├── .github\workflows\ai-review.yml
└── pyproject.toml
```

## Демонстрация

Полный сценарий записи видео: [docs/demo.md](docs/demo.md).

Коротко:

```powershell
cd C:\AiAssistant
.\.venv\Scripts\Activate.ps1
aiassist --version
aiassist index --repo C:\AiAssistant
aiassist chat --repo C:\AiAssistant
# /help Что делает проект?
# /help Как устроен RAG?
# /branch
# /exit

aiassist review --repo C:\AiAssistant --base main --head demo/task32-bug --output C:\DataProject\AiAssistant\review\review.md

aiassist support serve --host 127.0.0.1 --port 8000
# POST /help: {"ticket_id": "T-1001", "question": "Почему не работает авторизация?"}
```

## Соответствие требованиям

| Требование задания | Команда/файл/тест | Доказательство |
|---|---|---|
| 31: RAG по README/docs с цитатами | `ai_assistant/rag.py`, `tests/test_rag.py` | `aiassist ask ...` → блок «Источники» |
| 31: `/help` отвечает о структуре проекта | `ai_assistant/task31_cli.py`, `tests/test_task31.py` | чат: `/help Где находится MCP-клиент?` |
| 31: MCP `git_branch` | `ai_assistant/mcp_project.py`, `tests/test_git_tools.py` | `aiassist mcp project --repo ...` → вызов `git_branch` |
| 31: ветка через MCP | `ai_assistant/mcp_client.py`, `tests/test_mcp_client.py` | строка `MCP: branch=main, head=..., dirty=false` |
| 32: diff и структурированное ревью | `ai_assistant/task32_review.py`, `tests/test_review.py` | `aiassist review --diff-file demo/pr.diff` → `review.md` |
| 32: GitHub Action на PR | `.github/workflows/ai-review.yml` | PR `demo/task32-bug` → Action → комментарий |
| 33: FastAPI `/health` и `/help` | `ai_assistant/task33_support.py`, `tests/test_support.py` | `POST /help` с `T-1001` |
| 33: контекст тикета/пользователя | `ai_assistant/mcp_crm.py`, `demo/*.json` | ответ учитывает роль `viewer` и FAQ про `admin` |
| Индекс FTS5, только изменённые файлы | `ai_assistant/index.py`, `tests/test_index.py` | повторный `aiassist index` → `обновлено: 0` |
| Нет секретов и данных клиентов в Git | `.gitignore`, `git ls-files` | нет `.env`, `*.sqlite`, `review/` |

## Лицензия

MIT, см. [LICENSE](LICENSE).

