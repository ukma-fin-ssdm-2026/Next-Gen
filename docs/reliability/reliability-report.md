# Командний звіт про надійність (Reliability Report — Лабораторна робота 9)

Цей документ підсумовує результати аналізу надійності кодової бази **Baraholka NaUKMA**, класифікацію ланцюгів загроз (*Несправність → Помилка → Відмова*), застосовані патерни стійкості, режими відмов та стратегії відновлення, результати тестування надійності з ін'єкцією збоїв та виконані бонусні завдання.

---

## 1. Зведена таблиця знайдених проблем та оцінка критичності

Під час інтерактивної активності **Resilience Scavenger Hunt** ([`docs/reliability/scavenger-hunt.md`](scavenger-hunt.md)) команда виявила 7 реальних точок відмови у продуктовому коді `src/` за всіма п'ятьма категоріями (`A–E`):

| ID | Категорія | Локація в коді | Несправність (Fault) | Помилка (Error) | Відмова (Failure) | Критичність | Статус |
|---|---|---|---|---|---|---|---|
| **REL-01** | **B** (Зовнішні залежності) | `src/integrations/entra.py:45-82` | Виклики MSAL до Microsoft Entra ID без HTTP `timeout`, без повторів при транзієнтних збоях та без перехоплення `RequestException` / `OSError` | Необроблений мережевий виняток або зависання потоку під час OIDC-автентифікації | Користувач отримує неконтрольований `HTTP 500` або зависання входу; воркери блокуються | **Висока** | **Виправлено** (`fix/lab09-entra-resilience`, Є. Остапенко) |
| **REL-02** | **A** (Обробка помилок) | `src/api/main.py:139-142` | Занадто широкий `except Exception:` без логування при читанні зображень зі сховища | Системні помилки вводу-виводу (`PermissionError`, `OSError`) трактуються як відсутність файлу | Клієнт отримує хибний `HTTP 404`, а аварії файлової системи приховуються від моніторингу | **Висока** | Кандидат Етапу 3 (у роботі команди) |
| **REL-03** | **B** (Зовнішні залежності) | `src/db/engine.py:37-43` | Створення пулу SQLAlchemy `create_engine` без `connect_timeout` | Потоки пулу зависають на системному TCP-таймауті (~120 с) при недоступності PostgreSQL | Каскадне вичерпання пулу з'єднань та параліч API (`504 Gateway Timeout`) | **Висока** | Кандидат Етапу 3 (у роботі команди) |
| **REL-04** | **E** (Продуктивність і блокування) | `src/repositories/postgres_listings.py:27-30`, `src/services/listings.py:82` | Нелімітована вибірка `SELECT` усіх рядків таблиці оголошень у пам'ять Python | Надмірне споживання RAM та блокування CPU при серіалізації великого каталогу | Деградація часу відповіді (`p99 > 3 с`) та ризик аварійної зупинки контейнера (`OOM`) | **Висока** | Кандидат Етапу 3 (у роботі команди) |
| **REL-05** | **C** (Валідація вхідних даних) | `src/api/schemas/listings.py:74-80, 126-158`, `src/domain/listings.py:62-79` | Відсутність `.strip()` у схемах `ListingCreate`/`ListingUpdate` та guard clauses у доменній сутності `Listing` | Рядки з пробілів (`"   "`) проходять `min_length=3` і записуються в БД як активне оголошення | API повертає `201`/`200` замість `422`; у каталозі з'являється оголошення без назви та з порожнім контактом продавця (`FR-002`, `FR-010`) | **Середня** | Відкритий ризик (Backlog) |
| **REL-06** | **D** (Мовчазні збої) | `src/repositories/image_storage.py:449-453` | Порожній блок `except (OSError, InvalidListingImageError): pass` у `_safe_delete_blob` | Невидалені тимчасові або застарілі файли залишаються на диску без запису в журнал | Непомітний витік дискового простору; відсутність діагностики проблем із правами доступу | **Середня** | Відкритий ризик (Backlog) |
| **REL-07** | **E / D** (Ресурси та мовчазні збої) | `src/services/auth_sessions.py:22-38` | Відсутність періодичного TTL-очищення покинутих OIDC-потоків у словнику `_flows` | Накопичення прострочених записів `_ExpiringValue` у пам'яті при незавершених входах | Поступовий витік оперативної пам'яті (Memory Leak) при тривалій роботі чи флуді `/auth/login` | **Середня** | Відкритий ризик (Backlog) |

