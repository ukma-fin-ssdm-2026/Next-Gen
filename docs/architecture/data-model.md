# Модель даних

## Огляд

Baraholka NaUKMA використовує реляційну модель даних, представлену у вигляді Entity-Relationship (ER) моделі.

Модель підтримує такі ключові функції маркетплейсу:

1. Прив'язка локального профілю до Microsoft Entra ID НаУКМА.
2. Створення, редагування та зняття з публікації оголошень із фотографіями.
3. Перегляд і фільтрація оголошень.
4. Пошук оголошень за текстовим запитом.
5. Додавання оголошень до обраного.
6. Перегляд контактів продавця.
7. Модерація оголошень, категорій, пропозицій нових категорій і користувачів.

ER-діаграма зберігається у файлі:

`docs/architecture/uml/data-model.puml`

---

## Сутності

### User

Представляє зареєстрованого користувача маркетплейсу.

| Атрибут | Тип | Обмеження | Опис |
|---|---|---|---|
| `user_id` | UUID | PK | Унікальний ідентифікатор користувача |
| `tenant_id` | UUID | Required | Microsoft Entra tenant; для цієї системи — tenant НаУКМА |
| `entra_object_id` | UUID | Required | Стабільний object ID (`oid`) користувача в Microsoft Entra ID |
| `email` | string | UNIQUE, Required, Personal Data | Підтверджена адреса `@ukma.edu.ua`, оновлювана за перевіреною Entra-ідентичністю |
| `display_name` | string | Personal Data | Ім'я, яке відображається у маркетплейсі |
| `role` | enum | Required | Роль `USER` або `ADMIN` |
| `is_blocked` | boolean | Required, default `false` | Ознака блокування облікового запису |
| `display_name_customized` | boolean | Required, default `false` | Ознака, що ім'я змінив сам користувач; повторний вхід тоді не перезаписує його іменем з Entra (`FR-014`) |
| `avatar_url` | string | Nullable | Публічний URL аватарки (`/uploads/{key}.webp`); файл зберігається в сховищі зображень як зображення з псевдо-ідентифікатором `user_id`, тому не підпадає під TTL staged-завантажень (`FR-014`) |
| `contact` | string | Nullable, ≤ 300 символів, Personal Data | Контакти за замовчуванням (формат як у `Listing.contact`: основний контакт, `Тел.: …`, `Локація: …`); підставляються клієнтом у форму нового оголошення; публічно не віддаються (`FR-014`) |
| `created_at` | datetime | Required | Час створення облікового запису |

Унікальність зовнішньої ідентичності забезпечує обмеження `UNIQUE (tenant_id, entra_object_id)`. Система не приймає і не зберігає паролі Microsoft.

---

### Category

Представляє категорію, яка використовується для групування оголошень.

| Атрибут | Тип | Обмеження | Опис |
|---|---|---|---|
| `category_id` | UUID | PK | Унікальний ідентифікатор категорії |
| `name` | string | UNIQUE, Required | Назва категорії |
| `is_active` | boolean | Required, default `true` | Чи доступна категорія для нових оголошень |

Прикладами категорій можуть бути книги, електроніка, одяг, послуги та інші типи оголошень.

---

### CategorySuggestion

Представляє пропозицію нової категорії від продавця (`FR-015` / `US-010`).

| Атрибут | Тип | Обмеження | Опис |
|---|---|---|---|
| `suggestion_id` | UUID | PK | Унікальний ідентифікатор пропозиції категорії |
| `name` | string | Required, 2–40 символів | Запропонована назва категорії (після обрізання пробілів, без керівних символів) |
| `proposer_id` | UUID | FK → `User.user_id`, Required | Користувач, який запропонував категорію |
| `status` | enum | Required | Статус розгляду: `PENDING`, `APPROVED`, `REJECTED` |
| `reason` | text | Nullable | Причина відхилення (заповнюється для `REJECTED`, 5–500 символів) |
| `category_id` | UUID | FK → `Category.category_id`, Nullable | Створена категорія (заповнюється після схвалення `APPROVED`) |
| `reviewed_by` | UUID | FK → `User.user_id`, Nullable | Адміністратор, який розглянув пропозицію |
| `created_at` | datetime | Required | Час створення пропозиції (UTC) |
| `reviewed_at` | datetime | Nullable | Час розгляду пропозиції адміністратором (UTC) |

---

### Listing

Представляє оголошення, створене користувачем маркетплейсу.

