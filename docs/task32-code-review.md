# Задание 32 — автоматизация ревью кода

## Цель

На pull request запускается pipeline, который получает diff, добавляет
RAG-контекст документации и кода и публикует Markdown-ревью с багами,
архитектурными проблемами и рекомендациями.

## Локальный запуск

По веткам:

```powershell
aiassist review `
  --repo C:\AiAssistant `
  --base main `
  --head demo/task32-bug `
  --output C:\DataProject\AiAssistant\review\review.md
```

Офлайн по готовому diff:

```powershell
aiassist review --repo C:\AiAssistant --diff-file demo\pr.diff --output review.md
```

Если `--output` не указан, Markdown печатается в stdout.

## Pipeline

1. `git diff --name-status base...head` — список изменённых файлов.
2. `git diff --no-color base...head` — diff, ограничение 100 000 символов.
3. RAG:
   - top-5 чанков документации;
   - top-5 чанков кода из изменённых `.py`-файлов; если их нет в индексе —
     top-5 по всему коду.
4. Prompt: «Ты ревьюер. Анализируй только diff и предоставленный контекст».
5. DeepSeek возвращает разделы:
   - `## Потенциальные баги`;
   - `## Архитектурные проблемы`;
   - `## Рекомендации`;
   - `## Недостающие тесты`.
6. `## Источники` добавляется кодом из найденных чанков; отсутствующие разделы
   заполняются фразой «Существенных проблем не найдено».
7. Результат сохраняется в `review.md`.

## GitHub Action

Файл `.github/workflows/ai-review.yml`:

- триггер `pull_request` (opened, synchronize, reopened);
- `actions/checkout@v4` с `fetch-depth: 0`;
- `actions/setup-python@v5` (Python 3.12);
- `pip install -e .`;
- `python -m ai_assistant review --repo . --base <base sha> --head <head sha> --output review.md`;
- публикация через `gh pr comment --body-file review.md`;
- permissions: `contents: read`, `pull-requests: write`;
- секрет `DEEPSEEK_API_KEY`, встроенный `GITHUB_TOKEN`/`GH_TOKEN`.

### Риск scope workflow

Если у GitHub-токена нет scope `workflow`, push файла
`.github/workflows/ai-review.yml` может быть отклонён. В этом случае добавьте
файл через веб-интерфейс GitHub (Add file → Create new file). Локальный
`aiassist review` продолжает работать без GitHub.

## Демонстрационный PR

Ветка `demo/task32-bug` добавляет `ai_assistant/analytics.py` с намеренными
ошибками:

- деление на `len(values)` без проверки пустого списка;
- деление на `total` без проверки нуля;
- `results[0]` без проверки пустого списка.

Ожидаемое ревью: все три пункта в «Потенциальные баги», рекомендация
использовать guard-clauses и `statistics.fmean`, тесты на пустой список и
нулевой знаменатель. Локальный `demo/pr.diff` содержит тот же патч для
офлайн-демонстрации.

## Ограничения

- LLM видит только diff и RAG-контекст; это не полноценный SAST.
- Очень большие diff обрезаются (100 000 символов при чтении, 30 000 — в
  prompt).
- Для запуска Action нужен секрет `DEEPSEEK_API_KEY` в настройках репозитория.
