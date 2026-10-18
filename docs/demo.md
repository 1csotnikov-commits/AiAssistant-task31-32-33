# Демонстрация для видео

Все команды воспроизводимы на Windows/PowerShell. Перед записью создайте
`.env` с `DEEPSEEK_API_KEY` (файл не коммитится).

## Подготовка

```powershell
cd C:\AiAssistant
.\.venv\Scripts\Activate.ps1
aiassist --version
aiassist index --repo C:\AiAssistant
```

Ожидаемо: версия `0.1.0`, строка с путём индекса и количеством чанков.

## Задание 31

```powershell
aiassist chat --repo C:\AiAssistant
```

В чате:

```text
/help Что делает проект?
/help Как устроен RAG?
/help Где находится MCP-клиент?
/branch
/exit
```

Показать:

- ответ по README/docs;
- блок «Источники» с путями и разделами;
- строку `MCP: branch=main, head=..., dirty=...`.

Дополнительно:

```powershell
aiassist ask --repo C:\AiAssistant "Что делает проект?"
```

## Задание 32

На GitHub показать PR из `demo/task32-bug` в `main`: запуск Action и комментарий
с ревью. Локальный fallback:

```powershell
aiassist review `
  --repo C:\AiAssistant `
  --base main `
  --head demo/task32-bug `
  --output C:\DataProject\AiAssistant\review\review.md
```

Если ветки ещё нет:

```powershell
aiassist review --repo C:\AiAssistant --diff-file demo\pr.diff --output review.md
```

Показать разделы:

- потенциальные баги: деление на ноль и пустой список;
- архитектурные проблемы;
- рекомендации;
- недостающие тесты;
- источники.

## Задание 33

```powershell
aiassist support serve --host 127.0.0.1 --port 8000 --repo C:\AiAssistant --data C:\AiAssistant\demo
```

В браузере открыть `http://127.0.0.1:8000/docs`, вызвать `POST /help`:

```json
{
  "ticket_id": "T-1001",
  "question": "Почему не работает авторизация?"
}
```

Показать, что ответ:

- учитывает роль `viewer` и тариф `basic`;
- говорит, что для SSO нужна роль `admin` (и тариф `enterprise`);
- предлагает проверить роль, а не выдумывает сбой сервера;
- содержит источник `docs/faq.md → «Авторизация и SSO»`;
- содержит `"mcp": "MCP CRM: ticket=T-1001, user=U-001"`.

Проверка health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Проверки перед публикацией

```powershell
python -m pytest -q
python -m ruff check ai_assistant tests
git status
git ls-files
```

В `git ls-files` не должно быть `.env`, `*.sqlite`, `review/`, `logs/`.
