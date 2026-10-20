# Аудит Tutor CRM v1.0 перед редизайном

Дата аудита: 20 октября 2026 года. Ветка работ: `devRem`, создана от
`dev` на коммите `4bb2daf`.

## Основание и границы работ

Аудит выполнен по всему пакету `Tutor_CRM_Codex_Implementation_Pack.zip`.
Контрольные суммы всех 22 файлов совпали с `MANIFEST_SHA256.txt`.
Приоритет источников принят в следующем порядке:

1. `IMPLEMENTATION_SPEC.md`;
2. `SCREEN_MAP.md` и 14 PNG из `references/`;
3. `HOMEWORK_UPLOAD_FIX.md` и `QA_ACCEPTANCE.md`;
4. историческое ТЗ v1 и предыдущее ТЗ редизайна;
5. фактический код и тесты как источник текущего состояния.

Макеты используются как композиционный контракт. Фиктивные имена, суммы,
проценты, чат, оценивание ДЗ, тариф CRM, отдельное файловое хранилище и другие
неподтверждённые возможности из изображений не переносятся.

## Подтверждённое исходное состояние

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, отдельный
  worker и приватное S3-совместимое хранилище.
- Frontend: Next.js 16 App Router, React 19, TypeScript 6, Tailwind 4 используется
  только как CSS pipeline; интерфейс в основном написан общим CSS.
- Инфраструктура: Docker Compose, PostgreSQL 17.6, LocalStack S3.
- Данные: 16 миграций; схема покрывает пользователей, сессии, уроки,
  расписание, повторения, переносы, файлы, ДЗ, биллинг, уведомления, пробные
  заявки и публичные настройки.
- Маршруты: 22 Next.js route, включая public/auth, шесть student и девять
  teacher страниц, а также API proxy.
- Baseline-проверки до изменений прошли: Ruff, strict mypy, весь pytest,
  Biome, Vitest и production build Next.js (22 маршрута).
- Отдельного browser E2E и набора визуальных скриншот-тестов в репозитории нет.
  Frontend покрыт только тремя unit-тестами утилит календаря и темы.

## Архитектурное решение

Основной backend остаётся на FastAPI. Перенос на Java не выполняется в рамках
редизайна по следующим проверяемым причинам:

- действующий backend уже реализует серверные сессии, CSRF, RBAC/ownership,
  аудит, транзакции, outbox и 16 совместимых миграций;
- вся бизнес-логика расписания, финансов и приватных файлов имеет тесты;
- переписывание создаст второй источник истины и высокий риск потери данных,
  IDOR-регрессий и расхождения финансовых расчётов;
- актуальное ТЗ требует сохранять разумный стек, если нет документированной
  существенной причины миграции.

Развитие продолжается как модульный монолит. Новые backend-возможности
добавляются в существующие доменные модули, API остаётся обратно совместимым.
Java можно рассматривать отдельно после v1 только при измеримой причине:
нагрузке, недоступной интеграции или эксплуатационном ограничении.

## Матрица требований и разрывов