---

## 2. Виправлення проблем: код «До / Після»

### 2.1. REL-01: Надійність інтеграції з Microsoft Entra ID (`src/integrations/entra.py`)

**Автор виправлення та тестів:** Євгеній Остапенко (гілка `fix/lab09-entra-resilience`).

#### Код ДО виправлення:
```python
class MsalEntraOidcClient:
    """Confidential web client; client secret не потрапляє у browser."""

    def __init__(self, settings: EntraSettings) -> None:
        self._settings = settings
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            from msal import ConfidentialClientApplication

            self._client = ConfidentialClientApplication(
                client_id=self._settings.client_id,
                client_credential=self._settings.client_secret,
                authority=self._settings.authority,
            )
        return self._client

    def begin(self) -> dict[str, Any]:
        try:
            flow = self._get_client().initiate_auth_code_flow(
                scopes=OIDC_SCOPES,
                redirect_uri=self._settings.redirect_uri,
            )
        except ValueError as exc:
            raise EntraOidcError("Не вдалося розпочати вхід Microsoft") from exc
        if "auth_uri" not in flow or "state" not in flow:
            raise EntraOidcError("Не вдалося розпочати вхід Microsoft")
        return flow

    def complete(
        self,
        flow: dict[str, Any],
        auth_response: dict[str, str],
    ) -> VerifiedEntraClaims:
        try:
            result = self._get_client().acquire_token_by_auth_code_flow(
                flow,
                auth_response,
            )
        except ValueError as exc:
            raise EntraOidcError("Невалідний state або nonce") from exc

        if "error" in result:
            raise EntraOidcError("Вхід Microsoft відхилено")
        claims = result.get("id_token_claims")
        if not isinstance(claims, dict):
            raise EntraOidcError("Відповідь Microsoft не містить ID token claims")
        return verified_claims_from_msal(claims)
```

#### Код ПІСЛЯ виправлення:
```python
ENTRA_HTTP_TIMEOUT_SECONDS = 5.0
ENTRA_MAX_RETRY_ATTEMPTS = 3
ENTRA_BASE_BACKOFF_SECONDS = 0.2
ENTRA_MAX_BACKOFF_SECONDS = 2.0


def compute_full_jitter_backoff(
    attempt: int,
    *,
    base_delay: float = ENTRA_BASE_BACKOFF_SECONDS,
    max_delay: float = ENTRA_MAX_BACKOFF_SECONDS,
    uniform_fn: Callable[[float, float], float] | None = None,
) -> float:
    if attempt < 0:
        raise ValueError("Номер спроби attempt не може бути від'ємним")
    if base_delay < 0 or max_delay < 0:
        raise ValueError("Параметри затримки backoff не можуть бути від'ємними")
    cap = min(max_delay, base_delay * (2**attempt))
    chooser = uniform_fn if uniform_fn is not None else _SYSTEM_RANDOM.uniform
    return float(chooser(0.0, cap))


class MsalEntraOidcClient:
    """Confidential web client; client secret не потрапляє у browser."""

    _timeout: float = ENTRA_HTTP_TIMEOUT_SECONDS
    _max_attempts: int = ENTRA_MAX_RETRY_ATTEMPTS
    _base_backoff: float = ENTRA_BASE_BACKOFF_SECONDS
    _sleep_fn: Callable[[float], None] = staticmethod(time.sleep)

    def __init__(
        self,
        settings: EntraSettings,
        *,
        timeout: float = ENTRA_HTTP_TIMEOUT_SECONDS,
        max_attempts: int = ENTRA_MAX_RETRY_ATTEMPTS,
        base_backoff: float = ENTRA_BASE_BACKOFF_SECONDS,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("HTTP timeout для Entra ID має бути більшим за 0")
        if max_attempts < 1:
            raise ValueError("Кількість спроб max_attempts має бути не меншою за 1")
        if base_backoff < 0:
            raise ValueError("Базова затримка base_backoff не може бути від'ємною")
        self._settings = settings
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._base_backoff = base_backoff
        self._sleep_fn = sleep_fn
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            from msal import ConfidentialClientApplication

            self._client = ConfidentialClientApplication(
                client_id=self._settings.client_id,
                client_credential=self._settings.client_secret,
                authority=self._settings.authority,
                timeout=self._timeout,
            )
        return self._client

    def begin(self) -> dict[str, Any]:
        flow: Any = None
        for attempt in range(self._max_attempts):
            try:
                flow = self._get_client().initiate_auth_code_flow(
                    scopes=OIDC_SCOPES,
                    redirect_uri=self._settings.redirect_uri,
                )
                break
            except ValueError as exc:
                raise EntraOidcError("Не вдалося розпочати вхід Microsoft") from exc
            except (RequestException, OSError) as exc:
                if attempt + 1 >= self._max_attempts:
                    logger.warning(
                        "Помилка мережі при ініціалізації входу через Microsoft Entra "
                        "(вичерпано %d спроб): %s",
                        self._max_attempts,
                        exc,
                    )
                    raise EntraOidcError(
                        "Сервіс автентифікації Microsoft тимчасово недоступний"
                    ) from exc
                delay = compute_full_jitter_backoff(
                    attempt,
                    base_delay=self._base_backoff,
                )
                self._sleep_fn(delay)

        if not isinstance(flow, dict) or "auth_uri" not in flow or "state" not in flow:
            raise EntraOidcError("Не вдалося розпочати вхід Microsoft")
        return flow
```

