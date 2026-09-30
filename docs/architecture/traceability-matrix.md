# Матриця простежуваності: Вимоги → Архітектура

| Вимога   | Опис                                              | Архітектурний компонент / Сутність БД | Метод верифікації |
|----------|----------------------------------------------------|----------------------------------------|---------------------|
| FR-001   | Вхід за університетською адресою                    | Auth Service, User                     | Unit-тест перевірки домену email |
| FR-002   | Створення оголошення (UC-001)                       | Listing Service, Data Access Layer (ORM), Listing, ListingImage, Category, Сховище зображень | Інтеграційний тест створення запису |
| FR-003   | Редагування оголошення                              | Listing Service, Listing               | Unit-тест перевірки власника (seller_id) |
| FR-004   | Зняття оголошення з публікації                      | Listing Service, Listing (status: WITHDRAWN) | Unit-тест зміни статусу |
| FR-005   | Історія власних оголошень                           | Listing Service, Listing (seller_id)   | Інтеграційний тест вибірки за user_id |
| FR-006   | Перегляд каталогу                                   | React SPA, API Router, Listing         | E2E-тест рендеру списку |
| FR-007   | Текстовий пошук                                     | Listing Service, Listing.title/description | Unit-тест пошукового запиту |
| FR-008   | Фільтрація та сортування                            | Listing Service, Listing, Category     | Unit-тест фільтра за категорією/ціною |
| FR-009   | Обране                                              | Listing Service, Favorite              | Інтеграційний тест додавання/видалення |
| FR-010   | Контакти продавця                                   | Listing Service, Auth Service, Listing.contact | Unit-тест перевірки авторизації |
| FR-011   | Модерація оголошень                                 | Moderation Service, ModerationAction, Listing.status | Unit-тест зміни статусу адміном |
| FR-012   | Керування категоріями                               | Moderation Service, Category           | Unit-тест CRUD категорій |
| FR-013   | Блокування користувачів                             | Auth Service, Moderation Service, User.is_blocked | Unit-тест блокування входу |
| PERF-001 | Час завантаження ≤300мс при 50 користувачах         | React SPA, API Router, PostgreSQL (Listing) | Навантажувальний тест |
| REL-001  | Відновлення без втрати даних, RTO ≤5хв              | PostgreSQL Database                     | Тест відновлення після збою |
| SEC-001  | Обмеження реєстрації доменом @ukma.edu.ua           | Auth Service, User.email               | Unit-тест блокування чужого домену |
| SEC-002  | Приховування контактів від неавторизованих          | Listing Service, Auth Service, Listing.contact | Unit-тест доступу без токена |

---
> ### Нотатка «Використання ШІ»
> - **Інструменти:** Claude
> - **Етап:** Побудова матриці простежуваності вимог до архітектурних компонентів.
> - **Що згенеровано:** Чорновий варіант прив'язок FR/NFR до компонентів на основі high-level-design.md, components.puml, deployment.puml та data-model.md; формулювання методів верифікації.
> - **Що перевірено / відкинуто вручну:** Прив'язки перевірено і підтверджено мною; звірено назви компонентів з components.puml та deployment.puml; підтверджено з Architecture Lead (Даньок), що PERF-001 стосується всього ланцюжка обробки запиту, а не окремого компонента; перевірено, що кожна вимога має компонент і кожен компонент використаний хоча б раз.
