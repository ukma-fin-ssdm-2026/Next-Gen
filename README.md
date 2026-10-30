# Baraholka NaUKMA

[![CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/workflows/ci.yml/badge.svg)](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/workflows/ci.yml)
[![Deploy API docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/workflows/docs.yml/badge.svg)](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/workflows/docs.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.142-009688?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.1-D71F00?logo=sqlalchemy&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-7-3178C6?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-8-646CFF?logo=vite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

Студентський маркетплейс оголошень НаУКМА. Командний проєкт з курсу SSDM 2026.

- **Розгорнута версія:** <https://baraholka-naukma.duckdns.org>
- **Документація API (Swagger UI):** <https://ukma-fin-ssdm-2026.github.io/Next-Gen/docs/api/>

## Про проєкт

Baraholka NaUKMA — вебзастосунок для обміну речами в межах університетської спільноти. Платежів і доставки всередині сервісу немає: контакт продавця доступний авторизованим користувачам, домовленості відбуваються напряму. Вхід виконується лише через корпоративний обліковий запис Microsoft `@ukma.edu.ua`.

### Функціональність

| Роль | Можливості |
|---|---|
| Відвідувач | Перегляд каталогу, пошук за ключовими словами, фільтрація за категорією та ціною (до 100 000 000 грн), сортування за датою і ціною |
| Користувач | Створення, редагування й зняття оголошень із фото; обране; перегляд контактів продавців; профіль (ім'я, аватарка, контакти за замовчуванням); пропозиції категорій; скарги на оголошення; звернення до адміністрації |
| Адміністратор | Зняття оголошень; блокування й розблокування користувачів із причиною; модерація категорій; розгляд скарг і звернень; окремі журнали дій користувачів та адміністраторів із пошуком і фільтром |

Стани товару: «Новий», «Як новий», «Задовільний», «З помітними дефектами», «На запчастини». Заблокований користувач бачить причину й дату блокування. Вкладки адмін-панелі мають власні адреси (наприклад, `/admin/logs/admins?category=complaints`), тому на них можна посилатися.

### Технології

| Шар | Стек |
|---|---|
| Клієнт | React 19, TypeScript, Vite, `react-router-dom` |
| Сервер | Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Сховище | PostgreSQL; in-memory режим без `DATABASE_URL` для розробки й тестів |
| Автентифікація | Microsoft Entra ID (OIDC, single-tenant), серверні сесії в HttpOnly-cookie |
| Якість | pytest (поріг покриття 85%), Hypothesis, mutation testing, Bandit, SonarCloud, GitHub Actions |
| Розгортання | Docker Compose, Traefik |

### Архітектура

```text
Браузер (React SPA) -> FastAPI /api/v1 -> сервіси -> репозиторії -> PostgreSQL
                              |                     (in-memory для тестів)
                              +-- Microsoft Entra ID (вхід)
```

Шари коду: домен, репозиторії, сервіси, роутери зі схемами. Докладніше: [HLD](docs/architecture/high-level-design.md), [модель даних](docs/architecture/data-model.md), [ADR](docs/architecture/decisions/), [опис веб-клієнта](docs/frontend/frontend.md).

## Зміст

- [Про проєкт](#про-проєкт)
- [Команда](#команда)
- [Стратегія роботи з гілками](#стратегія-роботи-з-гілками--github-flow)
- [Артефакти вимог](#артефакти-вимог)
- [Архітектура та проєктування](#архітектура-та-проєктування)
- [Проєктування та документація API](#проєктування-та-документація-api)
- [Якість коду, стандарти та безпека](#якість-коду-стандарти-та-безпека)
- [Тестування та налагодження](#тестування-та-налагодження)
- [Планування тестування та валідація](#планування-тестування-та-валідація)
- [Індивідуальні відеозвіти (Loom)](#індивідуальні-відеозвіти-loom)
- [Швидкий запуск та перевірки якості коду](#швидкий-запуск-та-перевірки-якості-коду)
- [Розгортання на сервері](#розгортання-на-сервері)

## Команда

| Учасник | Lab 1 — репозиторій | Lab 2 — вимоги | Lab 3 — архітектура | Lab 4 — API | Lab 5 — якість коду | Lab 6 — тестування | Lab 7 — валідація |
|---|---|---|---|---|---|---|---|
| **Артем Солодкий** | Repo Maintainer | Requirements Lead + Functional Requirements Lead | Data Model & Threat Modeling Lead | Quality Lead | Code Reviewer | Testing Lead + Test Doubles Lead | Test Planner |
| **Данііл Чернявський** | CI Maintainer | Quality Lead (NFR) | Architecture Lead | Backend Lead + API Design Lead | Quality & Prototype Lead | Debugging Lead | Review Manager + AI Code Reviewer |
| **Євгеній Остапенко** | Documentation Lead | Documentation Lead | Documentation & UML Lead | Documentation Lead | Documentation Lead | Testing Strategist | Documentation Lead |
| **Богдан Солонина** | Issue Tracker Lead | Traceability Lead | Traceability Lead | Integration Lead | Security Analyst | Integration Lead | Quality Analyst |

Детальний опис відповідальностей наведено в [Командному статуті](TeamCharter.md#2-ролі-та-відповідальності).

## Стратегія роботи з гілками — GitHub Flow

- `main` містить стабільну версію проєкту.
- Нова робота виконується в окремих гілках.
- Зміни додаються до `main` через Pull Request.
- Прямі push у `main` обмежені.

### Назви гілок

| Префікс | Призначення |
|---|---|
| `feature/...` | нова функціональність |
| `fix/...` | виправлення помилок |
| `docs/...` | зміни в документації |
| `ci/...` | зміни, пов'язані з CI/CD |
| `loom-videos` | файли з посиланням на відео до лабораторних |

## Артефакти вимог

- [Опис проєкту та Міні-ТЗ](Project-Description.md) — ідея проєкту, ролі користувачів, межі системи, функціональні й нефункціональні вимоги та обмеження.
- [Вимоги (FR та NFR)](docs/requirements/requirements.md) — функціональні вимоги та вимірювані NFR за стандартом ISO 25010.
- [Користувацькі історії](docs/requirements/user-stories.md) — історії користувачів із критеріями прийняття.
- [Матриця простежуваності (RTM)](docs/requirements/rtm.md) — зв'язок між історіями, NFR та тестами.
- [Сценарії використання (Use Cases)](docs/requirements/use-cases.md) — детальні сценарії взаємодії користувача із системою.

## Архітектура та проєктування

- [Високорівневий дизайн (HLD)](docs/architecture/high-level-design.md) — архітектурний стиль, опис системи та інтерфейсів.
- [Матриця простежуваності архітектури](docs/architecture/traceability-matrix.md) — відображення вимог на компоненти та сценарії якості.
- [Модель даних](docs/architecture/data-model.md) — схема бази даних (ER) із позначенням чутливих даних.
- [Модель загроз STRIDE](docs/architecture/threat-model.md) — аналіз меж довіри, ризиків та контрзаходів.
- [Архітектурні рішення (ADR)](docs/architecture/decisions/) — реєстр ключових технічних рішень проєкту:
  [ADR-001](docs/architecture/decisions/ADR-001-architectural-style.md),
  [ADR-002](docs/architecture/decisions/ADR-002-database-storage.md),
  [ADR-003](docs/architecture/decisions/ADR-003-auth-mechanism.md).
- [Автентифікація Microsoft Entra ID](docs/architecture/decisions/ADR-003-auth-mechanism.md) — single-tenant OIDC-рішення для облікових записів НаУКМА та поточний стан його налаштування.
- [UML-діаграми](docs/architecture/uml/) — сирцеві файли діаграм компонентів, послідовності та розгортання.

## Проєктування та документація API

- [Документація проєктування API (API Design)](docs/api/api-design.md) — ресурсна модель, ключові проєктні рішення, перелік кінцевих точок, версіонування та обробка помилок.
- [Атрибути якості API](docs/api/quality-attributes.md) — вимірювані цілі якості (`PERF-001`, `SEC-001`, `SEC-002`, `REL-001`), умови провалу, сценарії якості та результати перевірок через Swagger UI.
- [Інтерактивна документація (Swagger UI)](docs/api/index.html) — веб-інтерфейс перегляду та тестування API.
- [Згенерована специфікація OpenAPI](docs/api/openapi-generated.yaml) — файл специфікації OpenAPI 3.1 у форматі YAML.
- **GitHub Pages:** <https://ukma-fin-ssdm-2026.github.io/Next-Gen/docs/api/>

## Якість коду, стандарти та безпека

- [Політика якості та огляду коду](TeamCharter.md#49-політика-якості-та-огляду-коду-code-quality--review-policy) — стандарти PEP 8, конвенції іменування, правила коментування, критерії peer review та оновлений Definition of Done.
- [Статичний аналіз та аналіз безпеки](docs/code-quality/static-analysis.md) — результати перевірки Bandit, аналіз загрози TM-05 (STRIDE), усунення витоку контактів (SA-01) з регресійним тестом та фіксація прийнятого ризику (SA-02).
- [Звіт командного огляду коду](docs/code-quality/review-report.md) — результати рецензування кодової бази іншої команди за 5 критеріями.
- [Прогрес реалізації компонентів](docs/code-quality/progress.md) — стан розробки базової структури коду та мінімального прототипу системи.
- [Розподіл реалізації](docs/code-allocation.md) — модулі, файли, порядок інтеграції та матриця взаємного огляду.

## Тестування та налагодження

- [Стратегія тестування](docs/testing/testing-strategy.md) — комплексна стратегія тестування, аналіз покриття (98%), плани піраміди тестування, ворота якості в CI (поріг 85%) та бонуси.
- [Журнал налагодження](docs/testing/debugging-log.md) — 5 систематичних кроків відтворення, ізоляції та виправлення логічного дефекту фільтрації цін із регресійними тестами.
- [Звіт покриття коду](htmlcov/index.html) — інтерактивний HTML-звіт тестового покриття на рівні 98% за допомогою `pytest-cov`.
- [Property-Based тестування](tests/test_properties.py) — перевірка інваріантів каталогу на згенерованих вхідних даних за допомогою `hypothesis` (Бонус).
- [Mutation testing](docs/testing/mutation-testing.md) — перевірка стійкості тестів до навмисних змін бізнес-логіки: знищено 54 з 54 мутантів (Бонус).

## Планування тестування та валідація

- [План тестування](docs/validation/test-plan.md) — обсяг, критерії виходу, аналіз ризиків та таблиця тест-кейсів різних рівнів із трасуванням до вимог.
- [Журнал взаємного огляду та огляду ШІ-коду](docs/validation/review-log.md) — підсумки взаємного огляду тест-плану з командою B2B, внесені зміни та контрольний список огляду ШІ-згенерованого коду.

## Індивідуальні відеозвіти (Loom)

| Лабораторна | Чернявський | Остапенко | Солодкий | Солонина |
|---|---|---|---|---|
| [Lab 1](Labs/Lab01/) (`Labs/Lab01/`) | [відео](Labs/Lab01/video_Cherniavskyi.txt) | [відео](Labs/Lab01/video_Ostapenko.txt) | [відео](Labs/Lab01/video_Solodkyi.txt) | [відео](Labs/Lab01/video_Solonyna.txt) |
| [Lab 2](Labs/Lab02/) (`Labs/Lab02/`) | [відео](Labs/Lab02/video_Cherniavskyi.txt) | [відео](Labs/Lab02/video_Ostapenko.txt) | [відео](Labs/Lab02/video_Solodkyi.txt) | [відео](Labs/Lab02/video_Solonyna.txt) |
| [Lab 3](Labs/Lab03/) (`Labs/Lab03/`) | [відео](Labs/Lab03/video_Cherniavskyi.txt) | [відео](Labs/Lab03/video_Ostapenko.txt) | [відео](Labs/Lab03/video_Solodkyi.txt) | [відео](Labs/Lab03/Video_Solonyna.txt) |
| [Lab 4](Labs/Lab04/) (`Labs/Lab04/`) | [відео](Labs/Lab04/video_Cherniavskyi.txt) | [відео](Labs/Lab04/video_Ostapenko.txt) | [відео](Labs/Lab04/video_Solodkyi.txt) | [відео](Labs/Lab04/video_Solonyna.txt) |
| [Lab 5](Labs/Lab05/) (`Labs/Lab05/`) | [відео](Labs/Lab05/video_Cherniavskyi.txt) | [відео](Labs/Lab05/video_Ostapenko.txt) | [відео](Labs/Lab05/video_Solodkyi.txt) | [відео](Labs/Lab05/video_Solonyna.txt) |
| [Lab 6](Labs/Lab06/) (`Labs/Lab06/`) | [відео](Labs/Lab06/video_Cherniavskyi.txt) · [TDD](Labs/Lab06/videoTDD_Cherniavskyi.txt) | [відео](Labs/Lab06/video_Ostapenko.txt) | [відео](Labs/Lab06/video_Solodkyi.txt) | [відео](Labs/Lab06/video_Solonyna.txt) |
| [Lab 7](Labs/Lab07/) (`Labs/Lab07/`) | [відео](Labs/Lab07/video_Cherniavskyi.txt) | [відео](Labs/Lab07/video_Ostapenko.txt) | [відео](Labs/Lab07/video_Solodkyi.txt) | [відео](Labs/Lab07/video_Solonyna.txt) |

## Швидкий запуск та перевірки якості коду

### 1. Встановлення залежностей розробки та тестування

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
```

### 2. Автогенерація специфікації OpenAPI з коду

```bash
python scripts/generate_openapi.py
```

*Специфікація автоматично зчитується з FastAPI-застосунку (`src/api/main.py`) та зберігається у `docs/api/openapi-generated.yaml`.*

### 3. Запуск аналізатора безпеки (Bandit)

```bash
python -m bandit -r src scripts -v
```

### 4. Запуск автоматизованих тестів із перевіркою порогу покриття (Coverage Gate 85%)

```bash
python -m pytest -q --cov=src --cov-report=term-missing --cov-fail-under=85
```

### 5. Локальний запуск API сервера

```bash
set -a; source .env.development; set +a
.venv/bin/python -m uvicorn src.api.main:app --reload --port 8000
```

Файл `.env.development` містить лише несекретні локальні значення. Кнопка входу створює
тестову серверну сесію без звернення до Microsoft. Production `.env`
не зберігається в репозиторії і не повинен містити `DEV_AUTH_ENABLED=true`.

Адміністраторів задає змінна `ADMIN_EMAILS` (адреси `@ukma.edu.ua` через кому): користувач із цієї
адреси отримує роль `ADMIN` під час входу, а після видалення зі списку повертається до `USER` при
наступному вході. Для локальної розробки в `.env.development` це `developer@ukma.edu.ua`. Після зміни
production `.env` контейнер API треба перестворити (`docker compose up -d`).

*Інтерактивна документація FastAPI доступна за адресою:* <http://localhost:8000/docs>

### 6. Запуск клієнта

```bash
cd frontend
npm ci
npm run dev        # http://127.0.0.1:5173, /api проксується на :8000
npm run build      # збірка в frontend/dist, яку віддає FastAPI
```

Докладніше про клієнт: [docs/frontend/frontend.md](docs/frontend/frontend.md).

## Розгортання на сервері

Розгорнута версія: <https://baraholka-naukma.duckdns.org> (Docker Compose, Traefik).

```bash
docker compose up -d --build  # збірка, міграції (сервіс migrate) і запуск
```

- Змінні середовища беруться з `.env` (шаблон — `.env.example`): Microsoft Entra, `BARAHOLKA_HOST`, `ADMIN_EMAILS`, `DATABASE_URL`.
- Схему БД створюють і оновлюють міграції Alembic (`alembic upgrade head`); `alembic check` у CI має показувати «No new upgrade operations detected».
- Резервне копіювання й відновлення: [docs/operations/backup-restore.md](docs/operations/backup-restore.md).
- Перевірка працездатності: <https://baraholka-naukma.duckdns.org/health>.