---

## 3. Опис застосованих патернів надійності

Під час усунення критичних ризиків застосовано такі інженерні патерни стійкості (відповідно до Лекції 9 «Інженерія надійності»):

1. **Тайм-аути на зовнішні операції (Timeouts, §3.2):**
   - Для клієнта Microsoft Entra ID встановлено жорстку верхню межу очікування HTTP-відповіді `ENTRA_HTTP_TIMEOUT_SECONDS = 5.0` секунд (`timeout=self._timeout` у `ConfidentialClientApplication`). Це унеможливлює нескінченне блокування робочих потоків FastAPI у разі зависання зовнішнього провайдера `login.microsoftonline.com`.
2. **Обмежені повтори з експоненційним відступом і повним джитером (Bounded Retries + Exponential Backoff + Full Jitter, §3.3, §3.5):**
   - Для ідемпотентного виклику `begin()` додано до `3` спроб при мережевих помилках із випадковою паузою в діапазоні $[0, \min(\text{max\_delay}, \text{base\_delay} \cdot 2^{\text{attempt}})]$. Це дозволяє автоматично пережити короткочасні мережеві збої та уникає синхронізованих штормів повторних запитів (*thundering herd*).
3. **Захисні перевірки та валідація входу (Guard Clauses, §3.1):**
   - У конструкторі `MsalEntraOidcClient` додано guard clauses для `timeout <= 0`, `max_attempts < 1`, `base_backoff < 0`, що відсікають некоректну конфігурацію ще на старті (Fail Fast).
   - На початку `complete()` додано guard-перевірки `if not isinstance(flow, dict) or not flow` та `if not isinstance(auth_response, dict) or not auth_response`, які негайно відхиляють порожні чи пошкоджені структури даних до виконання мережевого запиту.
   - Після виклику зовнішнього SDK додано перевірку типу відповіді `if not isinstance(result, dict)` перед зверненням до ключів словника.
4. **Вузьке перехоплення винятків (Specific Exception Handling):**
   - Замість широкого `except Exception` розділено обробку логічних помилок валідації параметрів (`except ValueError`) та транспортних/мережевих відмов зовнішнього сервісу (`except (RequestException, OSError)`).
5. **Структуроване логування збоїв без витоку чутливих деталей (Diagnostic Logging):**
   - При виникненні мережевого збою або тайм-ауту подія фіксується у серверному журналі через `logger.warning(...)` із технічною причиною збою для операторів, тоді як користувачеві повертається безпечне локалізоване повідомлення без внутрішніх стектрейсів.

---

## 4. Режими відмов і стратегія відновлення (Failure Modes & Recovery)

