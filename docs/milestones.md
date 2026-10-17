# Журнал этапов

## Этап 0 — каркас

Статус: завершён 2026-10-17.

Цель: воспроизводимый локальный запуск frontend, backend, worker, PostgreSQL и S3-эмулятора; миграционная основа, healthchecks, базовые дизайн-токены и CI-ready команды проверок.

Миграции: `20261017_0001` — расширения PostgreSQL `citext`, `btree_gist`, `pgcrypto`.

Проверено:

- backend: Ruff, strict mypy, 2 pytest;
- frontend: Biome, Vitest, production build, `npm audit` без уязвимостей;
- Compose: PostgreSQL healthy, миграция exit 0, API healthy, worker запущен, S3 running, web отвечает;
- `/health/live` и `/health/ready` возвращают успешный ответ;
- миграционные расширения присутствуют в PostgreSQL.

## Этап 1 — авторизация и роли

Статус: завершён 2026-10-17.

Реализованы bootstrap единственного преподавателя, создание ученика с ручным приглашением, активация, вход и выход, server-side sessions, абсолютный/idle TTL, CSRF, роли, блокировка с отзывом сессий, запросы и одноразовые ссылки восстановления пароля. Добавлены страницы входа, активации, восстановления, защищённые кабинеты и форма создания приглашения.

Миграции: `20261017_0002` — users, минимальные student profiles, sessions, invitation/reset tokens, reset requests, login attempts и audit log.

Проверено: 8 pytest, негативные role/CSRF сценарии, одноразовые токены, отзыв сессий, полный upgrade/downgrade PostgreSQL, production build frontend и сквозной API smoke flow.

