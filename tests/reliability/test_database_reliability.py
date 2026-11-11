"""Тести надійності підключення до PostgreSQL (Лаб 9, REL-03).

Несправність: engine створювався без `connect_timeout` і з типовим очікуванням
пулу, тому при недоступній БД потік запиту висів до системного TCP-таймауту.
Обрано швидку відмову (fail fast): підключення обмежене тайм-аутом, а API
відповідає зрозумілим 503 з `Retry-After` замість зависання чи 500.

1. Граничний тест: тайм-аути зі змінних середовища перевіряються на старті.
2. Тест конфігурації: engine отримує `connect_timeout` і `pool_timeout`.
3. Ін'єкція збою: дублер залежності сесії імітує недоступну БД.
4. Відновлення: коли БД знову доступна, той самий запит проходить.
"""

import logging
import os
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from src.api import deps
from src.api.main import DB_RETRY_AFTER_SECONDS, DB_UNAVAILABLE_DETAIL, app
from src.db import engine as db_engine

URL = "postgresql+psycopg2://user:secret@db.invalid:5432/baraholka"

requires_postgres = pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").startswith("postgresql"),
    reason="Потрібен PostgreSQL (DATABASE_URL); у CI це job postgres-migration.",
)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("", db_engine.DEFAULT_DB_CONNECT_TIMEOUT_SECONDS), ("7", 7), (" 3 ", 3)],
)
def test_timeout_env_accepts_default_and_positive_values(
    monkeypatch, raw, expected
) -> None:
    """[TP-037] [REL-001]
    Порожня змінна дає значення за замовчуванням, додатне ціле читається як є.
    """
    monkeypatch.setenv("DB_CONNECT_TIMEOUT_SECONDS", raw)
    assert (
        db_engine.read_timeout_seconds(
            "DB_CONNECT_TIMEOUT_SECONDS",
            db_engine.DEFAULT_DB_CONNECT_TIMEOUT_SECONDS,
        )
        == expected
    )


@pytest.mark.parametrize("raw", ["0", "-5", "abc", "1.5"])
def test_timeout_env_rejects_non_positive_or_non_integer(monkeypatch, raw) -> None:
    """[TP-037] [REL-001]
    Граничні значення (0, від'ємне, нечислове, дробове) зупиняють старт із
    зрозумілою помилкою, а не вимикають тайм-аут непомітно.
    """
    monkeypatch.setenv("DB_POOL_TIMEOUT_SECONDS", raw)
    with pytest.raises(RuntimeError, match="DB_POOL_TIMEOUT_SECONDS"):
        db_engine.read_timeout_seconds(
            "DB_POOL_TIMEOUT_SECONDS", db_engine.DEFAULT_DB_POOL_TIMEOUT_SECONDS
        )


def test_engine_is_built_with_connect_pool_and_query_timeouts(monkeypatch) -> None:
    """[TP-037] [REL-001]
    Engine обмежує підключення (`connect_timeout`), очікування пулу
    (`pool_timeout`) і вже відкрите з'єднання: `statement_timeout` для запиту,
    TCP keepalive і `tcp_user_timeout` для обірваної мережі; параметри SQL не
    потрапляють у текст винятків і логи (`hide_parameters`).
    """
    captured: dict = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(db_engine, "create_engine", fake_create_engine)

    db_engine.build_engine(URL, connect_timeout=4, pool_timeout=9, statement_timeout=7)

    assert captured["url"] == URL
    assert captured["connect_args"] == {
        "connect_timeout": 4,
        "options": "-c statement_timeout=7000",
        "keepalives": 1,
        "keepalives_idle": db_engine.DB_KEEPALIVES_IDLE_SECONDS,
        "keepalives_interval": db_engine.DB_KEEPALIVES_INTERVAL_SECONDS,
        "keepalives_count": db_engine.DB_KEEPALIVES_COUNT,
        "tcp_user_timeout": 7000,
    }
    assert captured["pool_timeout"] == 9
    assert captured["pool_pre_ping"] is True
    assert captured["hide_parameters"] is True


def _unavailable_session(exc: Exception):
    def override():
        raise exc
        yield  # pragma: no cover

    return override


@pytest.mark.parametrize(
    "exc",
    [
        OperationalError(
            "SELECT 1", {}, Exception("connection to server failed: timeout expired")
        ),
        PoolTimeoutError("QueuePool limit of size 5 overflow 10 reached"),
    ],
    ids=["connect-timeout", "pool-exhausted"],
)
def test_unavailable_database_returns_503_without_internal_details(exc, caplog) -> None:
    """[TP-037] [REL-001]
    Ін'єкція збою: сесія БД недоступна. Каталог відповідає 503 з Retry-After і
    зрозумілим повідомленням, внутрішні деталі не витікають, збій записано в лог.
    """
    app.dependency_overrides[deps.get_db_session] = _unavailable_session(exc)

    with caplog.at_level(logging.ERROR, logger="src.api.main"):
        response = TestClient(app).get("/api/v1/listings")

    assert response.status_code == 503
    assert response.headers["Retry-After"] == str(DB_RETRY_AFTER_SECONDS)
    assert response.json() == {"detail": DB_UNAVAILABLE_DETAIL}
    assert "timeout expired" not in response.text
    assert "QueuePool" not in response.text
    assert any("/api/v1/listings" in record.getMessage() for record in caplog.records)


class _HangingSession:
    """Дублер сесії: з'єднання вже видано з пулу, але запит обривається тайм-аутом."""

    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise OperationalError(
                "SELECT listings.id FROM listings",
                {"q": "secret-search"},
                Exception("canceling statement due to statement timeout"),
            )

        return fail


