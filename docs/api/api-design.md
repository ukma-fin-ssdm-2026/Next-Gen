# Документація проєктування API (API Design)

## 1. Ресурсна модель та поля ресурсу

Основний ресурс у нашій системі — це **Оголошення (Listings)**.

- **URI-корінь:** `/api/v1/listings`

### Поля ресурсу Оголошення (Resource Fields)

| Назва поля | Тип даних | Обмеження / Валідація | Опис | Видимість / Схеми |
|---|---|---|---|---|
| `id` | `UUID` | Auto UUID v4 | Унікальний ідентифікатор оголошення | Всі відповіді (`ListingPublicResponse`, `ListingResponse`) |
| `title` | `string` | min: 3, max: 100 | Назва оголошення | Всі схеми (`ListingBase`, `Create`, `Update`, `Response`) |
| `description` | `string` | min: 0, max: 2000; у `ListingCreate` поле можна не передавати, порожнє значення дозволене | Необов’язковий опис товару | Всі схеми (`ListingBase`, `Create`, `Update`, `Response`) |
| `price` | `number` (float) | ge: 0 (негативні значення заборонені) | Ціна в гривнях | Всі схеми (`ListingBase`, `Create`, `Update`, `Response`) |
| `category_id` | `UUID` | Valid UUID (необов'язковий у `ListingCreate`, якщо передано `suggested_category_name`) | Унікальний ідентифікатор категорії | Всі схеми (`ListingBase`, `Create`, `Update`, `Response`) |
| `suggested_category_name` | `string` | Optional, min: 2, max: 40 після `strip`, без керівних символів | Пропозиція нової категорії (`FR-015`). Оголошення публікується в категорії «Інше» до рішення адміністратора | **Приватне поле:** `ListingCreate`, `ListingResponse`. **Відсутнє в `ListingPublicResponse`** |
| `condition` | `string` | Enum: `NEW`, `LIKE_NEW`, `GOOD`, `USED` | Стан товару в оголошенні (`FR-002`) | Всі схеми (`ListingBase`, `Create`, `Update`, `Response`) |
| `image_urls` / `images` | `array` | min: 1, max: 10, валідні серверні ключі або `/uploads/` | Фотографії оголошення з thumbnail та порядком відображення (`FR-002`, `TM-03`). Довільні зовнішні URL відхиляються | `image_urls` у `ListingCreate`/`ListingUpdate`; `images` (`ListingImageResponse`) у відповідях |
| `contact` | `string` | Required on create | Контактні дані продавця (Telegram / Email). Це один рядок до 200 символів: веб-клієнт за домовленістю додає в нього необов'язкові рядки `Тел.: ...` і `Локація: ...` (див. [frontend.md](../frontend/frontend.md#контакт-телефон-і-локація)); окремих полів телефону й локації в API немає | **Приватне поле:** `ListingCreate`, `ListingUpdate`, `ListingResponse`. **Відсутнє в `ListingPublicResponse`** |
| `user_id` | `UUID` | Auto UUID v4 | Унікальний ідентифікатор автора | Всі відповіді (`ListingPublicResponse`, `ListingResponse`) |
| `status` | `string` | Enum: `ACTIVE`, `WITHDRAWN`, `REMOVED_BY_MODERATOR`, `RESERVED`, `SOLD` | Поточний стан оголошення | Всі відповіді (`ListingPublicResponse`, `ListingResponse`) |
| `created_at` | `string` (datetime) | ISO 8601 | Дата та час створення оголошення | Всі відповіді (`ListingPublicResponse`, `ListingResponse`) |
| `updated_at` | `string` (datetime) | ISO 8601 | Дата та час останнього оновлення | Всі відповіді (`ListingPublicResponse`, `ListingResponse`) |

---

## 2. Ключові проєктні рішення (Design Decisions)

### 2.1 Code-First підхід та автогенерація документації
- **Рішення:** Обрано розробку на FastAPI з Pydantic v2 замість ручного складання OpenAPI YAML файлу.
- **Обґрунтування:** Код є єдиним джерелом істини (Single Source of Truth). Всі правила валідації, опис полів `Field(...)` та статус-коди прописуються в Python-коді. Скрипт `scripts/generate_openapi.py` зчитує анотації додатка і генерує актуальний `openapi-generated.yaml` без людського фактора.

### 2.2 Захист персональних даних та публічна схема (SEC-002, QA-SEC-01)
- **Рішення:** Розділення схем відповідей на `ListingPublicResponse` та `ListingResponse`.
- **Обґрунтування:** Для захисту конфіденційності контактні дані продавця (`contact`) та службова назва запропонованої категорії (`suggested_category_name`) виключені з публічної схеми `ListingPublicResponse`, яка використовується для загального списку оголошень (`GET /api/v1/listings`), перегляду по ID (`GET /api/v1/listings/{id}`), історії оголошень продавця (`GET /api/v1/listings/my`) та відповіді часткового оновлення (`PATCH /api/v1/listings/{id}`). Повне представлення `ListingResponse` з контактами та `suggested_category_name` повертається лише власнику при створенні (`POST /api/v1/listings`).

### 2.3 Пагінація, фільтрація та сортування
- **Рішення:** Підтримка query-параметрів `skip`, `limit`, `category_id`, `q`, `min_price`, `max_price` та `sort` в ендпоінті `GET /api/v1/listings`.
- **Обґрунтування:**
  - `skip` (default 0, ge=0) — параметр зсуву для пагінації.
  - `limit` (default 10, ge=1, le=100) — обмеження розміру сторінки для запобігання перевантаженню сервера.
  - `category_id` (Optional[UUID]) — точкова фільтрація за категорією товару.
  - `q` (Optional[str]) — текстовий пошук за назвою та описом (FR-007).
  - `min_price` і `max_price` (Optional[float], ge=0) — межі ціни.
  - `sort` (`newest` або `oldest`, default `newest`) — порядок за датою публікації (FR-008).

### 2.4 Microsoft Entra ID та ідентифікація автора змін (SEC-001, TM-02)
- **Рішення:** `user_id` завжди призначається на сервері із `CurrentUser` (`require_current_user`). Роутер `/api/v1/auth` реалізує Microsoft Entra ID Authorization Code Flow через MSAL, створює непрозору server-side сесію та повторно читає локального `User` для кожного захищеного запиту (`POST /api/v1/listings`, `PATCH /api/v1/listings/{id}`, `DELETE /api/v1/listings/{id}`, `GET /api/v1/listings/my`, `POST /api/v1/listings/images`, `POST /api/v1/category-suggestions`). Клієнтські заголовки (`X-Actor-Id`) або поля `user_id`/`proposer_id` ніколи не довіряються.
- **Обґрунтування:** Microsoft-токени та `client_secret` не потрапляють у React/browser. Cookie містить лише випадковий ID сесії з `HttpOnly` та `SameSite=Lax`; у production додається `Secure`.

### 2.5 Семантика часткового оновлення (PATCH замість PUT)
- **Рішення:** Використання HTTP методу `PATCH` замість `PUT` для модифікації оголошення.
- **Обґрунтування:** Модель `ListingUpdate` дозволяє передавати лише ті поля, які змінюються. Використання `PATCH` відповідає специфікації REST і унеможливлює ненавмисне скидання відсутніх у запиті полів у `null`. При спробі передати `null` у обов'язкове поле сервер повертає контрольовану помилку `422 Unprocessable Entity` замість `500 Internal Server Error`.

### 2.6 Обране (FR-009)
- **Рішення:** Обране — окремий ресурс `/api/v1/favorites`, прив'язаний до `CurrentUser` із серверної сесії (`require_current_user`, cookie `baraholka_session`). `X-Actor-Id`, а також `user_id` у path, query чи body не враховуються: без валідної сесії — 401, заблокований користувач — 403. `POST /api/v1/favorites/{listing_id}` ідемпотентний: повторне додавання повертає наявний запис без дубліката.
- **Обґрунтування:** Обране одного користувача недоступне іншим (TM-02). Список повертає `ListingPublicResponse`, тож контакти продавців через обране не розкриваються (SEC-002). Додати можна лише активне оголошення (404 для знятого чи неіснуючого), а зняття оголошення власником одразу прибирає його з обраного всіх користувачів.

### 2.7 Категорії оголошень та пропозиції нових категорій (FR-012, FR-015)
- **Рішення:** Ресурс `/api/v1/categories` надає публічний перегляд активних категорій для фільтрації каталогу (`GET /api/v1/categories`, `GET /api/v1/categories/{id}`) та захищені адміністративні маршрути (`POST /api/v1/categories`, `PATCH /api/v1/categories/{id}`). Ресурс `/api/v1/category-suggestions` (а також поле `suggested_category_name` у `POST /api/v1/listings`) дозволяє автентифікованому продавцеві запропонувати нову категорію (2–40 символів після `strip`, без керівних символів).
- **Модерація та квоти (`FR-015` / `US-010`):**
  - До розгляду адміністратором оголошення публікується в категорії «Інше» (`55555555-5555-5555-5555-555555555555`) зі збереженням зв'язку `suggested_category_id`.
  - Пропозиція не може дублювати існуючу активну чи деактивовану категорію або іншу `PENDING`-пропозицію (повертається `409 Conflict` із посиланням на існуючу категорію).
  - Діє квота не більше 3 пропозицій у статусі `PENDING` на одного користувача; перевищення повертає `429 Too Many Requests`.
  - Схвалення (`POST /api/v1/category-suggestions/{id}/approve`, опційне тіло `{"name": "..."}`) атомарно створює активну категорію, переносить усі активні оголошення цієї пропозиції з категорії «Інше» до нової категорії (не чіпаючи `WITHDRAWN` і змінені вручну), переводить пропозицію в `APPROVED` і записує `ModerationAction` (`APPROVE_CATEGORY`).
  - Відхилення (`POST /api/v1/category-suggestions/{id}/reject`, обов'язкова причина 5–500 символів) залишає оголошення в «Інше», очищує `suggested_category_id`, переводить пропозицію в `REJECTED` і записує `ModerationAction` (`REJECT_CATEGORY`). Повторний розгляд вже обробленої пропозиції повертає `409 Conflict`.

### 2.8 Контакт продавця (FR-010, SEC-002)
- **Рішення:** Контакт продавця віддається лише окремим ресурсом `GET /api/v1/listings/{listing_id}/contact` і лише для `CurrentUser` із серверної сесії (`require_current_user`). Публічні схеми каталогу, деталей і обраного (`ListingPublicResponse`) поля `contact` не мають. Відповідь має `Cache-Control: no-store`.
- **Обґрунтування:** Окремий endpoint робить кожне розкриття контакту явною дією автентифікованого користувача і не змішує його з публічними відповідями (SEC-002, TM-05). Без сесії — 401, заблокований користувач — 403, неіснуюче або зняте оголошення — 404.

### 2.9 Адміністративна модерація (FR-011)
- **Рішення:** Окремий маршрут `POST /api/v1/admin/listings/{listing_id}/withdraw` з тілом `{"reason": "..."}`; власницький `DELETE /api/v1/listings/{id}` не змінюється. Роль `ADMIN` перевіряється лише з `CurrentUser`, який `require_current_user` щоразу перечитує з локального запису користувача. Причина обов'язкова: 5–500 символів, інакше 422. Успіх — 201 із записом `ModerationAction`.
- **Обґрунтування:** Модерація — окрема дія з іншим актором і обов'язковим аудитом, тому має власний ресурс, а не прапорець у власницькому `DELETE`. Оголошення не видаляється фізично, а переходить у `WITHDRAWN`, тож історія і причина зберігаються.

### 2.10 Завантаження, нормалізація та зберігання фотографій (FR-002, TM-03, TM-08)
- **Контракт:** Окремий маршрут `POST /api/v1/listings/images` (`multipart/form-data`, поле `files`, від 1 до 10 файлів до 10 МБ кожен). Захищено перевіркою валідної серверної сесії (`require_current_user`).
- **Безпека та нормалізація:**
  - Дозволені формати: JPEG, PNG, WebP, HEIC та HEIF. Декодування HEIC/HEIF здійснюється через бібліотеку `pillow-heif`, а результат нормалізується у формат WebP.
  - Валідація здійснюється виключно за фактичним декодуванням байтів вмісту, а не за розширенням файла або заголовком `Content-Type`.
  - Відхиляються SVG, анімовані зображення (GIF, APNG, анімований WebP), відеофайли / Live Photo (`.mov`, `.mp4`), RAW/DNG та невідомі формати (HTTP 422).
  - Захист від decompression bomb: ліміт 25 млн пікселів і перехоплення `Image.DecompressionBombError` / `Warning`.
  - Застосовується EXIF-orientation, після чого всі метадані (EXIF, XMP, GPS, ICC-профілі) повністю видаляються.
  - Основне зображення зменшується до 1600 px по довшій стороні (без апскейлу малих зображень) та стискається у WebP з quality=80.
  - Генерується thumbnail із довшою стороною до 400 px у WebP quality=80.
  - Сервер генерує випадковий UUID v4 для кожного збереженого файла (`<uuid>.webp`, `<uuid>_thumb.webp`), ігноруючи назву та шлях, передані клієнтом (захист від path traversal і колізій).
  - Потокове читання файлів по одному без одночасного утримання всього пакета в оперативній пам'яті; атомарний відкат пакета, якщо будь-який файл невалідний або перевищує 10 МБ.
  - Захист від виснаження сховища незавершеними завантаженнями (`TM-08`): кожне staged-завантаження прив'язується до `current_user.user_id` (інший користувач не може прикріпити чужий `storage_key`), діють TTL (30 хвилин) з автоматичним очищенням незавершених файлів, квота незавершених завантажень (до 20 фото на користувача) та rate limit (до 10 запитів на хвилину на користувача).
  - При оновленні фотографій оголошення (`PATCH /api/v1/listings/{id}`) замінені й більше не використовувані файли автоматично видаляються з диска.
  - Файли зберігаються через адаптер `LocalImageStorage` (підключений у production DI за замовчуванням через `get_image_storage_dir()`) у зовнішньому Docker volume, змонтованому поза writable layer API-контейнера. Контракт `ImageStorage` абстрагований для безшовної майбутньої заміни на S3-сумісне сховище.

---

## 3. Кінцеві точки (Endpoints)

| Метод | URL | Опис | Успішний статус | Статуси помилок |
|---|---|---|---|---|
| `POST` | `/api/v1/listings/images` | Завантажити фотографії оголошення (multipart/form-data, 1..10 файлів) | 201 Created | 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity, 429 Too Many Requests |
| `GET` | `/api/v1/listings` | Отримати список оголошень (з пагінацією, фільтрацією та сортуванням) | 200 OK | 422 Unprocessable Entity |
| `GET` | `/api/v1/listings/my` | Отримати історію власних оголошень продавця (активні та зняті, `FR-005`) | 200 OK | 401 Unauthorized, 403 Forbidden, 422 |
| `POST` | `/api/v1/listings` | Створити нове оголошення (підтримує `suggested_category_name`, `FR-002`, `FR-015`) | 201 Created | 400 Bad Request, 401 Unauthorized, 403 Forbidden, 409 Conflict, 422, 429 Too Many Requests |
| `GET` | `/api/v1/listings/{id}` | Отримати деталі конкретного оголошення за ID (без контактів) | 200 OK | 404 Not Found |
| `PATCH` | `/api/v1/listings/{id}` | Частково оновити дані оголошення | 200 OK | 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 |
| `DELETE` | `/api/v1/listings/{id}` | Видалити оголошення | 204 No Content | 401 Unauthorized, 403 Forbidden, 404 Not Found |
| `GET` | `/api/v1/favorites` | Отримати власне обране (активні оголошення без контактів, `FR-009`) | 200 OK | 401 Unauthorized, 403 Forbidden (заблокований) |
| `POST` | `/api/v1/favorites/{listing_id}` | Додати активне оголошення в обране (без дублікатів) | 201 Created | 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 |
| `DELETE` | `/api/v1/favorites/{listing_id}` | Прибрати оголошення з власного обраного | 204 No Content | 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 |
| `GET` | `/api/v1/listings/{listing_id}/contact` | Отримати контакт продавця активного оголошення (лише з серверною сесією, `FR-010`) | 200 OK | 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 |
| `POST` | `/api/v1/admin/users/{user_id}/block` | Заблокувати користувача з причиною 5–500 символів; сесії відкликаються, дія записується в журнал (Адміністратор, `FR-013`) | 201 Created | 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict (себе, адміністратор, вже заблоковано), 422 |
| `POST` | `/api/v1/admin/users/{user_id}/unblock` | Розблокувати користувача з причиною (Адміністратор, `FR-013`) | 201 Created | 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict (не заблоковано), 422 |
| `POST` | `/api/v1/admin/listings/{listing_id}/withdraw` | Зняти чуже оголошення з публікації з причиною (Адміністратор, `FR-011`) | 201 Created | 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 |
| `GET` | `/api/v1/categories` | Отримати список активних категорій для фільтрації каталогу (`FR-012`) | 200 OK | - |
| `GET` | `/api/v1/categories/{id}` | Отримати дані конкретної категорії за ID (`FR-012`) | 200 OK | 404 Not Found, 422 |
| `POST` | `/api/v1/categories` | Створити нову категорію (Адміністратор, `FR-012`) | 201 Created | 401 Unauthorized, 403 Forbidden, 409 Conflict, 422 |
| `PATCH` | `/api/v1/categories/{id}` | Оновити або деактивувати категорію (Адміністратор, `FR-012`) | 200 OK | 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 |
| `POST` | `/api/v1/category-suggestions` | Створити пропозицію нової категорії (автентифікований користувач, до 3 `PENDING`, `FR-015`) | 201 Created | 401 Unauthorized, 403 Forbidden, 409 Conflict, 422, 429 Too Many Requests |
| `GET` | `/api/v1/category-suggestions?status=PENDING` | Черга пропозицій категорій з `listings_count` (Адміністратор, `FR-015`) | 200 OK | 401 Unauthorized, 403 Forbidden, 422 |
| `POST` | `/api/v1/category-suggestions/{id}/approve` | Схвалити пропозицію, створити категорію й перенести активні оголошення з «Інше» (Адміністратор, `FR-015`) | 200 OK | 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 |
| `POST` | `/api/v1/category-suggestions/{id}/reject` | Відхилити пропозицію з обов'язковою причиною 5–500 символів (Адміністратор, `FR-015`) | 200 OK | 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 |
| `GET` | `/api/v1/auth/login` | Розпочати Microsoft Entra ID Authorization Code Flow; опційний `next` зберігає внутрішній маршрут для повернення після входу | 307 Temporary Redirect | 422 Unprocessable Entity, 502 Bad Gateway, 503 Service Unavailable |
| `GET` | `/api/v1/auth/callback` | Перевірити callback та створити локальну сесію | 303 See Other | 400 Bad Request, 401 Unauthorized, 403 Forbidden |
| `GET` | `/api/v1/auth/me` | Отримати поточного користувача | 200 OK | 401 Unauthorized, 403 Forbidden |
| `PATCH` | `/api/v1/auth/me` | Змінити власне ім'я та/або контакти за замовчуванням; передані поля оновлюються, `contact: null` очищає (`FR-014`) | 200 OK | 401 Unauthorized, 403 Forbidden, 422 |
| `PUT` | `/api/v1/auth/me/avatar` | Завантажити або замінити аватарку, `multipart/form-data`, поле `file` (JPEG, PNG, WebP, HEIC/HEIF до 10 МБ; нормалізується до WebP, метадані видаляються) (`FR-014`) | 200 OK | 401 Unauthorized, 403 Forbidden, 422 |
| `DELETE` | `/api/v1/auth/me/avatar` | Видалити аватарку (`FR-014`) | 200 OK | 401 Unauthorized, 403 Forbidden |
| `GET` | `/api/v1/users/{user_id}` | Публічний профіль для автентифікованих: лише `user_id`, `display_name`, `avatar_url`; без email, ролі й контактів (`FR-014`, `SEC-002`) | 200 OK | 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 |
| `POST` | `/api/v1/auth/logout` | Завершити локальну сесію | 204 No Content | — |

---

## 4. Версіонування

- **Стратегія:** URI Версіонування.
- **Поточна версія:** `v1`.
- **Приклад URL:** `http://localhost:8000/api/v1/listings`
- **Обґрунтування:** URI версіонування найпростіше реалізувати в коді (через префікси роутерів `APIRouter(prefix="/api/v1")`) та найлегше тестувати клієнтам.

---

## 5. Обробка помилок

Помилки повертаються у стандартному форматі:

```json
{
  "detail": "Оголошення не знайдено"
}
```

У випадку помилок валідації (`422 Unprocessable Entity`), Pydantic автоматично генерує масив `detail` з детальним описом того, яке саме поле не пройшло валідацію:

```json
{
  "detail": [
    {
      "loc": ["body", "price"],
      "msg": "Input should be greater than or equal to 0",
      "type": "greater_than_equal"
    }
  ]
}
```

---
> ### Нотатка «Використання ШІ»
> - **Інструменти:** Gemini, OpenAI Codex.
> - **Етап:** Проєктування API, розширення контракту завантаження фотографій та збереження в ImageStorage (FR-002, TM-03, TM-08) і додавання пропозицій категорій та їх модерації (FR-015 / US-010).
> - **Що згенеровано:** Опис розділів 2.7 і 2.10 (завантаження та нормалізація фотографій, захист від decompression bomb, видалення метаданих, thumbnail, UUID ключі, TTL/квоти staged-завантажень, очищення при PATCH, квота 3 `PENDING`-пропозицій з відповіддю HTTP 429), оновлення таблиці полів і ендпоінтів (`/api/v1/category-suggestions`).
> - **Що перевірено / відкинуто вручну:** Опис звірено з кодом `ImageStorage`, `LocalImageStorage`, `CategorySuggestionService`, роутерами `POST /api/v1/listings/images`, `/api/v1/category-suggestions`, `/api/v1/listings` та згенерованим `openapi-generated.yaml`.
> - **Доповнення (Артем Солодкий, FR-001, FR-013, FR-014):** Claude (Anthropic) допоміг сформулювати зміни: Додано endpoints профілю (`PATCH /auth/me`, `PUT`/`DELETE /auth/me/avatar`, `GET /users/{id}`) і блокування (`POST /admin/users/{id}/block`, `/unblock`). Звірено вручну з кодом, тестами та згенерованим OpenAPI; повний набір тестів, black, flake8 і перевірку простежуваності запущено.
