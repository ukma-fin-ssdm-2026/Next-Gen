[![CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/workflows/ci.yml/badge.svg)](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/workflows/ci.yml)
# Baraholka NaUKMA

Командний проєкт з курсу SSDM 2026.

## Команда 

| Учасник | Lab 1 — репозиторій | Lab 2 — вимоги | Lab 3 — архітектура | Lab 4 — API |
|---|---|---|---|---|
| **Артем Солодкий** | Repo Maintainer | Requirements Lead + Functional Requirements Lead | Data Model & Threat Modeling Lead | Quality Lead |
| **Данііл Чернявський** | CI Maintainer | Quality Lead (NFR) | Architecture Lead | Backend Lead + API Design Lead |
| **Євгеній Остапенко** | Documentation Lead | Documentation Lead | Documentation & UML Lead | Documentation Lead |
| **Богдан Солонина** | Issue Tracker Lead | Traceability Lead | Traceability Lead | Integration Lead |

Детальний опис відповідальностей наведено в [Командному статуті](TeamCharter.md#2-ролі-та-відповідальності).

## Стратегія роботи з гілками - GitHub Flow

- `main` містить стабільну версію проєкту.
- Нова робота виконується в окремих гілках.
- Зміни додаються до `main` через Pull Request.
- Прямі push у `main` обмежені.

### Назви гілок

- `feature/...` - нова функціональність
- `fix/...` - виправлення помилок
- `docs/...` - зміни в документації
- `ci/...` - зміни, пов'язані з CI/CD
- `loom-videos` - файли з посиланням на відео до лабораторних

## Артефакти вимог

- [Вимоги (FR та NFR)](docs/requirements/requirements.md) - функціональні вимоги та вимірювані NFR за стандартом ISO 25010.
- [Користувацькі історії](docs/requirements/user-stories.md) - історії користувачів із критеріями прийняття.
- [Матриця простежуваності (RTM)](docs/requirements/rtm.md) - зв'язок між історіями, NFR та тестами.
- [Сценарії використання (Use Cases)](docs/requirements/use-cases.md) - детальні сценарії взаємодії користувача із системою.

## Архітектура та проєктування

- [Високорівневий дизайн (HLD)](docs/architecture/high-level-design.md) - архітектурний стиль, опис системи та інтерфейсів.
- [Матриця простежуваності архітектури](docs/architecture/traceability-matrix.md) - відображення вимог на компоненти та сценарії якості.
- [Модель даних](docs/architecture/data-model.md) - схема бази даних (ER) із позначенням чутливих даних.
- [Модель загроз STRIDE](docs/architecture/threat-model.md) - аналіз меж довіри, ризиків та контрзаходів.
- [Архітектурні рішення (ADR)](docs/architecture/decisions/) - реєстр ключових технічних рішень проєкту.
- [UML-діаграми](docs/architecture/uml/) - сирцеві файли діаграм компонентів, послідовності та розгортання.

## Проєктування та документація API

- [Інтерактивна документація (Swagger UI)](docs/api/index.html) - веб-інтерфейс перегляду та тестування API.
- [Згенерована специфікація OpenAPI](docs/api/openapi-generated.yaml) - файл специфікації OpenAPI 3.1 у форматі YAML.
- **GitHub Pages:** https://ukma-fin-ssdm-2026.github.io/Next-Gen/docs/api/

### Швидкий запуск та автогенерація OpenAPI

1. **Встановлення залежностей:**
   ```bash
   pip install fastapi pyyaml uvicorn
   ```

2. **Автогенерація специфікації OpenAPI з коду:**
   ```bash
   python scripts/generate_openapi.py
   ```
   *Специфікація автоматично зчитується з FastAPI-застосунку (`src/api/main.py`) та зберігається у `docs/api/openapi-generated.yaml`.*

3. **Локальний запуск API сервера:**
   ```bash
   uvicorn src.api.main:app --reload --port 8000
   ```
   *Інтерактивна документація FastAPI доступна за адресою:* `http://localhost:8000/docs`