| Модуль / экран | Реализовано в v1? | API/состояние | Недостатки относительно PNG | План изменений | Риск регрессии | Тест |
|---|---|---|---|---|---|---|
| Dashboard преподавателя | Частично | `GET /api/v1/teacher/dashboard` возвращает только `today_lessons`; claims, notifications и trials собираются отдельными запросами | Нет AppShell, четырёх KPI, карточки ближайшего урока; форма приглашения постоянно занимает экран; присутствуют навигационные кнопки вместо sidebar | Расширить агрегат реальными счётчиками, перенести приглашение в dialog/drawer, собрать структуру 8/4 и последние три уведомления | Средний: агрегации и SSR | API-тест счётчиков, component/E2E dashboard, скриншоты desktop/mobile |
| Расписание день/неделя/месяц | Частично | Список уроков по диапазону дат; `WeekCalendar` группирует события только по дням | Есть только недельный список без часовых координат; нет day/month, proportional duration и detail drawer | Ввести общий календарный workspace, hour grid, day/week/month и drawer на реальных lesson данных | Высокий: время, overlap, responsive | Unit координат 60/80 минут, API range, keyboard и visual E2E |
| Выбор нескольких интервалов | Нет | Сервер умеет создавать отдельные lesson/block, batch-контракта нет | Нет selectable cells, контекстной панели и touch режима | Клиентский набор интервалов с последовательной/пакетной безопасной отправкой; сервер повторно проверяет каждый интервал | Высокий: частичный batch и конфликты | Интеграционный rollback/409, UI mouse/keyboard/touch |
| Создание и редактирование урока | Да, базово | `POST/PATCH /api/v1/teacher/lessons`, optimistic `version`, complete/cancel | Большая форма постоянно открыта на расписании; нет right drawer и отдельной карточки занятия | Перенести create/edit в drawer, добавить `/teacher/lessons` и `/teacher/lessons/[id]`, сохранить DTO | Средний | CRUD, stale version, conflict, UI smoke |
| Блокировки и типы | Частично | `availability_rules`, `availability_exceptions` с `BLOCKED`/`AVAILABLE_OVERRIDE` и private reason | Нет встроенных «Выходной»/«Болезнь», пользовательских типов и цветов; нет управления из календарной панели | Добавить справочник типов совместимой миграцией и привязку exception; student DTO не раскрывает блокировки | Высокий: миграция и приватность | Migration upgrade/downgrade, role/IDOR, calendar E2E |
| Запросы переноса | Частично | Разовый request/counter/accept/reject/cancel, серверная проверка конфликта | Нет типа разовый/постоянный, preview до/после и отдельного подтверждения после preview | Добавить read-only preview endpoint и scope для будущих экземпляров серии; принять атомарно с повторной проверкой | Высокий: recurrence и транзакции | Preview не меняет БД, permanent scope, concurrent 409 |
| Ученики/профиль | Частично | Пагинированный поиск/класс/статус/сортировка, detail/update, billing, privacy | Список карточками вместо таблицы; нет KPI/фильтра оплаты/следующего урока/долга; detail без вкладок и drawer | Расширить list DTO вычисляемыми полями, DataGrid/mobile cards, общий invite dialog, detail tabs; прогресс — «В разработке» | Средний | Pagination/filter API, invite, a11y таблицы/drawer |
| Занятия/материалы | Частично | Lesson CRUD/list и приватные file endpoints; материалы встроены в lesson cards | Нет teacher route «Занятия», плотной таблицы, detail tabs и отдельной страницы урока | Добавить страницы списка/detail на существующих API; вынести материалы в `ProtectedFileItem` | Средний | Role routes, lesson/file smoke, visual 08–09 |
| Отправка домашнего задания + файлы | Реализовано на API, заявлен P0-дефект UI/окружения | ticket: init → multipart content → complete; submission связывает draft files транзакционно, idempotency key | UI загружает по одному файлу сразу после выбора, без очереди, multiple/progress/retry; тесты используют MemoryStorage и обходят Next proxy/LocalStack; реальное S3 E2E отсутствует | Сначала воспроизвести через browser proxy и LocalStack; исправить root cause; единая очередь 1–10 файлов, отправка по явной кнопке, сохранение текста при ошибке, teacher download | Критический: потеря ответа/ACL | PNG+PDF+text byte equality, only-file/text, reload/restart, чужой student, 413/type, double click, proxy/S3 E2E |
| Финансы/экспорт | Основная логика есть, экспорт/графики отсутствуют | Profiles, invoices, max discount, monthly/per lesson, claims, confirm/reject, partial allocations, reversals, summary | Нет period/student filters, четвёртого KPI в UI, диаграмм, detail drawer и XLSX | Добавить фильтрованные агрегаты, реальные SVG charts, защищённый XLSX endpoint и drawer заявки; money logic не менять | Высокий: суммы и privacy | Decimal/discount/idempotency regression, XLSX types/formula injection/ownership |
| Уведомления | Да, базово | Пагинация, date/type/read filters, mark read/all, outbox | Нет KPI, поиска, группировки по датам и detail drawer; карточки слишком крупные | Плотные строки, real counters, фильтры, details panel, target navigation только по разрешённым маршрутам | Средний: safe target links | Ownership/read tests, filter UI, visual 13 |
| Настройки | Частично | Редактируются site settings и timezone; тема хранится локально; system diagnostics отдельно | Экран называется «Публичный сайт»; нет единой страницы профиля/timezone/theme; форма длинная; notification switches не подтверждены delivery | Одна прокручиваемая Settings page из реальных секций, accordion публичного контента, timezone и theme; недоступные каналы не показывать активными | Средний | Save/error/dirty state, timezone, role test, visual 14 |
| ЛК ученика | Функционально реализован | Dashboard, schedule, lessons, billing, notifications, profile | Нет desktop shell, next-lesson hero и спокойной иерархии; формы/карточки не соответствуют новой системе | Пересобрать поверх общих primitives после teacher core; сохранить только собственные данные | Высокий: ownership при UI refactor | Полный student E2E, 320/390 px, чужие ID |
| Публичный сайт | Частично | Config-driven site, trials feature flag и защищённая guest форма | Узкий текстовый hero, мало композиции, настройки не сгруппированы | Графитовый educational landing без hardcode личности, корректный disabled state | Низкий/средний | Feature flag, authenticated student 403, responsive visual |
| RBAC/IDOR/сессии | Да и покрыто backend-тестами | HttpOnly session, CSRF, role dependencies, ownership выборки, reset/invite/suspend | Нет browser E2E прямых route/API атак; upload E2E не проходит через proxy/storage | Сохранить зависимости; добавить сквозную security matrix и проверку download после re-login/restart | Критический | Student→teacher 403, foreign object 404, CSRF/session expiry, private file ACL |

