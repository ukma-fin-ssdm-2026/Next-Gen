# Changelog

Усі помітні зміни проєкту Baraholka NaUKMA фіксуються в цьому файлі.

Формат відповідає [Keep a Changelog](https://keepachangelog.com/uk/1.1.0/),
а нумерація версій — [семантичному версіонуванню](https://semver.org/lang/uk/)
(`MAJOR.MINOR.PATCH`). Номер версії однаковий у `src/__init__.py`,
`pyproject.toml`, `frontend/package.json`, у цьому журналі та в git-тегу `vX.Y.Z`;
узгодженість перевіряє `tests/test_version.py`.

## [Unreleased]

## [1.1.0] - 2026-11-04

Реліз Лабораторної 8 (рефакторинг). Версія MINOR, а не PATCH, бо після `1.0.0`
додано нову функціональність адміністратора (розділ Added); рефакторинги
поведінку не змінюють.

### Added

- Керування категоріями в адмін-панелі: створення, перейменування і
  деактивація без втрати наявних оголошень; власний slug під час схвалення
  пропозиції категорії (FR-012).

### Fixed

- Slug категорії перевіряється за безпечним шаблоном у домені та API;
  системну резервну категорію не можна деактивувати.
- Знахідки безпеки SonarCloud: API-клієнт фронтенду будує лише same-origin URL
  під префіксом API, динамічні сегменти обмежено UUID; залежності CI
  зафіксовано в `requirements-ci.lock`.

### Refactoring

- `src/db/converters.py`: однотипне заповнення рядків ORM у конвертерах
  `*_domain_to_row` замінено спільною функцією `_populate_row`. Техніка:
  Extract Function. Поведінку фіксують характеризаційні тести
  `tests/test_converters.py`, написані до зміни.
- `src/services/listings.py`: довгий метод `ListingService.create` розбито на
  `_resolve_target_category_for_creation`, `_save_listing_with_suggestion` і
  `_cleanup_failed_creation`. Техніка: Extract Method. Тести:
  `tests/test_listing_service.py`, `tests/test_listings_api.py`.
- `src/domain/feedback.py`: дубльовану перевірку меж довжини в
  `Feedback.__post_init__` винесено в `_validate_text_length`. Техніка: Extract
  Method. Тести: `tests/test_feedback_characterization.py`, написані до зміни.
- `frontend/src/App.tsx`: клікабельні `div` у `PhotoCropper` замінено на
  `<button type="button">`, галерея оголошення позначена як `region`
  (SonarCloud S6848). Техніка: Replace Element with Semantic Element.
  Перевірка: `npm test`, `npm run build`.
- Номер версії, що повторювався рядком `"1.0.0"` у `src/api/main.py` (FastAPI і
  `/health`), винесено в єдину константу `src.__version__`; версію фронтенду
  (`0.1.0`) узгоджено з бекендом. Техніка: Replace Magic Literal with Symbolic
  Constant. Поведінка API не змінилась: OpenAPI і `/health` повертають ту саму
  версію, що доводить `tests/test_version.py`.

## [1.0.0] - 2026-11-01

Стан проєкту на проміжне оцінювання (тег курсу `midterm-project-2026-11-02`).

### Added

- Вхід через Microsoft Entra ID НаУКМА із серверними сесіями; роль адміністратора
  задається списком `ADMIN_EMAILS` (FR-001, FR-013, SEC-001).
- Оголошення з фото (1–10, нормалізація у WebP), редагування, зняття з публікації
  та історія власних оголошень (FR-002–FR-005).
- Каталог із пошуком, фільтрами, сортуванням і пагінацією (FR-006–FR-008).
- Обране і контакт продавця лише для автентифікованих користувачів
  (FR-009, FR-010, SEC-002).
- Модерація: зняття оголошень із причиною, блокування користувачів, категорії та
  пропозиції нових категорій, журнал `ModerationAction` (FR-011–FR-013, FR-015).
- Профіль користувача (FR-014); скарги, звернення до адміністрації та журнали
  дій (FR-016–FR-018).
- Зберігання в PostgreSQL через SQLAlchemy і міграції Alembic; React-інтерфейс,
  який віддає FastAPI.
- Розгортання через Docker Compose і Traefik (HTTPS):
  <https://baraholka-naukma.duckdns.org>.
- CI: Black, Flake8, Bandit, pip-audit, тести фронтенду й бекенду з порогом
  покриття 85%, перевірка OpenAPI, job із PostgreSQL 16 і Alembic.

### Refactoring

- `frontend/src/contactLinks.ts`: перевірку email регулярним виразом із
  ризиком backtracking (SonarCloud S5852) замінено лінійною перевіркою
  `isEmail`, посилання на контакт будує `contactHref`. Техніка: Substitute
  Algorithm, Extract Function. Тест: `frontend/tests/contactLinks.test.mjs`.
- `frontend/src/App.tsx`: довгу функцію `confirm` у `PhotoCropper` розбито,
  заливку полів винесено в `paintGaps`, числа й кольори — в `GAP_COLORS` і
  `BLUR_SAMPLE`. Техніка: Extract Function, Replace Magic Number with Symbolic
  Constant.

[Unreleased]: https://github.com/ukma-fin-ssdm-2026/Next-Gen/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/ukma-fin-ssdm-2026/Next-Gen/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/ukma-fin-ssdm-2026/Next-Gen/releases/tag/v1.0.0
