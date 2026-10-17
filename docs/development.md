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