Для кожної точки відмови визначено обґрунтований вибір між **швидкою відмовою (Fail Fast)** і **безпечною відмовою (Fail Safe)**, поведінку системи очима користувача та механізм повернення до нормальної роботи:

| ID | Обраний режим відмови | Обґрунтування вибору (Швидка vs Безпечна відмова) | Що бачить користувач під час збою | Як система повертається до норми (Відновлення) |
|---|---|---|---|---|
| **REL-01** (Entra OIDC) | **Швидка відмова (Fail Fast) після обмежених повторів** | Автентифікація є критичною межею безпеки (`FR-001`, `SEC-001`). Повернення «резервного» чи анонімного профілю при збої Entra ID неприпустиме, бо порушує контроль доступу. Після 3 швидких спроб для ідемпотентного `begin()` система контрольовано перериває запит. | На `/api/v1/auth/login` — контрольована відповідь `HTTP 502 Bad Gateway` з повідомленням *«Сервіс автентифікації Microsoft тимчасово недоступний»* (без крашу `500`). Інші публічні сторінки маркетплейсу працюють штатно. | **Автоматичне відновлення при повторній спробі (Bounded Retry + Stateless Recovery):** короткочасний мережевий збій долається автоматично під час 3 спроб з full jitter; при тривалому падінні Microsoft наступний натиск «Увійти» після підняття сервісу працює без ручного втручання. |
| **REL-02** (Читання фото з диска) | **Швидка відмова (Fail Fast) з розмежуванням 404/500** | Відсутність файлу (`InvalidListingImageError`) — штатна ситуація (`404`), а аварія диска (`OSError`/`PermissionError`) — інфраструктурний збій, який не можна маскувати під `404`. | При відсутності фото — `404 Not Found` (фронтенд підставляє іконку-заглушку товару). При аварії диска — контрольований `500` і запис у серверний лог помилок. | **Локалізована деградація + втручання оператора:** каталог оголошень і тексти продовжують працювати; після відновлення прав доступу або примонтування тома роздача фото відновлюється автоматично. |
| **REL-03** (Таймаут підключення до БД) | **Швидка відмова (Fail Fast)** | При недоступності PostgreSQL очікування протягом 120 с вичерпує всі потоки сервера. Обмеження `connect_timeout=5` швидко звільняє потік і сигналізує про проблему. | Користувач отримує швидку відповідь про тимчасову недоступність сервісу замість нескінченного завантаження сторінки. | **Автоматичне перепідключення пулу (`pool_pre_ping=True`):** коли база даних піднімається, SQLAlchemy автоматично перевіряє життєздатність з'єднання перед видачею з пулу і відновлює роботу без перезапуску контейнера API. |
| **REL-04** (Обмеження вибірки каталогу) | **Безпечна відмова / Контрольована деградація (Fail Safe bound)** | Замість завантаження необмеженої кількості рядків, що веде до `Out-Of-Memory`, безпечніше обмежити верхню межу вибірки (`LIMIT`) і повернути найновіші активні оголошення. | Користувач бачить перші сторінки найактуальніших оголошень та використовує пошук/фільтри за категоріями. | **Штатна робота в межах квоти пам'яті:** процес бекенда залишається стабільним при будь-якому розмірі таблиці в БД. |
| **REL-05** (Пробільні поля `title`/`contact` в оголошеннях) | **Швидка відмова (Fail Fast)** | Рядки, що складаються лише з пробілів (`"   "`), мають відхилятися на вхідній межі (`422`) та в доменній сутності `Listing`, щоб у базу даних не потрапляли порожні оголошення чи контакти. | Клієнт отримує чітку помилку валідації (`422 Unprocessable Content`) із поясненням, що назва та контакти не можуть складатися лише з пробілів. | **Виправлення вводу клієнтом:** продавець вводить змістовну назву оголошення та реальні контактні дані й повторно надсилає запит. |
| **REL-06** (Логування при видаленні блобів) | **Безпечна відмова (Fail Safe) з логуванням** | Помилка видалення старого файлу зображення під час очищення не повинна ламати основну бізнес-операцію користувача (видалення чи оновлення оголошення), але мусить залишати слід у логах. | Основна операція користувача завершується успішно; користувач не бачить збою. | **Фонове/ручне очищення:** оператор бачить `WARNING` у логах із ключем незношеного блоба і може усунути проблему з правами або очистити диск. |