def test_in_flight_query_timeout_returns_503(caplog) -> None:
    """[TP-037] [REL-001]
    Ін'єкція збою під час уже відкритого з'єднання: запит каталогу обірвано
    тайм-аутом (statement_timeout / мережа). API відповідає 503, а не висить чи 500.
    """

    def in_flight_failure():
        yield _HangingSession()

    app.dependency_overrides[deps.get_db_session] = in_flight_failure

    with caplog.at_level(logging.ERROR, logger="src.api.main"):
        response = TestClient(app).get("/api/v1/listings")

    assert response.status_code == 503
    assert response.json() == {"detail": DB_UNAVAILABLE_DETAIL}
    assert "statement timeout" not in response.text
    assert "secret-search" not in response.text


@requires_postgres
def test_postgres_cancels_query_that_exceeds_statement_timeout() -> None:
    """[TP-037] [REL-001]
    Реальний PostgreSQL: engine з `statement_timeout=1` обриває `pg_sleep(5)`
    приблизно за секунду через OperationalError (його API перетворює на 503).
    Підключення з усіма параметрами з'єднання підтверджує, що libpq їх приймає.
    """
    engine = db_engine.build_engine(
        db_engine.get_database_url(),
        connect_timeout=5,
        pool_timeout=10,
        statement_timeout=1,
    )
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SHOW statement_timeout")).scalar() == "1s"
            started = time.monotonic()
            with pytest.raises(OperationalError, match="statement timeout"):
                connection.execute(text("SELECT pg_sleep(5)"))
            assert time.monotonic() - started < 3
    finally:
        engine.dispose()


def test_db_failure_log_uses_route_template_not_raw_url(caplog) -> None:
    """[TP-037] [REL-001]
    Захист від log injection: у лог обробника 503 потрапляє шаблон маршруту, а не
    шлях із запиту, тож закодований перенос рядка не підробить запис журналу.
    """
    app.dependency_overrides[deps.get_db_session] = _unavailable_session(
        OperationalError("SELECT 1", {}, Exception("connection refused"))
    )

    with caplog.at_level(logging.ERROR, logger="src.api.main"):
        response = TestClient(app).get("/api/v1/listings/x%0AFAKE-LOG-ENTRY")

    assert response.status_code == 503
    messages = [record.getMessage() for record in caplog.records]
    assert any("/api/v1/listings/{listing_id}" in message for message in messages)
    assert all("FAKE-LOG-ENTRY" not in message for message in messages)


def test_catalog_recovers_when_database_is_back() -> None:
    """[TP-037] [REL-001]
    Відновлення: після збою той самий запит проходить без перезапуску застосунку.
    """
    app.dependency_overrides[deps.get_db_session] = _unavailable_session(
        OperationalError("SELECT 1", {}, Exception("server closed the connection"))
    )
    client = TestClient(app)
    assert client.get("/api/v1/listings").status_code == 503

    app.dependency_overrides.pop(deps.get_db_session)
    assert client.get("/api/v1/listings").status_code == 200


def test_openapi_declares_503_only_where_database_is_used() -> None:
    """[TP-037] [REL-001]
    Контракт: 503 з Retry-After є в операціях, що відкривають сесію БД, і відсутній
    там, де БД не використовується (/health, вихід із системи).
    """
    paths = app.openapi()["paths"]

    catalog_503 = paths["/api/v1/listings"]["get"]["responses"]["503"]
    assert "Retry-After" in catalog_503["headers"]
    example = catalog_503["content"]["application/json"]["example"]
    assert example == {"detail": DB_UNAVAILABLE_DETAIL}
    assert "503" in paths["/api/v1/favorites"]["get"]["responses"]

    assert "503" not in paths["/health"]["get"]["responses"]
    assert "503" not in paths["/api/v1/auth/logout"]["post"]["responses"]

    for auth_path in ("/api/v1/auth/login", "/api/v1/auth/callback", "/api/v1/auth/me"):
        auth_503 = paths[auth_path]["get"]["responses"]["503"]
        assert "Entra ID not configured" in auth_503["description"]
        assert "база даних" in auth_503["description"]
        assert "Retry-After" in auth_503["headers"]


@pytest.mark.parametrize(
    "variable",
    [
        "DB_CONNECT_TIMEOUT_SECONDS",
        "DB_POOL_TIMEOUT_SECONDS",
        "DB_STATEMENT_TIMEOUT_SECONDS",
    ],
)
@pytest.mark.parametrize("raw", ["0", "abc"])
def test_startup_fails_fast_on_invalid_timeout_when_database_is_configured(
    monkeypatch, variable, raw
) -> None:
    """[TP-037] [REL-001]
    З DATABASE_URL некоректний тайм-аут зупиняє старт застосунку ще до першого
    запиту, а не дає 500 на першому зверненні до БД.
    """
    monkeypatch.setenv("DATABASE_URL", URL)
    monkeypatch.setenv(variable, raw)

    with pytest.raises(RuntimeError, match=variable):
        with TestClient(app):
            pass


@pytest.mark.parametrize(
    ("database_url", "timeout"), [(URL, "5"), ("", "0")], ids=["valid", "in-memory"]
)
def test_startup_succeeds_with_valid_timeouts_or_without_database(
    monkeypatch, database_url, timeout
) -> None:
    """[TP-037] [REL-001]
    Коректні тайм-аути не заважають старту, а без DATABASE_URL (in-memory) вони
    не перевіряються; старт не підключається до БД.
    """
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DB_CONNECT_TIMEOUT_SECONDS", timeout)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