## Аудит P0-цепочки файлов

Фактический контракт состоит из трёх запросов:

1. `POST /api/v1/files/upload-init` создаёт ticket и проверяет роль, ownership,
   размер и количество файлов.
2. `POST /api/v1/files/upload-tickets/{ticket}/content` получает browser
   `FormData`, сверяет реальный размер, magic bytes и пишет temporary object.
3. `POST /api/v1/files/upload-complete/{ticket}` копирует object в постоянный
   private key, создаёт `files` + `file_links` и удаляет temporary object.
4. `POST /api/v1/student/assignments/{id}/submission` в одной DB-транзакции
   создаёт единственный submission и переводит ссылки файлов с assignment на
   submission. Состояние `ACCEPTED` вычисляется только по наличию submission.

Серверная модель в целом соответствует v1, но текущие тесты подменяют S3
in-memory реализацией и вызывают FastAPI напрямую. Они не проверяют:

- Next.js proxy с multipart boundary и cookies;
- реально созданный bucket LocalStack;
- сохранение объектов после перезапуска контейнеров;
- выбор нескольких файлов в UI;
- состояние очереди, частичный upload, retry и понятные ошибки.

В предыдущем локальном запуске зафиксирована ошибка LocalStack init script:
`No such file or directory ... init-s3.sh`. Для Windows уже добавлено правило
LF в `.gitattributes`, однако это ещё не является доказательством исправного
сквозного обмена. Root cause P0 считается установленной только после
воспроизведения через frontend proxy, проверки bucket/object/DB и скачивания
байтов преподавателем.

Текущая совместимая политика файлов сохраняется: PDF, PNG, JPEG, WebP и DOCX,
до 15 MiB на файл и до 10 файлов на target. DOC/SVG не разрешаются. Изменение
лимитов или расширение типов не требуется для v1 и может быть сделано отдельно
после эксплуатационных замеров.

## Архитектура целевого frontend

```text
frontend/src/
  app/
    (существующие маршруты сохраняются)
    teacher/lessons/[id]/
  components/
    ui/             Button, Card, Badge, Field, Dialog, Drawer, Toast, Skeleton
    layout/         AppShell, Sidebar, Topbar, MobileNav, PageHeader
    data/           DataTable, FilterBar, EmptyState, StatCard
    calendar/       CalendarToolbar, DayGrid, WeekGrid, MonthGrid, SelectionPanel
    files/          FilePicker, UploadQueue, ProtectedFileItem
    homework/       HomeworkSummary, SubmissionForm, SubmissionView
    ...доменные компоненты
  lib/
    api/            единая обработка ошибок и auth-запросов
    design/         theme/sidebar persistence
    ...существующие типы доменов
```

