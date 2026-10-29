# Документація проєктування API (API Design)

## 1. Ресурсна модель та поля ресурсу

Основний ресурс у нашій системі — це **Оголошення (Listings)**.

- **URI-корінь:** `/api/v1/listings`

### Поля ресурсу Оголошення (Resource Fields)

| Назва поля | Тип даних | Обмеження / Валідація | Опис | Видимість / Схеми |
|---|---|---|---|---|
| `id` | `UUID` | Auto UUID v4 | Унікальний ідентифікатор оголошення | Всі відповіді (`ListingPublicResponse`, `ListingResponse`) |
| `title` | `string` | min: 3, max: 100 | Назва оголошення | Всі схеми (`ListingBase`, `Create`, `Update`, `Response`) |
| `description` | `string` | min: 10, max: 2000 | Детальний опис товару | Всі схеми (`ListingBase`, `Create`, `Update`, `Response`) |
| `price` | `number` (float) | ge: 0 (негативні значення заборонені) | Ціна в гривнях | Всі схеми (`ListingBase`, `Create`, `Update`, `Response`) |
| `category_id` | `UUID` | Valid UUID | Унікальний ідентифікатор категорії | Всі схеми (`ListingBase`, `Create`, `Update`, `Response`) |
| `condition` | `string` | Enum: `NEW`, `LIKE_NEW`, `GOOD`, `USED` | Стан товару в оголошенні (`FR-002`) | Всі схеми (`ListingBase`, `Create`, `Update`, `Response`) |
| `image_urls` / `images` | `array` | min: 1, max: 10, валідні `https://` або `/uploads/` | Фотографії оголошення з порядком відображення (`FR-002`) | `image_urls` у `Create`/`Update`; `images` (`ListingImageResponse`) у відповідях |
| `contact` | `string` | Required on create | Контактні дані продавця (Telegram / Email) | **Приватне поле:** `ListingCreate`, `ListingUpdate`, `ListingResponse`. **Відсутнє в `ListingPublicResponse`** |
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
- **Обґрунтування:** Для захисту конфіденційності контактні дані продавця (`contact`) виключено з публічної схеми `ListingPublicResponse`, яка використовується для загального списку оголошень (`GET /api/v1/listings`), перегляду по ID (`GET /api/v1/listings/{id}`), історії оголошень продавця (`GET /api/v1/listings/my` до появи повноцінної Entra-автентифікації) та відповіді часткового оновлення (`PATCH /api/v1/listings/{id}`). Повне представлення `ListingResponse` з контактами повертається лише при створенні (`POST /api/v1/listings`).

### 2.3 Пагінація, фільтрація та сортування
- **Рішення:** Підтримка query-параметрів `skip`, `limit`, `category_id`, `q`, `min_price`, `max_price` та `sort` в ендпоінті `GET /api/v1/listings`.
- **Обґрунтування:**
  - `skip` (default 0, ge=0) — параметр зсуву для пагінації.
  - `limit` (default 10, ge=1, le=100) — обмеження розміру сторінки для запобігання перевантаженню сервера.
  - `category_id` (Optional[UUID]) — точкова фільтрація за категорією товару.
  - `q` (Optional[str]) — текстовий пошук за назвою та описом (FR-007).
  - `min_price` і `max_price` (Optional[float], ge=0) — межі ціни.
  - `sort` (`newest` або `oldest`, default `newest`) — порядок за датою публікації (FR-008).

### 2.4 Microsoft Entra ID та ідентифікація автора змін (TM-02)
- **Рішення:** `user_id` завжди призначається на сервері. Роутер `/api/v1/auth` реалізує Microsoft Entra ID Authorization Code Flow через MSAL, створює непрозору server-side сесію та повторно читає локального `User` для кожного захищеного запиту.
- **Обґрунтування:** Microsoft-токени та `client_secret` не потрапляють у React/browser. Cookie містить лише випадковий ID сесії з `HttpOnly` та `SameSite=Lax`; у production додається `Secure`.
- **Перехідний стан:** endpoints оголошень ще приймають прототипний `X-Actor-Id`, а сесії зберігаються in-memory. Заголовок треба замінити `require_current_user`, а для кількареплічного deployment додати Redis-адаптер.

### 2.5 Семантика часткового оновлення (PATCH замість PUT)
- **Рішення:** Використання HTTP методу `PATCH` замість `PUT` для модифікації оголошення.
- **Обґрунтування:** Модель `ListingUpdate` дозволяє передавати лише ті поля, які змінюються. Використання `PATCH` відповідає специфікації REST і унеможливлює ненавмисне скидання відсутніх у запиті полів у `null`. При спробі передати `null` у обов'язкове поле сервер повертає контрольовану помилку `422 Unprocessable Entity` замість `500 Internal Server Error`.

