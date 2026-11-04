# Changelog

Усі помітні зміни проєкту Baraholka NaUKMA фіксуються в цьому файлі.

Формат відповідає [Keep a Changelog](https://keepachangelog.com/uk/1.1.0/),
а нумерація версій — [семантичному версіонуванню](https://semver.org/lang/uk/)
(`MAJOR.MINOR.PATCH`). Номер версії однаковий у `src/__init__.py`,
`pyproject.toml`, `frontend/package.json`, у цьому журналі та в git-тегу `vX.Y.Z`;
узгодженість перевіряє `tests/test_version.py`.

## [Unreleased]

### Refactoring

- **Бекенд (ORM / Domain)**: `src/db/converters.py` — усунено дублювання коду та рутинне зіставлення полів при двосторонній конвертації між SQLAlchemy ORM моделями та Domain dataclass за допомогою узагальнених допоміжних функцій `_populate_row` та `_row_to_domain`. Забезпечено повну еквівалентність контрактів і цілісність інкапсуляції, підтверджену характеризаційними тестами `tests/test_converters.py` (20 тестів, 100% покриття).
- **Бекенд (Сервіси)**: `src/services/listings.py` — декомпоновано довгий метод `ListingService.create` (техніка Extract Method: виділено `_resolve_category`). Знижено цикломатичну складність, ізольовано валідацію/дозволи категорій та спрощено читабельність бізнес-логіки створення оголошення.
- **Фронтенд (Доступність та безпека)**: `frontend/src/App.tsx` — покращено семантику доступності (заміна несемантичних клікабельних елементів на нативні `<button>` у кропері фотографій `PhotoCropper`, додано коректні ARIA-атрибути для скрінрідерів у галереї `ListingGallery`) та усунено потенційний ризик ReDoS / некоректного парсингу.
- **Константи версій**: Номер версії, що повторювався рядком `"1.0.0"` у `src/api/main.py` (FastAPI і `/health`), винесено в єдину константу `src.__version__`; версію фронтенду узгоджено з бекендом. Техніка: Replace Magic Literal with Symbolic Constant. Поведінка API не змінилась: OpenAPI і `/health` повертають ту саму версію, що доводить `tests/test_version.py`.

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

[Unreleased]: https://github.com/ukma-fin-ssdm-2026/Next-Gen/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/ukma-fin-ssdm-2026/Next-Gen/releases/tag/v1.0.0
