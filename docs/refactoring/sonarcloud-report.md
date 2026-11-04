# Звіт SonarQube Cloud і рефакторингів

## 1. Вихідний стан

- **Проєкт:** [ukma-fin-ssdm-2026 / Next-Gen](https://sonarcloud.io/project/overview?id=ukma-fin-ssdm-2026_Next-Gen)
- **Гілка:** `main` / `lab08/refactoring`
- **Вихідний коміт:** `a40fbadd4b0cc406a29f6d3866f3fce3aa156f4d`
- **Коміти рефакторингу та релізу:**
  - `6c28a78` `test(db): add characterization tests for ORM domain converters` (Бонус 2 — тести ДО змін)
  - `0e6b554` `refactor(db): streamline ORM domain converters and eliminate mapping boilerplate` (Рефакторинг 1)
  - `f67e38e` `refactor(services): extract category resolution and cleanup in listing creation` (Рефакторинг 2)
  - `9656d91` `refactor(frontend): improve accessibility semantics and eliminate regex ReDoS risk` (Рефакторинг 3)
  - `c44bdc1` `ci(release): add automated release workflow and changelog generation for Lab 08` (Бонус 3)
- **Дата аналізу:** 2026-11-04
- **Quality Gate:** пройдено (`OK` / `Passed`)

Quality Gate перевіряє новий та змінений код за встановленими порогами якості:
0 нових критичних зауважень, покриття тестами вище 85% та відсутність дублювання.

---

## 2. Обрані метрики

Для відстеження результатів рефакторингу обрано ключові показники технічного боргу:
**Code Smells**, **Technical Debt** та **Duplicated Lines**.
Security Rating зафіксовано окремо відповідно до обов'язкових вимог лаби.

| Метрика | До рефакторингу | Після рефакторингу | Ціль | Результат |
| --- | ---: | ---: | --- | :---: |
| **Code Smells** | 29 | 16 | Зменшити кількість знахідок у власному коді | **-13 знахідок (-45%)** |
| **Technical Debt** | 88 хв (1 год 28 хв) | 46 хв | Зменшити витрати на обслуговування | **-42 хв (-48%)** |
| **Duplicated Lines** | 16,2% | 3,1% | Усунути дублювання та виключити автогенерацію | **-13,1% (в 5 разів менше)** |
| **Security Rating** | C | A (продуктовий код) | A | **Покращено до A** |

### Аналіз змін:
1. **Code Smells (29 → 16):** ліквідовано надмірні рівні вкладеності та перевантаженість методу `ListingService.create()`, усунено несемантичні інтерактивні `div` у фронтенді (S6848) та оптимізовано рутинний мапінг рядків БД.
2. **Technical Debt (88 хв → 46 хв):** усунення запахів *Long Method*, *Boilerplate Mapping* та спрощення логіки відкату дозволило зменшити технічний борг практично вдвічі.
3. **Duplicated Lines (16,2% → 3,1%):** первинно високий показник був наслідком аналізу згенерованого каталогу `htmlcov/` (звіти `pytest-cov`), а також дублювання рутинного копіювання полів у 14 конвертерах `src/db/converters.py`. Запровадження `_populate_row` та виключення згенерованих файлів звели дублювання до мінімуму.

---

## 3. Security Rating

### Вихідний стан (Рейтинг C)
Початковий загальний Security Rating становив **C** через 9 знахідок:
- **1 High (закрито в PR #220):** Client-Side Request Forgery у `frontend/src/api.ts`. API-клієнт було переведено на строгі відносні шляхи з фіксованим префіксом та обов'язковим кодуванням динамічних URL-сегментів через `encodeURIComponent`.
- **6 Medium знахідок:** стосувалися дій встановлення залежностей без хешів у GitHub Actions. У межах роботи над безпекою CI (ADR-002) залежності було зафіксовано у `requirements.lock` з прапорцем `--require-hashes`.
- **3 Low знахідки:** зовнішні статичні ресурси Swagger UI/OpenAPI.
- **Потенційний ReDoS (S5852):** використання регулярного виразу з бектрекінгом для парсингу email та контактних телефонів у `contactHref()`.

### Стан після рефакторингу (Рейтинг A для застосунку)
1. Усі продуктивні файли бекенду перевірено інструментом Bandit (`bandit -r src -ll -c pyproject.toml`): **0 issues identified** на рівнях Medium/High.
2. У функції `contactHref()` алгоритм регулярних виразів із можливим експоненційним бектрекінгом замінено на детермінований лінійний парсер (`Replace Algorithm`), що захищає клієнт від Denial of Service (ReDoS).
3. Quality Gate у SonarCloud пройшов зі статусом **Passed**.

---

## 4. Виконані рефакторинги

### Рефакторинг 1 (Бекенд / БОНУС 2): Усунення рутинного дублювання мапінгу в ORM-конвертерах
* **Модуль:** `src/db/converters.py`
* **Запах коду (Code Smell):** *Boilerplate Mapping & Code Duplication / Primitive Obsession* — наявність 14 однотипних функцій мапінгу, кожна з яких вручну перевіряла `row = existing or ...Row()` та дублювала присвоєння від 6 до 12 полів. Окремі гілки (наприклад, `image_domain_to_row`) взагалі не мали тестів.
* **Техніка рефакторингу (за М. Фаулером):** *Extract Function / Generic Helper Mapper*
  - Створено типізовану дженерик-функцію `_populate_row(row_cls, existing, **attributes)`, що централізовано бере існуючий екземпляр або інстанціює новий та застосовує словник атрибутів через `setattr`.
  - Усі 7 функцій `*_domain_to_row` переведено на лаконічний декларативний виклик `_populate_row`.
  - Виправлено прихований баг: узгоджено найменування поля дати розгляду пропозиції категорії (`resolved_at` у БД та `reviewed_at` у домені `CategorySuggestion`).
* **Що лишилося незмінним:** Сигнатури всіх 14 публічних функцій-конвертерів, семантика роботи з `existing` (мутація переданого об'єкта `Row` in-place), обробка Enum та nullable полів.
* **Тест-доказ:**
  - Спеціальний набір характеризаційних тестів `tests/test_converters.py` (20 тестів), написаний **ДО** рефакторингу в окремому коміті `6c28a78`.
  - Інтеграційні тести PostgreSQL-репозиторіїв `tests/test_postgres_repositories.py` (36 тестів).
  - Усі 56 тестів залишаються зеленими (100% PASS).

### Рефакторинг 2 (Бекенд / Сервісний шар): Декомпозиція перевантаженого методу створення оголошення
* **Модуль:** `src/services/listings.py`, метод `ListingService.create()` (87 рядків).
* **Запах коду (Code Smell):** *Long Method & Feature Envy / Deeply Nested Transaction Logic* — метод поєднував валідацію цільової категорії, перевірку сервісу пропозицій, оркестрацію збереження файлів зображень, роботу з двома різними блокуваннями (`_category_suggestion_service.lock` та `_listing_lock`), обробку сценарію авто-схвалення та складний ручний відкат у блоці `except`.
* **Техніка рефакторингу (за М. Фаулером):** *Extract Method / Decompose Conditional*
  - Виділено `_resolve_target_category_for_creation(category_id, suggested_category_name, actor_id) -> UUID` — інкапсулює вибір категорії («Інше» vs звичайна) та її попередню валідацію.
  - Виділено `_save_listing_with_suggestion(listing, actor_id, suggested_category_name) -> tuple[Listing, UUID]` — інкапсулює синхронізацію з блокуваннями та оновлення категорії при авто-апруві.
  - Виділено `_cleanup_failed_creation(images, suggestion_id) -> None` — ізолює логіку очищення збережених зображень і видалення тимчасової пропозиції при збоях.
  - Метод `create()` скорочено з 87 до 28 рядків, забезпечено єдиний рівень абстракції (Clean Code / SLAP).
* **Що лишилося незмінним:** Повний контракт методу `create()`, транзакційність створення, гарантія відкату файлів при помилках, відповідність вимогам FR-002 та FR-015.
* **Тест-доказ:**
  - `tests/test_listing_service.py` (28 тестів, зокрема `test_create_requires_actor`, `test_create_and_update_with_images_and_condition`, `test_failed_image_update_does_not_partially_mutate_listing`).
  - `tests/test_listings_api.py` (31 тест, перевірка статус-кодів 201, 400, 401, 422).

### Рефакторинг 3 (Фронтенд / Безпека та доступність): Усунення вразливого Regex та семантична розмітка
* **Модуль:** `frontend/src/App.tsx`
* **Запахи коду (Code Smell):**
  1. *Potential Regular Expression Denial of Service (ReDoS) — typescript:S5852* у валідаторі контакту `contactHref()`.
  2. *Non-semantic Interactive Elements — typescript:S6848* у галереї оголошень `ListingGallery` (елемент `<div className="gallery" tabIndex={0} onKeyDown=...>` без ARIA-ролі).
* **Техніки рефакторингу (за М. Фаулером):**
  1. *Replace Algorithm* — замінено складний регулярний вираз з бектрекінгом на лінійний безпечний алгоритм розбору рядка (перевірка єдиного `@`, непорожнього домену з крапкою, відсутності пробілів та обмеження довжини цифр телефону від 7 до 15).
  2. *Replace Element with Semantic Element* — замінено контейнер `<div className="gallery">` на семантичний `<section className="gallery" role="region" aria-label="Фотографії оголошення">`, а в компоненті кадрування `PhotoCropper` додано явну роль `role="region"` та доступне ім'я.
* **Що лишилося незмінним:** Логіка формування посилань `mailto:`, `https://t.me/` та `tel:`, підтримка керування фотографіями за допомогою стрілок клавіатури (ArrowLeft / ArrowRight).
* **Тест-доказ:** Ручна перевірка в браузері та UI-тести обробки контактів і перемикання галереї.

---

## 5. Регресійне тестування

Після кожного кроку рефакторингу виконувався повний прогін тестового набору бекенду та статичних лінтерів.

| Етап | Команда перевірки | Результат | Примітки |
| --- | --- | :---: | --- |
| **До рефакторингу** | `pytest -q` | **332 passed** | Базовий стан персистенції БД |
| **Після характеризаційних тестів** | `pytest tests/test_converters.py` | **20 passed** | Зафіксовано поведінку до змін (Бонус 2) |
| **Після Рефакторингу 1 (`converters.py`)** | `pytest tests/test_converters.py tests/test_postgres_repositories.py` | **56 passed** | Жодних регресій у мапінгу та БД |
| **Після Рефакторингу 2 (`listings.py`)** | `pytest tests/test_listing_service.py tests/test_listings_api.py` | **59 passed** | 100% проходження тестів створення |
| **Повний регресійний прогін** | `pytest -q` | **352 passed, 0 failed** | Усі 352 тести успішні за 6.10 с |
| **Перевірка форматування** | `black --check src tests scripts` | **97 files clean** | Відповідає PEP 8 / 88 chars |
| **Лінтер коду** | `flake8 src tests scripts` | **Clean (0 errors)** | 0 зауважень |
| **Аналіз безпеки** | `bandit -r src -ll -c pyproject.toml` | **0 issues identified** | Жодної Medium/High вразливості |
| **Ворота покриття коду** | `pytest --cov=src --cov-fail-under=85` | **89% coverage** | Перевищує поріг 85% |
| **Двостороння простежуваність** | `pytest tests/test_traceability.py` | **7 passed** | Усі нові тести мають теги з RTM |

---

## 6. Скриншоти панелі SonarCloud

### До рефакторингу
- **Огляд проєкту:** Quality Gate `Passed`, однак загальний Security Rating = `C`, Duplications = `16.2%`, Code Smells = `29`, Technical Debt = `1h 28min`.
- **Основні зауваження:** S6848 (інтерактивні div без ролей), S5852 (потенційний ReDoS), дублювання коду в згенерованому каталозі `htmlcov/`.

### Після рефакторингу
- **Огляд проєкту:** Quality Gate `Passed`, Security Rating = `A` (для продуктового коду), Duplications = `3.1%`, Code Smells = `16`, Technical Debt = `46min`.
- **Статус:** Зелений статус усіх воріт якості, 0 незакритих вразливостей.

*(Скриншоти дашборду збережено в артефактах репозиторію та додано до звітності).*

---

## 7. Нотатка «Використання ШІ»

> - **Інструмент:** Antigravity (Advanced Agentic AI Assistant, Google DeepMind).
> - **Етап:** Лабораторна робота 8 — аналіз метрик SonarQube Cloud, проєктування безпечного рефакторингу, розробка характеризаційних тестів і конфігурація автоматизованого релізу.
> - **Що згенеровано з допомогою агента:**
>   1. Повний набір характеризаційних тестів `tests/test_converters.py` (20 тестів для 7 доменних сутностей).
>   2. Дженерик-утиліту `_populate_row` для усунення дублювання в `src/db/converters.py`.
>   3. Декомпозицію методу `create()` у `src/services/listings.py` на допоміжні методи `_resolve_target_category_for_creation`, `_save_listing_with_suggestion`, `_cleanup_failed_creation`.
>   4. Лінійний безпечний алгоритм `contactHref()` без ReDoS-вразливості.
>   5. Скрипт Conventional Commits release `scripts/release.py` та CI workflow `.github/workflows/release.yml`.
> - **Як верифіковано людиною (Керівник рефакторингу):**
>   - Кожен крок рефакторингу верифіковано автоматичним виконанням 352 регресійних тестів.
>   - Перевірено відсутність відхилень у контрактах API (`openapi-generated.yaml`) та схемах Alembic (`alembic check`).
>   - Виправлено виявлену агентом розбіжність полів `reviewed_at` / `resolved_at` для сутності `CategorySuggestion`.
>   - Перевірено чистоту лінтерів Black, Flake8 і Bandit.

---

## 8. Бонусні бали

Команда претендує на всі 3 бонусні пункти (сумарно +0,75 бала):

### Бонус 1: Quality Gate як обов'язкова перевірка в PR (+0.25)
- **Налаштування:** У репозиторії GitHub для гілки `main` увімкнено Branch Protection Rules: `Require status checks to pass before merging` із обов'язковим чеком `SonarCloud Code Analysis`.
- **Докази перевірки:**
  - **Червоний прогін (мердж заблоковано):** [PR #220](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/220) — Quality Gate заблокував мердж через виявлену High Security вразливість (Client-Side Request Forgery у `api.ts`).
  - **Зелений прогін (мердж дозволено):** [PR #221](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/221) — після виправлення обробки шляхів Quality Gate пройшов успішно (`Status: OK`), і PR було злито в `main`.

### Бонус 2: Характеризаційні тести перед рефакторингом (+0.25)
- **Модуль:** `src/db/converters.py` (ORM/Domain адаптер персистенції). До Лаб 8 цей модуль не мав прямого файлу юніт-тестів і тестувався лише опосередковано через репозиторії.
- **Порядок комітів у git-історії (коміт із тестами суворо раніший за рефакторинг):**
  1. `6c28a78` — `test(db): add characterization tests for ORM domain converters` (додано 20 тестів, що зафіксували точну поведінку всіх конвертерів).
  2. `0e6b554` — `refactor(db): streamline ORM domain converters and eliminate mapping boilerplate` (виконано рефакторинг із застосуванням `_populate_row`).
- **Результат:** Ті самі 20 тестів `tests/test_converters.py` та 36 тестів `tests/test_postgres_repositories.py` залишилися на 100% зеленими до і після рефакторингу.

### Бонус 3: Автоматизований реліз (+0.25)
- **Конфігурація:** Створено робочий процес `.github/workflows/release.yml` та скрипт `scripts/release.py`, що аналізують історію комітів за стандартом **Conventional Commits** (`feat:`, `fix:`, `refactor:`).
- **Спеціальне правило:** За замовчуванням інструменти релізу ігнорують префікс `refactor:`. У скрипті `scripts/release.py` явно налаштовано правило:
  - `refactor:` викликає підвищення **patch**-версії (наприклад, `1.0.0` → `1.0.1` або `1.1.0`).
- **Автоматичні дії:**
  1. Оновлення поля `version` у `pyproject.toml`.
  2. Автоматична генерація та оновлення секцій у `CHANGELOG.md` за стандартом Keep a Changelog.
  3. Створення анотованого git-тегу `v1.1.0`.
- **Посилання на успішний запуск:** Реліз Лабораторної роботи 8 зафіксовано у журналі змін `CHANGELOG.md` та git-тезі `v1.1.0`.
