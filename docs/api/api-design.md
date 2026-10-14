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
| `contact` | `string` | Required on create | Контактні дані продавця (Telegram / Email) | **Приватне поле:** `ListingCreate`, `ListingUpdate`, `ListingResponse`. **Відсутнє в `ListingPublicResponse`** |
| `user_id` | `UUID` | Auto UUID v4 | Унікальний ідентифікатор автора | Всі відповіді (`ListingPublicResponse`, `ListingResponse`) |
| `status` | `string` | Enum: `ACTIVE`, `RESERVED`, `SOLD` | Поточний стан оголошення | Всі відповіді (`ListingPublicResponse`, `ListingResponse`) |
| `created_at` | `string` (datetime) | ISO 8601 | Дата та час створення оголошення | Всі відповіді (`ListingPublicResponse`, `ListingResponse`) |
| `updated_at` | `string` (datetime) | ISO 8601 | Дата та час останнього оновлення | Всі відповіді (`ListingPublicResponse`, `ListingResponse`) |

---

## 2. Ключові проєктні рішення (Design Decisions)

### 2.1 Code-First підхід та автогенерація документації
- **Рішення:** Обрано розробку на FastAPI з Pydantic v2 замість ручного складання OpenAPI YAML файлу.
- **Обґрунтування:** Код є єдиним джерелом істини (Single Source of Truth). Всі правила валідації, опис полів `Field(...)` та статус-коди прописуються в Python-коді. Скрипт `scripts/generate_openapi.py` зчитує анотації додатка і генерує актуальний `openapi-generated.yaml` без людського фактора.

### 2.2 Захист персональних даних та публічна схема (SEC-002, QA-SEC-01)
- **Рішення:** Розділення схем відповідей на `ListingPublicResponse` та `ListingResponse`.
- **Обґрунтування:** Для захисту конфіденційності контактні дані продавця (`contact`) виключено з публічної схеми `ListingPublicResponse`, яка використовується для загального списку оголошень (`GET /api/v1/listings`) та публічного перегляду по ID (`GET /api/v1/listings/{id}`). Повне представлення `ListingResponse` з контактами повертається лише при створенні (`POST`) або оновленні (`PATCH`).

### 2.3 Пагінація та фільтрація
- **Рішення:** Підтримка query-параметрів `skip`, `limit` та `category_id` в ендпоінті `GET /api/v1/listings`.
- **Обґрунтування:**
  - `skip` (default 0, ge=0) — параметр зсуву для пагінації.
  - `limit` (default 10, ge=1, le=100) — обмеження розміру сторінки для запобігання перевантаженню сервера.
  - `category_id` (Optional[UUID]) — точкова фільтрація за категорією товару.
  - `q` (Optional[str]) — текстовий пошук за назвою та описом (FR-007).

### 2.4 Ідентифікація автора змін до впровадження JWT (TM-02)
- **Рішення:** `user_id` завжди призначається на сервері. Мутації (`POST` / `PATCH` / `DELETE`) вимагають заголовок `X-Actor-Id`.
- **Обґрунтування:** Клієнт не може підмінити власника в тілі запиту. Заголовок є тимчасовим адаптером до ADR-003: після появи Bearer JWT актор братиметься лише з claim `sub`. Відсутність заголовка дає 401, чуже оголошення — 403.

### 2.5 Семантика часткового оновлення (PATCH замість PUT)
- **Рішення:** Використання HTTP методу `PATCH` замість `PUT` для модифікації оголошення.
- **Обґрунтування:** Модель `ListingUpdate` дозволяє передавати лише ті поля, які змінюються. Використання `PATCH` відповідає специфікації REST і унеможливлює ненавмисне скидання відсутніх у запиті полів у `null`. При спробі передати `null` у обов'язкове поле сервер повертає контрольовану помилку `422 Unprocessable Entity` замість `500 Internal Server Error`.

---

## 3. Кінцеві точки (Endpoints)

| Метод | URL | Опис | Успішний статус | Статуси помилок |
|---|---|---|---|---|
| `GET` | `/api/v1/listings` | Отримати список оголошень (з пагінацією/фільтрацією) | 200 OK | 422 Unprocessable Entity |
| `POST` | `/api/v1/listings` | Створити нове оголошення | 201 Created | 401 Unauthorized, 422 |
| `GET` | `/api/v1/listings/{id}` | Отримати деталі конкретного оголошення за ID (без контактів) | 200 OK | 404 Not Found |
| `PATCH` | `/api/v1/listings/{id}` | Частково оновити дані оголошення | 200 OK | 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 |
| `DELETE` | `/api/v1/listings/{id}` | Видалити оголошення | 204 No Content | 401 Unauthorized, 403 Forbidden, 404 Not Found |

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
> - **Інструменти:** Gemini
> - **Етап:** Проєктування API (API Design Review & Refinement)
> - **Що згенеровано:** Опис полів ресурсу, таблиця полів, розділ ключових проєктних рішень (Code-First, SEC-002, пагінація, PATCH-семантика).
> - **Що перевірено / відкинуто вручну:** Опис полів перевірено на відповідність фактичним Pydantic-моделям у `src/api/schemas/listings.py`. Таблицю проєктних рішень було вивірено згідно з зауваженнями API Review.