| Атрибут | Тип | Обмеження | Опис |
|---|---|---|---|
| `listing_id` | UUID | PK | Унікальний ідентифікатор оголошення |
| `seller_id` | UUID | FK → `User.user_id` | Користувач, який створив оголошення |
| `category_id` | UUID | FK → `Category.category_id` | Категорія оголошення (для оголошень із нерозглянутою пропозицією категорії — категорія «Інше») |
| `suggested_category_id` | UUID | FK → `CategorySuggestion.suggestion_id`, Nullable | Прив'язана пропозиція нової категорії (`FR-015`) |
| `title` | string | Required | Заголовок оголошення |
| `description` | text | Required | Опис оголошення |
| `price` | decimal | Required | Ціна |
| `contact` | string | Required, Personal Data | Email або Telegram продавця, видимий лише автентифікованим користувачам. Веб-клієнт може дописувати в цей самий рядок необов'язкові телефон і локацію окремими рядками (`Тел.: ...`, `Локація: ...`, див. [frontend.md](../frontend/frontend.md#контакт-телефон-і-локація)); вони мають ту саму класифікацію Personal Data |
| `condition` | enum | Required | Стан товару |
| `status` | enum | Required | Поточний статус оголошення |
| `created_at` | datetime | Required | Час створення оголошення |
| `updated_at` | datetime | Required | Час останнього оновлення |

Можливі значення `condition`:

- `NEW`
- `LIKE_NEW`
- `GOOD`
- `USED`

Можливі значення `status`:

- `ACTIVE`
- `WITHDRAWN`
- `REMOVED_BY_MODERATOR`

---

### ListingImage

Представляє зображення, прикріплене до оголошення.

| Атрибут | Тип | Обмеження | Опис |
|---|---|---|---|
| `image_id` | UUID | PK | Унікальний ідентифікатор зображення |
| `listing_id` | UUID | FK → `Listing.listing_id` | Оголошення, до якого належить зображення |
| `image_url` | string | Required | Посилання або шлях до збереженого зображення |
| `display_order` | integer | Required | Порядок відображення зображень |

Винесення зображень в окрему сутність дозволяє одному оголошенню мати кілька зображень без фіксованого обмеження на їх кількість у сутності `Listing`.

---

### ModerationAction

Представляє зафіксовану дію адміністратора над оголошенням, користувачем або пропозицією категорії. Окрема сутність зберігає історію рішень і забезпечує аудит модерації (`FR-011`, `FR-013`, `FR-015`).

| Атрибут | Тип | Обмеження | Опис |
|---|---|---|---|
| `moderation_action_id` | UUID | PK | Унікальний ідентифікатор дії |
| `moderator_id` | UUID | FK → `User.user_id`, Required | Адміністратор, який виконав дію |
| `listing_id` | UUID | FK → `Listing.listing_id`, Nullable | Оголошення, якого стосується дія |
| `target_user_id` | UUID | FK → `User.user_id`, Nullable | Користувач, якого блокують або розблоковують |
| `suggestion_id` | UUID | FK → `CategorySuggestion.suggestion_id`, Nullable | Пропозиція категорії, яку схвалюють або відхиляють (`FR-015`) |
| `action_type` | enum | Required | У коді реалізовано `WITHDRAW_LISTING`, `BLOCK_USER`, `UNBLOCK_USER`, `APPROVE_CATEGORY`, `REJECT_CATEGORY` |
| `reason` | text | Required | Причина модераційного рішення (5–500 символів) |
| `created_at` | datetime | Required | Час виконання дії |

Рівно одне з полів `listing_id`, `target_user_id` і `suggestion_id` має бути заповнене залежно від типу дії (`WITHDRAW_LISTING` → `listing_id`; `BLOCK_USER` / `UNBLOCK_USER` → `target_user_id`; `APPROVE_CATEGORY` / `REJECT_CATEGORY` → `suggestion_id`). Це обмеження перевіряється на рівні домену і БД (`CHECK`).

Зміна стану цільової сутності та створення `ModerationAction` виконуються в одній атомарній операції, а записи журналу не видаляються.

---

### Favorite

Представляє оголошення, яке користувач додав до обраного.

| Атрибут | Тип | Обмеження | Опис |
|---|---|---|---|
| `user_id` | UUID | PK, FK → `User.user_id` | Користувач, який додав оголошення до обраного |
| `listing_id` | UUID | PK, FK → `Listing.listing_id` | Обране оголошення |
| `created_at` | datetime | Required | Час додавання оголошення до обраного |

Складений первинний ключ:

`(user_id, listing_id)`

не дозволяє одному користувачу додати те саме оголошення до обраного більше одного разу.

---

## Зв'язки та кардинальності

### User — Listing

`User 1 → 0..* Listing`

Один користувач може не мати жодного оголошення або створити багато оголошень.

Кожне оголошення належить рівно одному користувачу.

---

### User — CategorySuggestion

`User (proposer) 1 → 0..* CategorySuggestion` та `User (reviewer) 0..1 ← 0..* CategorySuggestion`

Один продавець може подати нуль або декілька пропозицій категорій (не більше 3 одночасно у статусі `PENDING`). Адміністратор розглядає пропозицію.

---

### CategorySuggestion — Listing

`CategorySuggestion 0..1 ← 0..* Listing`

Одне оголошення може бути створене з необов'язковим посиланням `suggested_category_id` на пропозицію нової категорії. До розгляду оголошення зберігається з `category_id` категорії «Інше», а при схваленні автоматично переходить до новоствореної `Category`.

---

### User (модератор) — ModerationAction

`User 1 → 0..* ModerationAction`

Один адміністратор може виконати нуль або багато дій. Кожна дія належить рівно одному адміністратору.

---

### User (ціль) — ModerationAction

