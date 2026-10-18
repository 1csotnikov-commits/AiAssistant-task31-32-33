# MCP: серверы и клиент

## Что такое MCP в проекте

MCP (Model Context Protocol) используется для двух источников контекста:

- **project server** — git-ветка, HEAD, список файлов и diff;
- **CRM server** — тикеты и пользователи поддержки.

Транспорт — stdio (JSON-RPC). Используется официальный Python SDK `mcp` 2.x.
В версии 2.x класс `FastMCP` переименован в `MCPServer`, поэтому серверы
создаются так:

```python
from mcp.server.mcpserver import MCPServer

server = MCPServer(name="aiassistant-project", version="0.1.0")

@server.tool()
def git_branch() -> dict:
    ...
```

Запуск: `server.run("stdio")`.

## MCP project server

Команда:

```powershell
aiassist mcp project --repo C:\AiAssistant
```

Инструменты:

| Инструмент | Аргументы | Результат |
|---|---|---|
| `git_branch` | нет | `{"branch": "main", "head": "abc1234", "dirty": false}` |
| `list_files` | `glob="**/*"` | список путей внутри repo, максимум 500 |
| `git_diff` | `base`, `head="HEAD"` | unified diff `base...head`, ограничен 100 000 символов |

`git_branch` возвращает ветку, короткий HEAD и признак незакоммиченных
изменений (`git status --porcelain`). Реализация git — только
`subprocess.run(["git", "-C", repo, ...], shell=False)`. Запись и удаление
запрещены, ссылки валидируются.

## MCP CRM server

Команда:

```powershell
aiassist mcp crm --data C:\AiAssistant\demo
```

Инструменты:

| Инструмент | Аргументы | Результат |
|---|---|---|
| `get_ticket` | `ticket_id` | объект тикета или `null` |
| `get_user` | `user_id` | объект пользователя или `null` |
| `list_user_tickets` | `user_id` | список тикетов пользователя |

Данные читаются из `tickets.json` и `users.json` в каталоге `--data` (или из
единого `crm.json`/указанного файла). Формат:

```json
{
  "tickets": [
    {
      "id": "T-1001",
      "user_id": "U-001",
      "subject": "Не работает авторизация",
      "status": "open",
      "product": "AiAssistant",
      "messages": ["Пользователь не может войти после смены роли"]
    }
  ],
  "users": [
    {
      "id": "U-001",
      "name": "Тестовый пользователь",
      "role": "viewer",
      "plan": "basic"
    }
  ]
}
```

## MCP client

`ai_assistant/mcp_client.py`:

- формирует `StdioServerParameters` с `sys.executable -m ai_assistant mcp ...`;
- открывает `stdio_client` и `ClientSession`, вызывает `initialize()`;
- вызывает инструмент через `session.call_tool(name, arguments)`;
- разбирает `structured_content`, а при его отсутствии — JSON-текст;
- ограничивает вызов таймаутом `AIASSIST_MCP_TIMEOUT` (по умолчанию 30 с).

Высокоуровневые обёртки:

- `ProjectMCP(repo).git_branch()` → `GitBranch`;
- `ProjectMCP(repo).list_files(glob)`, `git_diff(base, head)`;
- `MCPCRMClient(data).get_ticket(id)`, `get_user(id)`,
  `list_user_tickets(id)`.

Строка для демонстрации:

```text
MCP: branch=main, head=abc1234, dirty=false
```

## Почему ветка берётся через MCP

По заданию 31 ассистент не вызывает `git branch` напрямую. Прямой вызов
остаётся только внутри MCP-сервера; клиент общается с ним по протоколу. Это
позволяет заменить источник контекста, не меняя RAG-логику.

## Диагностика

- `MCP: недоступен (...)` — проверьте, что пакет установлен
  (`pip install -e .`) и `python -m ai_assistant mcp project --repo ...`
  запускается вручную.
- `git не найден в PATH` — установите Git.
- Пустой `head` — в репозитории ещё нет коммитов.
- Таймаут — проверьте путь к repo и права на запуск subprocess.
