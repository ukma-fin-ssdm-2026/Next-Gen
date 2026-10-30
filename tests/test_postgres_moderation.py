"""Інтеграційні тести модерації на PostgreSQL (FR-011, ADR-002).

Перевіряють те, чого не видно на in-memory сховищі:
- зміна статусу, очищення обраного й запис аудиту комітяться однією транзакцією;
- помилка БД під час запису аудиту відкочує всю транзакцію;
- два паралельні запити на зняття одного оголошення серіалізуються
  рядковим блокуванням SELECT ... FOR UPDATE (get_for_update).

Тести з реальним PostgreSQL пропускаються без DATABASE_URL=postgresql...;
у CI їх запускає job `postgres-migration` після `alembic upgrade head`.
"""

import os
import threading
import time
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.models import Base, ModerationActionRow
from src.domain.categories import Category
from src.domain.exceptions import ListingNotFoundError
from src.domain.favorites import Favorite
from src.domain.listings import Listing, ListingCondition, ListingStatus
from src.domain.users import CurrentUser, User, UserRole
from src.repositories.postgres_categories import PostgresCategoryRepository
from src.repositories.postgres_favorites_moderation import (
    PostgresFavoriteRepository,
    PostgresModerationActionRepository,
)
from src.repositories.postgres_listings import PostgresListingRepository
from src.repositories.postgres_users import PostgresUserRepository
from src.services.moderation import ModerationService

REASON = "Порушення правил маркетплейсу"

requires_postgres = pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").startswith("postgresql"),
    reason="Потрібен реальний PostgreSQL (DATABASE_URL); SQLite не має FOR UPDATE.",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user(role: UserRole = UserRole.USER) -> User:
    return User(
        user_id=uuid.uuid4(),
        tenant_id=uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001"),
        entra_object_id=uuid.uuid4(),
        email=f"mod_{uuid.uuid4().hex[:8]}@ukma.edu.ua",
        display_name="Test User",
        role=role,
    )


def _as_current(user: User) -> CurrentUser:
    return CurrentUser(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        entra_object_id=user.entra_object_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
    )


def _service(session: Session) -> ModerationService:
    """Той самий набір, що get_moderation_service збирає на один HTTP-запит."""
    return ModerationService(
        PostgresListingRepository(session),
        PostgresFavoriteRepository(session),
        PostgresModerationActionRepository(session),
    )


def _seed(session: Session) -> dict[str, object]:
    """Адміністратор, продавець, покупець з оголошенням в обраному."""
    users = PostgresUserRepository(session)
    admin = users.save(_user(UserRole.ADMIN))
    seller = users.save(_user())
    buyer = users.save(_user())
    category_id = uuid.uuid4()
    PostgresCategoryRepository(session).add(
        Category(
            id=category_id,
            name=f"Модерація {category_id.hex[:8]}",
            slug=f"moderation-{category_id.hex[:8]}",
            is_active=True,
            created_at=_now(),
        )
    )
    listing = PostgresListingRepository(session).add(
        Listing(
            title="Оголошення для модерації",
            description="Перевірка транзакції модерації",
            price=100.0,
            category_id=category_id,
            contact="@seller_contact",
            user_id=seller.user_id,
            condition=ListingCondition.GOOD,
            status=ListingStatus.ACTIVE,
        )
    )
    PostgresFavoriteRepository(session).add(
        Favorite(user_id=buyer.user_id, listing_id=listing.id)
    )
    session.commit()
    return {"admin": admin, "buyer": buyer, "listing_id": listing.id}


def _snapshot(engine, listing_id: uuid.UUID, buyer_id: uuid.UUID):
    """Стан у БД, прочитаний окремою сесією (тобто лише закомічене)."""
    with Session(engine) as session:
        listing = PostgresListingRepository(session).get(listing_id)
        favorite = PostgresFavoriteRepository(session).get(buyer_id, listing_id)
        actions = session.scalar(
            select(func.count())
            .select_from(ModerationActionRow)
            .where(ModerationActionRow.listing_id == listing_id)
        )
    return listing.status, favorite is not None, actions


@pytest.fixture(scope="module")
def pg_engine() -> Iterator:
    from alembic import command
    from alembic.config import Config

    url = os.environ["DATABASE_URL"]
    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    yield engine
    engine.dispose()


@requires_postgres
def test_withdraw_commits_status_favorites_and_audit_together(pg_engine) -> None:
    """[TP-031] [FR-011]
    Успішне зняття: після commit у БД WITHDRAWN, обране очищене, один запис аудиту.
    """
    # Arrange
    with Session(pg_engine) as session:
        data = _seed(session)
    # Act: як один HTTP-запит — одна сесія, commit наприкінці
    with Session(pg_engine) as session:
        _service(session).withdraw_listing(
            _as_current(data["admin"]), data["listing_id"], REASON
        )
        session.commit()
    # Assert
    assert _snapshot(pg_engine, data["listing_id"], data["buyer"].user_id) == (
        ListingStatus.WITHDRAWN,
        False,
        1,
    )