CSS variables остаются источником design tokens. Tailwind уже установлен, но
ввод второй UI-библиотеки сейчас не нужен: это увеличит bundle и заставит
переписать доступные работающие компоненты. Иконки допускается добавить одной
небольшой зависимостью (Lucide), когда будет собран AppShell.

## Этапы реализации и зависимости

### Этап 0. Аудит и контрольная точка

Файлы: этот документ. Результат: подтверждённый scope, карта API/routes,
baseline тестов, архитектурное решение и последовательность работ.

### Этап 1. P0 — файловый обмен домашнего задания

Зависит от работающих PostgreSQL и LocalStack. Изменяем только
`frontend/src/components/homework/*`, `frontend/src/lib/files.ts`, при
подтверждённой необходимости API proxy/files service, соответствующие backend
и frontend тесты. Добавляем `docs/HOMEWORK_UPLOAD_FIX_REPORT_RU.md`.

Definition of Done: student отправляет PNG+PDF+text через browser-facing API,
teacher видит metadata и скачивает идентичные байты после reload/re-login;
другой student получает отказ; invalid/oversize не создаёт submission;
повторный submit не дублируется.

### Этап 2. Design foundation и AppShell

Семантические токены, typography/spacing, shared primitives, desktop sidebar
с persisted collapse, topbar и mobile navigation. Существующие маршруты остаются
доступны. На этом этапе меняется оболочка, а не бизнес-логика страниц.

### Этап 3. Dashboard и ученики

Новый teacher dashboard по PNG 01 без быстрых действий/матрицы, затем students
DataGrid, общий invite dialog и профиль с вкладками. Требуемые реальные
агрегации добавляются в совместимые DTO.

### Этап 4. Занятия и ДЗ

Teacher lessons list/detail по PNG 08–10, materials/homework reading mode,
редактирование в drawer. Student lesson workflow получает новый upload queue.

### Этап 5. Расписание

Day/week/month, часовые координаты, detail drawer, keyboard/touch selection,
batch actions, typed blocks, затем reschedule preview и permanent scope.
Миграции делаются отдельными обратимыми коммитами перед UI.

### Этап 6. Финансы

Фильтры, четыре KPI, реальные диаграммы, очередь claims и detail drawer,
backend XLSX export с numeric/date cells и защитой от formula injection.
Текущие discount/payment правила остаются неизменными.

### Этап 7. Уведомления, настройки, student и public polish

Плотная лента и details panel, единая settings page, затем общий design system
для student кабинета, auth и публичного сайта. Неподтверждённые каналы/функции
не имитируются.

### Этап 8. Полный release gate

Backend unit/integration/security, frontend unit/component, browser E2E,
визуальные скриншоты 1920×1080, 1440×900, 1024×768, 768×1024, 390×844 и
320×568, keyboard/a11y, migrations, build, Docker smoke и чистое git-дерево.

## Решения, не требующие дополнительного согласования

- v2-функции не добавляются; три статуса ДЗ сохраняются.
- CRM не принимает деньги, а только учитывает начисления и ручные
  подтверждения.
- Часовой пояс интерфейса и расписания — `Europe/Moscow`.
- Приглашения передаёт преподаватель вручную.
- Персональные данные v1 ограничены ФИО и классом.
- XLSX считается новым явно утверждённым требованием текущего ТЗ, несмотря на
  историческую пометку v2.
- Backend остаётся на FastAPI; миграция на Java вынесена за scope v1.

## Главные риски

1. P0 upload нельзя закрыть только unit-тестом: требуется реальный S3 и proxy.
2. Календарь и permanent reschedule потребуют совместимых изменений схемы и
   максимального набора conflict/concurrency тестов.
3. Финансовые графики и XLSX обязаны строиться из тех же серверных агрегатов,
   иначе появится двойная семантика сумм.
4. Большой визуальный рефактор нужно вести маршрут за маршрутом, сохраняя
   доступность старого действия до готовности нового.
5. Точные pixel-level сравнения доступны только для 14 teacher PNG; student и
   public проверяются на соответствие общей design system без заявления о
   pixel-perfect.