---

## 5. Верифікація тестами надійності (`/tests/reliability/`)

У каталозі [`tests/reliability/test_entra_reliability.py`](../../tests/reliability/test_entra_reliability.py) реалізовано набір автоматизованих тестів надійності з прив'язкою до вимог RTM (`[TP-AUTH-01]`, `[TP-AUTH-03]`, `[FR-001]`, `[SEC-001]`):

| Категорія тесту (за умовою Лаб 9) | Тестова функція | Що перевіряє | Результат |
|---|---|---|---|
| **1. Тест обробки помилки** | `test_entra_complete_handles_rejected_or_malformed_token_response_gracefully` | Перевіряє, що при відхиленні входу провайдером (`error: access_denied`), відсутності `id_token_claims` або поверненні `None` замість словника система не падає з `KeyError`/`TypeError`, а підіймає контрольований `EntraOidcError`. | `PASSED` |
| **2. Тест зовнішньої відмови (ін'єкція збою)** | `test_entra_fault_injection_network_timeout_and_connection_error` | Тестовий дублер `_FaultInjectingMsalClient` ін'єктує `requests.Timeout` та `requests.ConnectionError` у методи `begin()` і `complete()`. Перевіряється запис попередження у лог (`caplog`) та повернення `HTTP 502 Bad Gateway` на `/api/v1/auth/login` замість `500`. | `PASSED` |
| **3. Граничні тести (Boundary tests)** | `test_entra_boundary_rejects_non_positive_timeout`, `test_entra_boundary_rejects_invalid_retry_or_backoff_parameters`, `test_entra_boundary_rejects_empty_or_non_dict_flow_and_response` | Перевіряють спрацювання guard clauses на межових і некоректних вхідних даних: `timeout <= 0`, `max_attempts < 1`, `base_backoff < 0`, а також порожні (`{}`) або `None` аргументи `flow` і `auth_response`. | `PASSED` (9 кейсів) |
| **4. Бонус 1 (Backoff + Full Jitter)** | `test_entra_begin_retries_with_exponential_backoff_and_full_jitter_are_bounded`, `test_entra_begin_recovers_on_transient_failure_before_max_attempts` | Доводять, що кількість спроб ідемпотентного `begin()` суворо обмежена (`max_attempts=3`), затримка обчислюється з full jitter, при тимчасовому збої система відновлюється, а після вичерпання спроб спрацьовує контрольована реакція `EntraOidcError`. | `PASSED` |

Команда запуску:
```bash
pytest -q tests/reliability/
```

---

## 6. Які проблеми залишилися відкритими

На момент формування цього звіту:
1. **Виправлено та покрито тестами надійності:**
   - **REL-01** (`src/integrations/entra.py` — тайм-аут клієнта MSAL, обмежені повтори з експоненційним відступом і full jitter, захисні перевірки, перехоплення мережевих збоїв та логування).
2. **Передано в роботу учасникам команди для індивідуальних виправлень Етапу 3 та відеозвітів:**
   - **REL-02** (`src/api/main.py` — розділення клієнтської помилки `404` та системної відмови читання диска з логуванням).
   - **REL-03** (`src/db/engine.py` — додавання `connect_timeout` для SQLAlchemy engine).
   - **REL-04** (`src/repositories/postgres_listings.py` — обмеження верхньої межі вибірки каталогу).
3. **Задокументовано у відкритому беклозі (Open Risks / Backlog):**
   - **REL-05** (`src/api/schemas/listings.py`, `src/domain/listings.py` — нормалізація `.strip()` і guard-перевірки на пробільні рядки `title` і `contact`).
   - **REL-06** (`src/repositories/image_storage.py` — додавання `logger.warning` у `_safe_delete_blob`).
   - **REL-07** (`src/services/auth_sessions.py` — періодичне очищення прострочених записів у `InMemoryOidcFlowStore`).

---

## 7. Нотатка «Використання ШІ»

> - **Інструмент:** Antigravity (Advanced Agentic AI Assistant, Google DeepMind).
> - **Етап:** Лабораторна робота 9 — проєктування виправлення точки відмови `REL-01`, реалізація експоненційного відступу з повним джитером (`compute_full_jitter_backoff`), написання тестів надійності з ін'єкцією збою (`tests/reliability/test_entra_reliability.py`) та підготовка командного звіту `reliability-report.md`.
> - **Що згенеровано з допомогою асистента:**
>   1. Реалізація захисних перевірок, конфігурації `timeout`, композиції обмежених повторів із full jitter (`§3.3`, `§3.5`) та обробки мережевих винятків `(RequestException, OSError)` у `src/integrations/entra.py`.
>   2. Набір модульних та інтеграційних тестів надійності з тестовим дублером `_FaultInjectingMsalClient` у `tests/reliability/test_entra_reliability.py`.
>   3. Структурований проєкт командного звіту з таблицею режимів відмов (Fail Fast / Fail Safe) та стратегій відновлення.
> - **Як верифіковано людиною (Відповідальний за документацію — Євгеній Остапенко):**
>   - Виконано прогін створених тестів надійності (`pytest tests/reliability/test_entra_reliability.py`) та перевірку двосторонньої простежуваності вимог (`pytest tests/test_traceability.py`).
>   - Перевірено дотримання стандартів якості коду та безпеки (`black --check`, `flake8`, `bandit`).
>   - Звірено кожен фрагмент коду «До / Після» та опис поведінки HTTP-ендпоінтів (`/api/v1/auth/login`, `/api/v1/auth/callback`) із фактичною реалізацією в репозиторії.

---

## 8. Бонуси

### Бонус 1: Повтори з відступом (`backoff`) і джитером (`jitter`) (+0,25 бала)

- **Ідемпотентний зовнішній виклик:** ініціалізація OIDC-потоку `MsalEntraOidcClient.begin()` (`initiate_auth_code_flow`) у [`src/integrations/entra.py`](../../src/integrations/entra.py). На відміну від обміну одноразового коду в `complete()`, операція `begin()` є повністю ідемпотентною, оскільки лише формує параметри редіректу та завантажує метадані OpenID-конфігурації Microsoft.
- **Композиція патернів за порядком §3.5 Лекції 9:**
  1. **Внутрішній шар — Тайм-аут (§3.2):** кожна окрема HTTP-спроба обмежена часом `ENTRA_HTTP_TIMEOUT_SECONDS = 5.0` с.
  2. **Середній шар — Обмежені повтори з Exponential Backoff + Full Jitter (§3.3):** при виникненні мережевого винятку `(RequestException, OSError)` виконується до `ENTRA_MAX_RETRY_ATTEMPTS = 3` спроб. Перед кожним повтором функція `compute_full_jitter_backoff(attempt)` обчислює верхню межу $\text{cap} = \min(\text{max\_delay}, \text{base\_delay} \cdot 2^{\text{attempt}})$ і обирає випадкову затримку рівномірно на відрізку $[0, \text{cap}]$ за допомогою `secrets.SystemRandom().uniform`.
  3. **Зовнішній шар — Обрана реакція (Fail Fast, §3.1):** якщо після останньої (`3`-ї) спроби збій не зник, подія логується через `logger.warning(...)` і підіймається доменний `EntraOidcError`, який повертає клієнту контрольований статус `HTTP 502 Bad Gateway`.
- **Докази в тестах ([`tests/reliability/test_entra_reliability.py`](../../tests/reliability/test_entra_reliability.py)):**
  - `test_entra_begin_retries_with_exponential_backoff_and_full_jitter_are_bounded` — доводить, що при постійному таймауті виконується рівно `3` спроби (`double.begin_calls == 3`), між ними виконуються `2` паузи в межах full jitter (`0.0 <= sleep_0 <= 0.2`, `0.0 <= sleep_1 <= 0.4`), а після 3-ї спроби спрацьовує `EntraOidcError`.
  - `test_entra_begin_recovers_on_transient_failure_before_max_attempts` — доводить, що при тимчасовому збої на 1-й і 2-й спробах третя спроба успішно завершує ініціалізацію потоку входу.
- **Пояснення у відео:** демонструється та пояснюється у відеозвіті Євгенія Остапенка (`Labs/Lab09/video_Ostapenko.txt`).
