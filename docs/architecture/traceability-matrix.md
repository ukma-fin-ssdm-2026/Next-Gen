# Матриця простежуваності: Вимоги → Архітектура

| Вимога   | Опис                                              | Архітектурний компонент / Сутність БД | Метод верифікації |
|----------|----------------------------------------------------|----------------------------------------|---------------------|
| FR-001   | Вхід через Microsoft Entra ID НаУКМА | Microsoft Entra ID, Auth Service, Data Access Layer (ORM), User | Інтеграційні OIDC-тести та unit-тести claims/domain |
| FR-002   | Створення оголошення (UC-001)                       | Listing Service, Data Access Layer (ORM), Listing, ListingImage, Category, Сховище зображень | Інтеграційний тест створення запису |
| FR-003   | Редагування оголошення                              | Listing Service, Data Access Layer (ORM), Listing | Unit-тест перевірки власника (seller_id) |
| FR-004   | Зняття оголошення з публікації                      | Listing Service, Data Access Layer (ORM), Listing (status: WITHDRAWN) | Unit-тест зміни статусу |
| FR-005   | Історія власних оголошень                           | Listing Service, Data Access Layer (ORM), Listing (seller_id) | Інтеграційний тест вибірки за user_id |
| FR-006   | Перегляд каталогу                                   | React SPA, API Router, Listing Service, Data Access Layer (ORM), Listing | E2E-тест рендеру списку |
| FR-007   | Текстовий пошук                                     | Listing Service, Data Access Layer (ORM), Listing.title/description | Unit-тест пошукового запиту |
| FR-008   | Фільтрація та сортування                            | Listing Service, Data Access Layer (ORM), Listing, Category | Unit-тест фільтра за категорією/ціною |
| FR-009   | Обране                                              | Listing Service, Data Access Layer (ORM), Favorite | Інтеграційний тест додавання/видалення |
| FR-010   | Контакти продавця                                   | Listing Service, Auth Service, Data Access Layer (ORM), Listing.contact | Unit-тест перевірки авторизації |
| FR-014   | Профіль користувача (ім'я, аватарка, контакти)      | Profile Service, Auth Service, Image Storage, User | TP-024, TP-025 |
| FR-011   | Модерація оголошень                                 | Moderation Service, Data Access Layer (ORM), ModerationAction, Listing.status | Unit-тест зміни статусу адміном |
| FR-012   | Керування категоріями                               | Moderation Service, Data Access Layer (ORM), Category | Unit-тест CRUD категорій |
| FR-013   | Блокування користувачів                             | User Moderation Service, Auth Service, Data Access Layer (ORM), User.is_blocked, ModerationAction | TP-026, TP-027 |
| FR-015   | Пропозиції нових категорій і їх модерація           | Category Suggestion Service, Listing Service, Category Service, Data Access Layer, CategorySuggestion, Listing.suggested_category_id, ModerationAction | TP-026, TP-027, TP-028 |
| FR-016   | Скарги на оголошення                                | React SPA, Complaint Service, Activity Log Service, Data Access Layer (ORM), Complaint, Listing, ActivityEvent | TP-031, TP-034 |
| FR-017   | Звернення до адміністрації                          | React SPA, Feedback Service, Activity Log Service, Data Access Layer (ORM), FeedbackMessage, ActivityEvent | TP-032, TP-034 |
| FR-018   | Окремі журнали дій користувачів та адміністраторів  | React SPA, Activity Log Service, Moderation Service, Data Access Layer (ORM), ActivityEvent, ModerationAction | TP-033, TP-034 |
| FR-019   | Власна оцінка й агрегат продавця | API Router, Seller Review Service, PostgreSQL, SellerReview, ActivityEvent, ListingDetailPublicResponse | TP-039, TP-040, TP-042, TP-043, TP-044 |
| FR-020   | Модерація оцінок і статистика за автором | API Router, Auth Service, Seller Review Service, SellerReview, ActivityEvent | TP-041, TP-043 |
| FR-021   | Початок розмови чату зі сторінки оголошення | API Router (`conversations`), Conversation Service, Activity Log Service, Data Access Layer (ORM), PostgreSQL (`Conversation`, `Message`, `ActivityEvent`) | TP-050, TP-051, TP-052, TP-053, TP-054, TP-055 |
| FR-022   | Обмін повідомленнями, курсори, непрочитані та безпечна картка оголошення | API Router (`conversations`), Conversation Service, Data Access Layer (ORM), PostgreSQL (`Conversation`, `Message`, `Listing`) | TP-050, TP-051, TP-052, TP-053, TP-054, TP-055 |
| PERF-001 | Браузерний p95 ≤ 300 мс до відображення 20 карток при 50 одночасних відкриттях | Chromium, мережа, React SPA, API Router, Listing Service, PostgreSQL | TP-N03 (staging) |
| PERF-002 | Своєчасність polling чату ≤10 с (опитування кожні 5 с; p95 ≤300 мс при 50 користувачах) | API Router (`conversations`), Conversation Service, Data Access Layer (ORM), PostgreSQL (`Message`) | TP-056 |
| PERF-003 | Медіана p95 трьох раундів ≤ 300 мс, 50 одночасних запитів на раунд і 0% помилок | API Router, Listing Service, in-memory репозиторій | TP-N02 |
| REL-001  | Відновлення без втрати даних, RTO ≤5хв              | Data Access Layer (ORM), PostgreSQL Database | Хаос-експеримент (збій сервера) |
| SEC-001  | Лише tenant НаУКМА та @ukma.edu.ua | Microsoft Entra ID, Auth Service, User.tenant_id/entra_object_id/email | Негативні тести tenant, issuer, audience, expiry, state/nonce і domain |
| SEC-002  | Приховування контактів від неавторизованих          | API Router, Listing Service, Auth Service, Data Access Layer (ORM), Listing.contact | Unit-тест доступу без токена |
| SEC-003  | Конфіденційність розмов, захист від IDOR (`404` для неучасників) та відсутність контактів і `no-store` | API Router (`conversations`), Auth Service (`require_current_user`), Conversation Service, Data Access Layer (ORM) | TP-053, TP-055 |

## Сценарії атрибутів якості

### QAS-PERF-001 — Сторінка каталогу (PERF-001, FR-006)
- Метод перевірки: 50 одночасних навігацій на `/listings` у Chromium на staging із PostgreSQL і 500 активними оголошеннями (TP-N03).
- Критерій успіху: браузерний p95 від навігації до відображення 20 карток ≤ 300 мс і 0% невдалих навігацій.

### QAS-PERF-003 — API каталогу (PERF-003, FR-006)
- Метод перевірки: три раунди по 50 одночасних викликів `GET /api/v1/listings?limit=20` через ASGI, 500 активних оголошень in-memory (TP-N02).
- Критерій успіху: медіана p95 трьох раундів ≤ 300 мс, усі відповіді HTTP 200 із 20 оголошеннями.

### QAS-REL-001 — Збереження оголошень при збої (REL-001, FR-002)
- Вимога: при критичному збої сервера опубліковані оголошення не втрачаються (RPO = 0), робота відновлюється за ≤ 5 хв (RTO).
- Метод перевірки: хаос-експеримент на ланцюжку API Router → Listing Service → Data Access Layer (ORM) → PostgreSQL. Гіпотеза: після збою жодне створене оголошення не зникає.
- Критерій успіху: після рестарту всі підтверджені оголошення є в БД, сервіс відновлюється за ≤ 5 хв.

### QAS-PERF-002 — Своєчасність polling чату (PERF-002, FR-022)
- Вимога: за опитування відкритої розмови кожні 5 с нове повідомлення доставляється співрозмовнику за ≤ 10 с, а конкурентне опитування 50 користувачами має серверну затримку `p95 ≤ 300 мс`.
- Метод перевірки: інтеграційний тест polling і конкурентний ASGI-бенчмарк (`tests/test_conversations_api.py`, `TP-056`) на ланцюжку API Router (`conversations`) → Auth Service → Conversation Service → Repository.
- Критерій успіху: 0% помилок, доставка на наступному 5-секундному циклі опитування (`≤ 10 с`), серверний `p95 ≤ 300 мс`, `Cache-Control: no-store`.

---
> ### Нотатка «Використання ШІ»
> - **Інструменти:** Claude, Gemini.
> - **Етап:** Побудова матриці простежуваності вимог до архітектурних компонентів та сценаріїв атрибутів якості, включаючи FR-014 і FR-015.
> - **Що згенеровано:** Чорновий варіант прив'язок FR/NFR до компонентів на основі high-level-design.md, components.puml, deployment.puml та data-model.md; формулювання методів верифікації; чернетка двох сценаріїв атрибутів якості за довідником курсу (цифри з requirements.md).
> - **Що перевірено / відкинуто вручну:** Прив'язки і сценарії перевірено і підтверджено мною; звірено назви компонентів з components.puml та deployment.puml; підтверджено з Architecture Lead, що PERF-001 стосується всього ланцюжка обробки запиту; Data Access Layer додано в усі рядки після зауваження викладача; сценарії звірено з довідником про сценарії атрибутів якості.
> - **Доповнення (Артем Солодкий, 02.11.2026):** OpenAI Codex допоміг додати архітектурну простежуваність FR-016–FR-018 після проміжного оцінювання. Компоненти, сутності та тест-кейси вручну звірено з `requirements.md`, `rtm.md`, сервісами, SQLAlchemy-моделями й тест-планом.
> - **Доповнення (Євгеній Остапенко, ADR-005 / чат API):** ШІ-асистент допоміг додати архітектурну простежуваність `FR-021`, `FR-022`, `PERF-002`, `SEC-003` та сценарій якості `QAS-PERF-002`. Звірено з `src/api/routers/conversations.py`, `tests/test_conversations.py` і `tests/test_conversations_api.py`.
> - **Доповнення (Євгеній Остапенко, PERF-001 / PERF-003):** Codex (OpenAI) допоміг прив'язати браузерний сценарій і сценарій API до відповідних компонентів. Сценарії звірено з вимогами та тест-планом.