@requires_postgres
def test_audit_insert_failure_rolls_back_whole_transaction(pg_engine) -> None:
    """[TP-031] [FR-011]
    Збій запису аудиту в БД (FK модератора) відкочує статус і обране;
    назовні йде саме помилка БД, а не помилка компенсації.
    """
    # Arrange: модератор із роллю ADMIN, якого немає в таблиці users
    with Session(pg_engine) as session:
        data = _seed(session)
    ghost_admin = _as_current(_user(UserRole.ADMIN))
    # Act: як get_db_session — rollback при винятку
    with Session(pg_engine) as session:
        with pytest.raises(IntegrityError):
            _service(session).withdraw_listing(ghost_admin, data["listing_id"], REASON)
        session.rollback()
    # Assert: у БД нічого не змінилось
    assert _snapshot(pg_engine, data["listing_id"], data["buyer"].user_id) == (
        ListingStatus.ACTIVE,
        True,
        0,
    )


class _HoldingListingRepository(PostgresListingRepository):
    """Після SELECT ... FOR UPDATE «думає» 0.5 с, утримуючи блокування рядка."""

    def get_for_update(self, listing_id):
        listing = super().get_for_update(listing_id)
        time.sleep(0.5)
        return listing


@requires_postgres
def test_concurrent_withdrawals_serialize_on_row_lock(pg_engine) -> None:
    """[TP-031] [FR-011]
    Два паралельні запити (окремі сесії) на одне оголошення: успішний один,
    другий чекає на блокування рядка, бачить WITHDRAWN і отримує 404-помилку.
    """
    # Arrange
    with Session(pg_engine) as session:
        data = _seed(session)
    admin = _as_current(data["admin"])
    outcomes: list[str] = []
    start = threading.Barrier(2)

    def request(delay: float, slow: bool) -> None:
        start.wait()
        time.sleep(delay)
        with Session(pg_engine) as session:
            listings = (
                _HoldingListingRepository(session)
                if slow
                else PostgresListingRepository(session)
            )
            service = ModerationService(
                listings,
                PostgresFavoriteRepository(session),
                PostgresModerationActionRepository(session),
            )
            try:
                service.withdraw_listing(admin, data["listing_id"], REASON)
                session.commit()
                outcomes.append("ok")
            except ListingNotFoundError:
                session.rollback()
                outcomes.append("not_found")

    # Act: перший бере блокування й тримає його, другий приходить за 0.1 с
    threads = [
        threading.Thread(target=request, args=(0.0, True)),
        threading.Thread(target=request, args=(0.1, False)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    # Assert
    assert sorted(outcomes) == ["not_found", "ok"]
    assert _snapshot(pg_engine, data["listing_id"], data["buyer"].user_id) == (
        ListingStatus.WITHDRAWN,
        False,
        1,
    )


@requires_postgres
def test_admin_withdraw_api_on_postgres(pg_engine) -> None:
    """[TP-031] [FR-011]
    Через API з реальними Postgres-репозиторіями: 201 і закомічений стан у БД.
    """
    from fastapi.testclient import TestClient

    from src.api import deps
    from src.api.main import app

    with Session(pg_engine) as session:
        data = _seed(session)

    def override_db_session():
        with Session(pg_engine) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[deps.get_db_session] = override_db_session
    app.dependency_overrides[deps.require_current_user] = lambda: _as_current(
        data["admin"]
    )
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/admin/listings/{data['listing_id']}/withdraw",
                json={"reason": REASON},
            )
            repeat = client.post(
                f"/api/v1/admin/listings/{data['listing_id']}/withdraw",
                json={"reason": REASON},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201, response.text
    assert response.json()["moderator_id"] == str(data["admin"].user_id)
    assert repeat.status_code == 404
    assert _snapshot(pg_engine, data["listing_id"], data["buyer"].user_id) == (
        ListingStatus.WITHDRAWN,
        False,
        1,
    )


def test_get_for_update_returns_listing_on_sqlite() -> None:
    """[TP-031] [FR-011]
    get_for_update повертає те саме оголошення, що й get (SQLite ігнорує FOR UPDATE).
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        data = _seed(session)
        repository = PostgresListingRepository(session)
        locked = repository.get_for_update(data["listing_id"])
        assert locked is not None
        assert locked.id == data["listing_id"]
        assert locked.status == ListingStatus.ACTIVE
        assert repository.get_for_update(uuid.uuid4()) is None
    engine.dispose()
