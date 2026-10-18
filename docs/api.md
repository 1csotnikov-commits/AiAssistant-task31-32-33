# API сервиса поддержки

## Запуск

```powershell
aiassist support serve --host 127.0.0.1 --port 8000 --repo C:\AiAssistant --data C:\AiAssistant\demo
```

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI: `http://127.0.0.1:8000/openapi.json`

## GET /health

Проверка живости и состояния индекса.

```json
{
  "status": "ok",
  "service": "aiassistant-support",
  "version": "0.1.0",
  "repo": "C:\\AiAssistant",
  "data": "C:\\AiAssistant\\demo",
  "index": "C:\\DataProject\\AiAssistant\\indexes\\aiassistant.sqlite",
  "chunks": 142
}
```

Если индекса нет, сервис строит его при старте.

## POST /help

Тело запроса:

```json
{
  "ticket_id": "T-1001",
  "question": "Почему не работает авторизация?",
  "user_id": null
}
```

`user_id` необязателен: по умолчанию берётся `ticket.user_id`.

Успешный ответ:

```json
{
  "answer": "Краткий ответ...\n\nИсточники:\n- docs/faq.md → «Авторизация и SSO»",
  "sources": ["docs/faq.md → «Авторизация и SSO»"],
  "ticket": {
    "id": "T-1001",
    "user_id": "U-001",
    "subject": "Не работает авторизация",
    "status": "open",
    "product": "AiAssistant",
    "messages": ["Пользователь не может войти после смены роли"]
  },
  "user": {
    "id": "U-001",
    "name": "Тестовый пользователь",
    "role": "viewer",
    "plan": "basic"
  },
  "mcp": "MCP CRM: ticket=T-1001, user=U-001"
}
```

Ассистент должен связать роль `viewer` с FAQ-правилом «для SSO нужна роль
admin» и предложить проверить роль, а не выдумывать сбой сервера.

### Ошибки

| Код | Причина |
|---|---|
| 404 | тикет не найден |
| 422 | пустой вопрос |
| 503 | MCP CRM недоступен |

## Примеры

PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/help `
  -ContentType "application/json" `
  -Body '{"ticket_id":"T-1001","question":"Почему не работает авторизация?"}'
```

curl:

```bash
curl -X POST http://127.0.0.1:8000/help \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"T-1001","question":"Почему не работает авторизация?"}'
```

## Зависимости

Сервис использует тот же индекс и тот же MCP CRM-клиент, что и CLI. LLM
внедряется через `create_app(llm=...)`, CRM — через `create_app(crm=...)`, что
позволяет тестировать `/help` без сети и без subprocess.
