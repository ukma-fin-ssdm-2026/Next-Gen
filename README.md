[![CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/workflows/ci.yml/badge.svg)](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/workflows/ci.yml)
# Baraholka NaUKMA

Командний проєкт з курсу SSDM 2026.

## Команда 

| Учасник | Lab 1 — репозиторій | Lab 2 — вимоги | Lab 3 — архітектура | Lab 4 — API | Lab 5 — якість коду | Lab 6 — тестування |
|---|---|---|---|---|---|---|
| **Артем Солодкий** | Repo Maintainer | Requirements Lead + Functional Requirements Lead | Data Model & Threat Modeling Lead | Quality Lead | Code Reviewer | Testing Lead + Test Doubles Lead |
| **Данііл Чернявський** | CI Maintainer | Quality Lead (NFR) | Architecture Lead | Backend Lead + API Design Lead | Quality & Prototype Lead | Debugging Lead |
| **Євгеній Остапенко** | Documentation Lead | Documentation Lead | Documentation & UML Lead | Documentation Lead | Documentation Lead | Testing Strategist |
| **Богдан Солонина** | Issue Tracker Lead | Traceability Lead | Traceability Lead | Integration Lead | Security Analyst | Integration Lead |

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
- [Автентифікація Microsoft Entra ID](docs/architecture/decisions/ADR-003-auth-mechanism.md) - single-tenant OIDC-рішення для облікових записів НаУКМА та поточний стан його налаштування.
- [UML-діаграми](docs/architecture/uml/) - сирцеві файли діаграм компонентів, послідовності та розгортання.

## Проєктування та документація API

- [Інтерактивна документація (Swagger UI)](docs/api/index.html) - веб-інтерфейс перегляду та тестування API.
- [Згенерована специфікація OpenAPI](docs/api/openapi-generated.yaml) - файл специфікації OpenAPI 3.1 у форматі YAML.
- **GitHub Pages:** https://ukma-fin-ssdm-2026.github.io/Next-Gen/docs/api/

## Якість коду, стандарти та безпека

- [Політика якості та огляду коду](TeamCharter.md#49-політика-якості-та-огляду-коду-code-quality--review-policy) - стандарти PEP 8, конвенції іменування, правила коментування, критерії peer review та оновлений Definition of Done.
- [Статичний аналіз та аналіз безпеки](docs/code-quality/static-analysis.md) - результати перевірки Bandit, аналіз загрози TM-05 (STRIDE), усунення витоку контактів (SA-01) з регресійним тестом та фіксація прийнятого ризику (SA-02).
- [Звіт командного огляду коду](docs/code-quality/review-report.md) - результати рецензування кодової бази іншої команди за 5 критеріями.
- [Прогрес реалізації компонентів](docs/code-quality/progress.md) - стан розробки базової структури коду та мінімального прототипу системи.

## Тестування та налагодження

- [Стратегія тестування](docs/testing/testing-strategy.md) - комплексна стратегія тестування, аналіз покриття (98%), плани піраміди тестування, ворота якості в CI (поріг 85%) та бонуси.
- [Журнал налагодження](docs/testing/debugging-log.md) - 5 систематичних кроків відтворення, ізоляції та виправлення логічного дефекту фільтрації цін із регресійними тестами.
- [Звіт покриття коду](htmlcov/index.html) - інтерактивний HTML-звіт тестового покриття на рівні 98% за допомогою `pytest-cov`.
- [Property-Based тестування](tests/test_properties.py) - перевірка інваріантів каталогу на згенерованих вхідних даних за допомогою `hypothesis` (Бонус).
- [Mutation testing](docs/testing/mutation-testing.md) - перевірка стійкості тестів до навмисних змін бізнес-логіки: знищено 54 з 54 мутантів (Бонус).

### Швидкий запуск та перевірки якості коду

1. **Встановлення залежностей розробки та тестування:**
   ```bash
   python -m pip install -r requirements.txt -r requirements-dev.txt
   ```

2. **Автогенерація специфікації OpenAPI з коду:**
   ```bash
   python scripts/generate_openapi.py
   ```
   *Специфікація автоматично зчитується з FastAPI-застосунку (`src/api/main.py`) та зберігається у `docs/api/openapi-generated.yaml`.*

3. **Запуск аналізатора безпеки (Bandit):**
   ```bash
   python -m bandit -r src scripts -v
   ```

4. **Запуск автоматизованих тестів із перевіркою порогу покриття (Coverage Gate 85%):**
   ```bash
   python -m pytest -q --cov=src --cov-report=term-missing --cov-fail-under=85
   ```


5. **Локальний запуск API сервера:**
   ```bash
   uvicorn src.api.main:app --reload --port 8000
   ```
   *Інтерактивна документація FastAPI доступна за адресою:* `http://localhost:8000/docs`

