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
| PERF-001 | Час завантаження ≤300мс при 50 користувачах         | React SPA, API Router, Listing Service, Data Access Layer (ORM), PostgreSQL (Listing) | Навантажувальний тест |
| REL-001  | Відновлення без втрати даних, RTO ≤5хв              | Data Access Layer (ORM), PostgreSQL Database | Хаос-експеримент (збій сервера) |
| SEC-001  | Лише tenant НаУКМА та @ukma.edu.ua | Microsoft Entra ID, Auth Service, User.tenant_id/entra_object_id/email | Негативні тести tenant, issuer, audience, expiry, state/nonce і domain |
| SEC-002  | Приховування контактів від неавторизованих          | API Router, Listing Service, Auth Service, Data Access Layer (ORM), Listing.contact | Unit-тест доступу без токена |

## Сценарії атрибутів якості

### QAS-PERF-001 — Продуктивність каталогу (PERF-001, FR-006)
- Вимога: сторінка каталогу з 20 карток завантажується за ≤ 300 мс при 50 одночасних активних користувачах.
- Метод перевірки: навантажувальний тест на ланцюжку React SPA → API Router → Listing Service → Data Access Layer (ORM) → PostgreSQL.
- Критерій успіху: виміряний час відповіді ≤ 300 мс.

### QAS-REL-001 — Збереження оголошень при збої (REL-001, FR-002)
- Вимога: при критичному збої сервера опубліковані оголошення не втрачаються (RPO = 0), робота відновлюється за ≤ 5 хв (RTO).
- Метод перевірки: хаос-експеримент на ланцюжку API Router → Listing Service → Data Access Layer (ORM) → PostgreSQL. Гіпотеза: після збою жодне створене оголошення не зникає.
- Критерій успіху: після рестарту всі підтверджені оголошення є в БД, сервіс відновлюється за ≤ 5 хв.

---
> ### Нотатка «Використання ШІ»
> - **Інструменти:** Claude
> - **Етап:** Побудова матриці простежуваності вимог до архітектурних компонентів та сценаріїв атрибутів якості.
> - **Що згенеровано:** Чорновий варіант прив'язок FR/NFR до компонентів на основі high-level-design.md, components.puml, deployment.puml та data-model.md; формулювання методів верифікації; чернетка двох сценаріїв атрибутів якості за довідником курсу (цифри з requirements.md).
> - **Що перевірено / відкинуто вручну:** Прив'язки і сценарії перевірено і підтверджено мною; звірено назви компонентів з components.puml та deployment.puml; підтверджено з Architecture Lead, що PERF-001 стосується всього ланцюжка обробки запиту; Data Access Layer додано в усі рядки після зауваження викладача; сценарії звірено з довідником про сценарії атрибутів якості.
