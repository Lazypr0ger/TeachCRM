# Разработка

## Локальный backend

```bash
cd backend
uv sync --frozen
uv run pytest
uv run ruff check .
uv run mypy app
uv run uvicorn app.main:app --reload
```

Worker достраивает активные серии уроков на 12 недель вперёд, удаляет истёкшие
временные загрузки из приватного S3-хранилища, доставляет внутренние уведомления
из outbox и создаёт дедуплицированные напоминания о просроченных начислениях:

```bash
cd backend
uv run python -m app.workers.main
```

Для локального S3 используется LocalStack. Compose создаёт приватный bucket
`tutorcrm-private` скриптом `infra/localstack/init-s3.sh`. Разрешены PDF, PNG,
JPEG, WebP и DOCX до 15 МБ; на один объект можно прикрепить до 10 файлов.

В локальной среде пароль преподавателя создаётся интерактивно:

```bash
uv run python -m app.cli bootstrap-teacher --login teacher
```

## Локальный frontend

```bash
cd frontend
npm ci
npm run lint
npm test
npm run build
npm run dev
```

## Миграции

При запущенном PostgreSQL:

```bash
cd backend
uv run alembic upgrade head
```

Новые миграции проверяются на чистой базе и на обновлении предыдущей версии. Интеграционные тесты бизнес-ограничений выполняются на PostgreSQL.