### 2.6 Обране (FR-009)
- **Рішення:** Обране — окремий ресурс `/api/v1/favorites`, прив'язаний до `CurrentUser` із серверної сесії (`require_current_user`, cookie `baraholka_session`). `X-Actor-Id`, а також `user_id` у path, query чи body не враховуються: без валідної сесії — 401, заблокований користувач — 403. `POST /api/v1/favorites/{listing_id}` ідемпотентний: повторне додавання повертає наявний запис без дубліката.
- **Обґрунтування:** Обране одного користувача недоступне іншим (TM-02). Список повертає `ListingPublicResponse`, тож контакти продавців через обране не розкриваються (SEC-002). Додати можна лише активне оголошення (404 для знятого чи неіснуючого), а зняття оголошення власником одразу прибирає його з обраного всіх користувачів.

### 2.7 Категорії оголошень (FR-012)
- **Рішення:** Ресурс `/api/v1/categories` надає публічний перегляд активних категорій для фільтрації каталогу (`GET /api/v1/categories`, `GET /api/v1/categories/{id}`) та захищені адміністративні маршрути (`POST /api/v1/categories`, `PATCH /api/v1/categories/{id}`) для додавання, перейменування й деактивації категорій з обов'язковою перевіркою активної сесії (`X-Actor-Id`) та адміністративної ролі `ADMIN` (`X-Actor-Role: ADMIN` до підключення server-side OIDC claims у гілці Auth PR).
- **Обґрунтування:** Публічний каталог категорій необхідний покупцям і продавцям для категоризації товарів НаУКМА. Деактивовані категорії (`is_active=False`) виключаються з публічної видачі для нових оголошень, але фізично зберігаються в базі даних для цілісності зв'язків з раніше створеними оголошеннями. Будь-які модифікації структури категорій захищені: без сесії повертається HTTP 401 Unauthorized, а звичайний користувач отримує HTTP 403 Forbidden. Оновлення категорії здійснюється через створення нової копії, що унеможливлює пошкодження стану при конфлікті slug (HTTP 409 Conflict). До інтеграції серверних сесій вимога FR-012 заявлена як частково реалізована.

### 2.8 Контакт продавця (FR-010, SEC-002)
- **Рішення:** Контакт продавця віддається лише окремим ресурсом `GET /api/v1/listings/{listing_id}/contact` і лише для `CurrentUser` із серверної сесії (`require_current_user`). Публічні схеми каталогу, деталей і обраного (`ListingPublicResponse`) поля `contact` не мають. Відповідь має `Cache-Control: no-store`.
- **Обґрунтування:** Окремий endpoint робить кожне розкриття контакту явною дією автентифікованого користувача і не змішує його з публічними відповідями (SEC-002, TM-05). Без сесії або лише з `X-Actor-Id` — 401, заблокований користувач — 403, неіснуюче або зняте оголошення — 404. Тіла помилок контакту не містять. `no-store` не дає контакту осідати в кешах браузера чи проксі.

### 2.9 Адміністративна модерація (FR-011)
- **Рішення:** Окремий маршрут `POST /api/v1/admin/listings/{listing_id}/withdraw` з тілом `{"reason": "..."}`; власницький `DELETE /api/v1/listings/{id}` не змінюється. Роль `ADMIN` перевіряється лише з `CurrentUser`, який `require_current_user` щоразу перечитує з локального запису користувача; поля `role`, `moderator_id` у тілі та заголовки `X-Actor-Id` / `X-Actor-Role` ігноруються. Причина обов'язкова: 5–500 символів після обрізання пробілів, інакше 422. Успіх — 201 із записом `ModerationAction` (`id`, `listing_id`, `moderator_id`, `action_type`, `reason`, `created_at`).
- **Обґрунтування:** Модерація — окрема дія з іншим актором і обов'язковим аудитом, тому має власний ресурс, а не прапорець у власницькому `DELETE`. Оголошення не видаляється фізично, а переходить у `WITHDRAWN`, тож історія і причина зберігаються. Зміна статусу, очищення обраного й запис аудиту виконуються як одна операція: при збої будь-якого кроку стан відновлюється. Зараз це забезпечується компенсацією в in-memory сервісі; після підключення PostgreSQL ті самі кроки мають виконуватися в одній транзакції БД (блок persistence). Неіснуюче або вже зняте оголошення — 404, тож повторний запит не створює дубліката аудиту. Перевірка статусу й зміни стану виконуються під замком сервісу, тому два одночасні запити не можуть обидва побачити `ACTIVE`; у PostgreSQL це місце займе `SELECT ... FOR UPDATE` у тій самій транзакції.