`User 0..1 ← 0..* ModerationAction`

Один користувач може бути ціллю нуля або багатьох дій блокування чи розблокування. Кожна дія може стосуватися не більш ніж одного користувача; для дій над оголошеннями чи пропозиціями категорій `target_user_id` не заповнюється.

---

### Listing — ModerationAction

`Listing 0..1 ← 0..* ModerationAction`

Одне оголошення може мати нуль або багато записів модерації. Кожна дія може стосуватися не більш ніж одного оголошення.

---

### CategorySuggestion — ModerationAction

`CategorySuggestion 0..1 ← 0..* ModerationAction`

Кожне рішення адміністратора про схвалення (`APPROVE_CATEGORY`) або відхилення (`REJECT_CATEGORY`) пропозиції категорії створює запис у `ModerationAction` із заповненим `suggestion_id`.

---

### Category — Listing

`Category 1 → 0..* Listing`

Одна категорія може містити нуль або багато оголошень.

Кожне оголошення належить рівно одній категорії.

---

### Listing — ListingImage

`Listing 1 → 1..* ListingImage`

Опубліковане оголошення має містити щонайменше одне зображення.

Кожне зображення належить рівно одному оголошенню.

---

### User — Favorite

`User 1 → 0..* Favorite`

Один користувач може мати нуль або багато записів в обраному.

Кожен запис `Favorite` належить рівно одному користувачу.

---

### Listing — Favorite

`Listing 1 → 0..* Favorite`

Одне оголошення може бути додане до обраного нулем або багатьма користувачами.

Кожен запис `Favorite` посилається рівно на одне оголошення.

Таким чином, сутність `Favorite` реалізує зв'язок many-to-many між `User` та `Listing`.

---

## Персональні та чутливі дані

Додаткового захисту потребують такі атрибути:

| Сутність | Атрибут | Класифікація |
|---|---|---|
| `User` | `email` | Personal Data |
| `User` | `display_name` | Personal Data |
| `User` | `contact` | Personal Data |
| `User` | `avatar_url` | Personal Data (зображення користувача) |
| `User` | `tenant_id`, `entra_object_id` | Identity Data |
| `Listing` | `contact` | Personal Data |

Ці поля окремо позначаються на ER-діаграмі, оскільки вони є важливими вхідними даними для подальшого аналізу загроз.

Зокрема:

- Entra-ідентифікатори не повинні бути доступними неавторизованим користувачам;
- паролі не зберігаються в Baraholka у жодному вигляді;
- персональні дані користувачів повинні бути доступними лише там, де це потрібно для роботи системи.

---

## Покриття ключових функцій

| Функція маркетплейсу | Сутності |
|---|---|
| Зв'язок локального профілю з Microsoft Entra ID | `User` |
| Створення, редагування і зняття оголошень із фотографіями | `User`, `Listing`, `Category`, `ListingImage` |
| Пропозиції нових категорій і перехід оголошень після схвалення | `CategorySuggestion`, `Listing.suggested_category_id`, `Category`, `ModerationAction` |
| Перегляд і фільтрація | `Listing`, `Category`, `ListingImage`, `User` |
| Текстовий пошук | `Listing.title`, `Listing.description` |
| Додавання до обраного | `User`, `Favorite`, `Listing` |
| Перегляд контактів продавця | `Listing.contact` |
| Профіль користувача: ім'я, аватарка, контакти за замовчуванням | `User.display_name`, `User.display_name_customized`, `User.avatar_url`, `User.contact` |
| Модерація оголошень, категорій, пропозицій і користувачів | `User.role`, `User.is_blocked`, `Category.is_active`, `CategorySuggestion`, `Listing.status`, `ModerationAction` |

Таким чином, модель покриває дані, необхідні для основних функцій Baraholka NaUKMA, без додавання сутностей, які не потрібні в поточному обсязі проєкту.

---

### Нотатка «Використання ШІ»

> - **Інструменти:** ChatGPT / Codex, Gemini.
> - **Етап:** Підготовка первинної чернетки реляційної моделі даних, ER-діаграми та розширення моделлю `CategorySuggestion` (FR-015).
> - **Що згенеровано:** Чернетка сутностей `User`, `Category`, `CategorySuggestion`, `Listing`, `ListingImage`, `Favorite`, `ModerationAction`, їхніх атрибутів, ключів, зв'язків і кардинальностей.
> - **Що перевірено / відкинуто вручну:** Перевірено відповідність сутностей ключовим функціям міні-ТЗ, наявність PK/FK, коректність кардинальностей, аудит блокувань за FR-013 та пропозицій категорій за FR-015 і позначення персональних та чутливих даних; відкинуто сутності, які не потрібні для обраного обсягу.
> - **Доповнення (Артем Солодкий, FR-001, FR-013, FR-014):** Claude (Anthropic) допоміг сформулювати зміни: Додано атрибути `User.display_name_customized`, `avatar_url`, `contact` і рядок покриття для профілю. Звірено вручну з кодом, тестами та згенерованим OpenAPI; повний набір тестів, black, flake8 і перевірку простежуваності запущено.