---

## 3. Кінцеві точки (Endpoints)

| Метод | URL | Опис | Успішний статус | Статуси помилок |
|---|---|---|---|---|
| `GET` | `/api/v1/listings` | Отримати список оголошень (з пагінацією, фільтрацією та сортуванням) | 200 OK | 422 Unprocessable Entity |
| `GET` | `/api/v1/listings/my` | Отримати історію власних оголошень продавця (активні та зняті, `FR-005`) | 200 OK | 401 Unauthorized, 422 |
| `POST` | `/api/v1/listings` | Створити нове оголошення | 201 Created | 400 Bad Request, 401 Unauthorized, 422 |
| `GET` | `/api/v1/listings/{id}` | Отримати деталі конкретного оголошення за ID (без контактів) | 200 OK | 404 Not Found |
| `PATCH` | `/api/v1/listings/{id}` | Частково оновити дані оголошення | 200 OK | 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 |
| `DELETE` | `/api/v1/listings/{id}` | Видалити оголошення | 204 No Content | 401 Unauthorized, 403 Forbidden, 404 Not Found |
| `GET` | `/api/v1/favorites` | Отримати власне обране (активні оголошення без контактів, `FR-009`) | 200 OK | 401 Unauthorized, 403 Forbidden (заблокований) |
| `POST` | `/api/v1/favorites/{listing_id}` | Додати активне оголошення в обране (без дублікатів) | 201 Created | 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 |
| `DELETE` | `/api/v1/favorites/{listing_id}` | Прибрати оголошення з власного обраного | 204 No Content | 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 |
| `GET` | `/api/v1/listings/{listing_id}/contact` | Отримати контакт продавця активного оголошення (лише з серверною сесією, `FR-010`) | 200 OK | 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 |
| `POST` | `/api/v1/admin/listings/{listing_id}/withdraw` | Зняти чуже оголошення з публікації з причиною (Адміністратор, `FR-011`) | 201 Created | 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 |
| `GET` | `/api/v1/categories` | Отримати список активних категорій для фільтрації каталогу (`FR-012`) | 200 OK | - |
| `GET` | `/api/v1/categories/{id}` | Отримати дані конкретної категорії за ID (`FR-012`) | 200 OK | 404 Not Found, 422 |
| `POST` | `/api/v1/categories` | Створити нову категорію (Адміністратор, `FR-012`) | 201 Created | 401 Unauthorized, 403 Forbidden, 409 Conflict, 422 |
| `PATCH` | `/api/v1/categories/{id}` | Оновити або деактивувати категорію (Адміністратор, `FR-012`) | 200 OK | 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 |
| `GET` | `/api/v1/auth/login` | Розпочати Microsoft Entra ID Authorization Code Flow; опційний `next` зберігає внутрішній маршрут для повернення після входу | 307 Temporary Redirect | 422 Unprocessable Entity, 502 Bad Gateway, 503 Service Unavailable |
| `GET` | `/api/v1/auth/callback` | Перевірити callback та створити локальну сесію | 303 See Other | 400 Bad Request, 401 Unauthorized, 403 Forbidden |
| `GET` | `/api/v1/auth/me` | Отримати поточного користувача | 200 OK | 401 Unauthorized, 403 Forbidden |
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
> - **Етап:** Проєктування API та додавання Microsoft Entra ID Authorization Code Flow.
> - **Що згенеровано:** Опис полів ресурсу, ключових проєктних рішень та контракту `/api/v1/auth` для login, callback, поточного користувача і logout.
> - **Що перевірено / відкинуто вручну:** Опис звірено з Pydantic-моделями, FastAPI-роутерами та згенерованим OpenAPI; явно залишено перехідний `X-Actor-Id` і не подано in-memory session store як кількареплічне production-сховище.
> - **Доповнення (Богдан Солонина, FR-009–FR-011):** Claude (Anthropic) допоміг сформулювати розділи 2.6, 2.8, 2.9 та рядки endpoint-ів контакту й модерації. Звірено вручну з кодом роутерів і тестами; повний набір тестів, black, flake8 і перевірку простежуваності запущено локально.
