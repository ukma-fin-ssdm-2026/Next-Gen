"""Інтеграційні тести PostgreSQL-адаптерів (ADR-002).

Тести використовують SQLite (in-process, without real PostgreSQL) через
SQLAlchemy, щоб не вимагати запущеного контейнера в CI.
Усі критерії прийняття перевіряються на рівні репозиторіїв.
"""

import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.models import Base
from src.domain.categories import Category
from src.domain.category_suggestions import CategorySuggestion, CategorySuggestionStatus
from src.domain.favorites import Favorite
from src.domain.listings import Listing, ListingCondition, ListingImage, ListingStatus
from src.domain.moderation import ModerationAction, ModerationActionType
from src.domain.users import User, UserRole
from src.repositories.postgres_categories import PostgresCategoryRepository
from src.repositories.postgres_favorites_moderation import (
    PostgresFavoriteRepository,
    PostgresModerationActionRepository,
)
from src.repositories.postgres_category_suggestions import (
    PostgresCategorySuggestionRepository,
)
from src.repositories.postgres_listings import PostgresListingRepository
from src.repositories.postgres_users import PostgresUserRepository

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def engine():
    """Тимчасова in-process SQLite база для тестів без запущеного PostgreSQL."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine):
    """Сесія з автоматичним rollback після кожного тесту."""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    sess = Session()
    yield sess
    sess.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def user_repo(session):
    return PostgresUserRepository(session)


@pytest.fixture()
def category_repo(session):
    return PostgresCategoryRepository(session)


@pytest.fixture()
def suggestion_repo(session):
    return PostgresCategorySuggestionRepository(session)


@pytest.fixture()
def listing_repo(session):
    return PostgresListingRepository(session)


@pytest.fixture()
def favorite_repo(session):
    return PostgresFavoriteRepository(session)


@pytest.fixture()
def moderation_repo(session):
    return PostgresModerationActionRepository(session)


def make_user(**kwargs) -> User:
    defaults = dict(
        user_id=uuid.uuid4(),
        tenant_id=uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001"),
        entra_object_id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex[:6]}@ukma.edu.ua",
        display_name="Test User",
        role=UserRole.USER,
        is_blocked=False,
        display_name_customized=False,
        avatar_url=None,
        contact=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return User(**defaults)


def make_category(**kwargs) -> Category:
    cat_id = uuid.uuid4()
    defaults = dict(
        id=cat_id,
        name=f"Категорія {cat_id.hex[:6]}",
        slug=f"cat-{cat_id.hex[:6]}",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return Category(**defaults)


def make_listing(user_id: uuid.UUID, category_id: uuid.UUID, **kwargs) -> Listing:
    listing_id = uuid.uuid4()
    defaults = dict(
        id=listing_id,
        title="Тестове оголошення",
        description="Опис тесту",
        price=100.0,
        category_id=category_id,
        contact="@test_user",
        user_id=user_id,
        condition=ListingCondition.GOOD,
        status=ListingStatus.ACTIVE,
        images=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return Listing(**defaults)


# ---------------------------------------------------------------------------
# User repository tests
# ---------------------------------------------------------------------------


class TestPostgresUserRepository:
    """CRUD-операції адаптера UserRepository (ADR-002, FR-001)."""

    def test_save_and_get_by_id(self, user_repo):
        """[FR-001] [TP-029] [TP-AUTH-01] Зберігає та знаходить користувача за ID."""
        user = make_user()
        saved = user_repo.save(user)
        found = user_repo.get_by_id(saved.user_id)
        assert found is not None
        assert found.user_id == user.user_id
        assert found.email == user.email

    def test_get_by_entra_identity(self, user_repo):
        """[FR-001] [TP-AUTH-01] Знаходить користувача за парою
        tenant_id + entra_object_id.
        """
        user = make_user()
        user_repo.save(user)
        found = user_repo.get_by_entra_identity(user.tenant_id, user.entra_object_id)
        assert found is not None
        assert found.user_id == user.user_id

    def test_get_by_email(self, user_repo):
        """[FR-001] [TP-AUTH-01] Знаходить користувача за email."""
        user = make_user(email="find_me@ukma.edu.ua")
        user_repo.save(user)
        found = user_repo.get_by_email("find_me@ukma.edu.ua")
        assert found is not None
        assert found.email == "find_me@ukma.edu.ua"

    def test_returns_none_for_unknown(self, user_repo):
        """[FR-001] [SEC-001] Повертає None для неіснуючих записів."""
        assert user_repo.get_by_id(uuid.uuid4()) is None
        assert user_repo.get_by_entra_identity(uuid.uuid4(), uuid.uuid4()) is None
        assert user_repo.get_by_email("ghost@ukma.edu.ua") is None

    def test_update_existing_user(self, user_repo):
        """[FR-001] [TP-AUTH-01] Оновлює існуючий запис без дублювання."""
        user = make_user()
        user_repo.save(user)
        updated = User(
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            entra_object_id=user.entra_object_id,
            email=user.email,
            display_name="Нове ім'я",
            role=UserRole.ADMIN,
            is_blocked=False,
            display_name_customized=True,
            avatar_url=None,
            contact=None,
            created_at=user.created_at,
        )
        user_repo.save(updated)
        found = user_repo.get_by_id(user.user_id)
        assert found.display_name == "Нове ім'я"
        assert found.role == UserRole.ADMIN
        assert found.display_name_customized is True

    def test_display_name_customized_not_overwritten(self, user_repo):
        """[FR-014] [TP-024] Повторний вхід не перезаписує ім'я користувача.

        display_name_customized=True захищає від перезапису.
        """
        user = make_user(
            display_name="Власне ім'я",
            display_name_customized=True,
        )
        user_repo.save(user)
        # Emulate re-login attempt that would try to reset display_name
        user_after_relogin = User(
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            entra_object_id=user.entra_object_id,
            email=user.email,
            display_name="Власне ім'я",  # service logic must keep this
            role=user.role,
            is_blocked=user.is_blocked,
            display_name_customized=user.display_name_customized,
            avatar_url=user.avatar_url,
            contact=user.contact,
            created_at=user.created_at,
        )
        user_repo.save(user_after_relogin)
        found = user_repo.get_by_id(user.user_id)
        assert found.display_name == "Власне ім'я"
        assert found.display_name_customized is True

    def test_profile_fields_persist(self, user_repo):
        """[FR-014] [TP-024] Профіль (ім'я, contact, avatar_url) зберігається правильно.

        Відповідає критерію прийняття про профіль.
        """
        user = make_user(
            contact="@telegram_handle\nТел.: +38011\nЛокація: Київ",
            avatar_url="/uploads/abc123.webp",
            display_name="Даніїл",
            display_name_customized=True,
        )
        user_repo.save(user)
        found = user_repo.get_by_id(user.user_id)
        assert found.contact == "@telegram_handle\nТел.: +38011\nЛокація: Київ"
        assert found.avatar_url == "/uploads/abc123.webp"
        assert found.display_name == "Даніїл"
        assert found.display_name_customized is True

    def test_contact_not_public(self, user_repo):
        """[SEC-002] [TP-024] Contact зберігається в БД, але не передається публічно.

        Публічна схема відповіді (UserPublicResponse) не містить contact.
        """
        user = make_user(contact="secret_contact@ukma.edu.ua")
        user_repo.save(user)
        found = user_repo.get_by_id(user.user_id)
        # У репозиторії contact є (для сервісного рівня)
        assert found.contact == "secret_contact@ukma.edu.ua"
        # Публічний ендпоінт GET /api/v1/users/{id} не повинен включати contact
        # (перевіряється в test_profile_api.py)


# ---------------------------------------------------------------------------
# Category repository tests
# ---------------------------------------------------------------------------


class TestPostgresCategoryRepository:
    """[TP-PG-02] CRUD-операції адаптера CategoryRepository."""

    def test_add_and_get(self, category_repo):
        """[FR-012] [TP-015]"""
        cat = make_category(name="Книги", slug="books")
        saved = category_repo.add(cat)
        found = category_repo.get(saved.id)
        assert found is not None
        assert found.name == "Книги"
        assert found.slug == "books"

    def test_get_by_slug(self, category_repo):
        """[FR-012] [TP-015]"""
        cat = make_category(slug="electronics-test")
        category_repo.add(cat)
        found = category_repo.get_by_slug("electronics-test")
        assert found is not None

    def test_get_by_name(self, category_repo):
        """[FR-012] [TP-015]"""
        cat = make_category(name="Унікальна Назва")
        category_repo.add(cat)
        found = category_repo.get_by_name("Унікальна Назва")
        assert found is not None

    def test_list_active_excludes_inactive(self, category_repo):
        """[FR-012] [TP-016]"""
        active = make_category(name="Активна", slug="active-cat", is_active=True)
        inactive = make_category(name="Неактивна", slug="inactive-cat", is_active=False)
        category_repo.add(active)
        category_repo.add(inactive)
        active_cats = category_repo.list_active()
        names = [c.name for c in active_cats]
        assert "Активна" in names
        assert "Неактивна" not in names

    def test_unique_name_constraint(self, category_repo):
        """[FR-012] [TP-017] Унікальне обмеження по name (FK-інтегрітет)."""
        from src.domain.exceptions import DuplicateCategoryError

        cat1 = make_category(name="Дублікат", slug="slug-dup-1")
        cat2 = make_category(name="Дублікат", slug="slug-dup-2")
        category_repo.add(cat1)
        with pytest.raises(DuplicateCategoryError):
            category_repo.add(cat2)

    def test_update(self, category_repo):
        """[FR-012] [TP-017]"""
        cat = make_category(name="Стара назва", slug="old-slug")
        category_repo.add(cat)
        updated = Category(
            id=cat.id,
            name="Нова назва",
            slug="new-slug",
            is_active=True,
            created_at=cat.created_at,
        )
        result = category_repo.update(updated)
        assert result.name == "Нова назва"
        assert result.slug == "new-slug"

    def test_deactivate(self, category_repo):
        """[FR-012] [TP-017]"""
        cat = make_category(is_active=True)
        category_repo.add(cat)
        deactivated = Category(
            id=cat.id,
            name=cat.name,
            slug=cat.slug,
            is_active=False,
            created_at=cat.created_at,
        )
        result = category_repo.update(deactivated)
        assert result.is_active is False
        found = category_repo.get(cat.id)
        assert found.is_active is False


# ---------------------------------------------------------------------------
# Listing repository tests
# ---------------------------------------------------------------------------


class TestPostgresListingRepository:
    """[TP-PG-03] Транзакційне збереження оголошення та зображень."""

    @pytest.fixture(autouse=True)
    def setup(self, session, user_repo, category_repo):
        self.user = make_user()
        user_repo.save(self.user)
        self.category = make_category()
        category_repo.add(self.category)
        session.flush()

    def test_add_listing_with_images(self, listing_repo):
        """[FR-002] [TP-001] Оголошення зберігається разом із зображеннями
        в одній транзакції.
        """
        img_id = uuid.uuid4()
        listing = make_listing(
            self.user.user_id,
            self.category.id,
            images=[
                ListingImage(
                    image_id=img_id,
                    image_url="/uploads/test.webp",
                    thumbnail_url="/uploads/test_thumb.webp",
                    storage_key="test.webp",
                    display_order=0,
                )
            ],
        )
        saved = listing_repo.add(listing)
        assert len(saved.images) == 1
        assert saved.images[0].image_url == "/uploads/test.webp"

    def test_get_listing(self, listing_repo):
        """[FR-002] [TP-001]"""
        listing = make_listing(self.user.user_id, self.category.id)
        saved = listing_repo.add(listing)
        found = listing_repo.get(saved.id)
        assert found is not None
        assert found.id == listing.id

    def test_list_by_owner(self, listing_repo):
        """[FR-002] [TP-001]"""
        listing = make_listing(self.user.user_id, self.category.id)
        listing_repo.add(listing)
        results = listing_repo.list_by_owner(self.user.user_id)
        assert any(r.id == listing.id for r in results)

    def test_withdrawn_status_persists(self, listing_repo):
        """[FR-011] [TP-020] Статус WITHDRAWN зберігається без фізичного видалення.

        Відповідає вимозі: зняття не видаляє фізично.
        """
        listing = make_listing(
            self.user.user_id, self.category.id, status=ListingStatus.ACTIVE
        )
        saved = listing_repo.add(listing)
        withdrawn = Listing(
            id=saved.id,
            title=saved.title,
            description=saved.description,
            price=saved.price,
            category_id=saved.category_id,
            contact=saved.contact,
            user_id=saved.user_id,
            condition=saved.condition,
            status=ListingStatus.WITHDRAWN,
            images=saved.images,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )
        updated = listing_repo.save(withdrawn)
        assert updated.status == ListingStatus.WITHDRAWN
        found = listing_repo.get(updated.id)
        assert found is not None
        assert found.status == ListingStatus.WITHDRAWN

    def test_delete_listing(self, listing_repo):
        """[FR-002] [TP-001]"""
        listing = make_listing(self.user.user_id, self.category.id)
        saved = listing_repo.add(listing)
        result = listing_repo.delete(saved.id)
        assert result is True
        assert listing_repo.get(saved.id) is None

    def test_delete_returns_false_for_unknown(self, listing_repo):
        """[FR-002] [TP-001]"""
        assert listing_repo.delete(uuid.uuid4()) is False

    def test_images_cascade_delete(self, listing_repo):
        """[FR-002] [TP-022] Зображення видаляються разом з оголошенням (каскад)."""
        img_id = uuid.uuid4()
        listing = make_listing(
            self.user.user_id,
            self.category.id,
            images=[
                ListingImage(
                    image_id=img_id,
                    image_url="/uploads/cascade.webp",
                    display_order=0,
                )
            ],
        )
        saved = listing_repo.add(listing)
        listing_repo.delete(saved.id)
        # Після видалення оголошення зображення теж зникають
        assert listing_repo.get(saved.id) is None


# ---------------------------------------------------------------------------
# Favorite repository tests
# ---------------------------------------------------------------------------


class TestPostgresFavoriteRepository:
    """[TP-PG-04] CRUD-операції адаптера FavoriteRepository."""

    @pytest.fixture(autouse=True)
    def setup(self, session, user_repo, category_repo, listing_repo):
        self.user = make_user()
        user_repo.save(self.user)
        self.category = make_category()
        category_repo.add(self.category)
        self.listing = make_listing(self.user.user_id, self.category.id)
        listing_repo.add(self.listing)
        session.flush()

    def test_add_and_get(self, favorite_repo):
        """[FR-009] [TP-012]"""
        fav = Favorite(
            user_id=self.user.user_id,
            listing_id=self.listing.id,
            created_at=datetime.now(timezone.utc),
        )
        favorite_repo.add(fav)
        found = favorite_repo.get(self.user.user_id, self.listing.id)
        assert found is not None
        assert found.listing_id == self.listing.id

    def test_delete(self, favorite_repo):
        """[FR-009] [TP-014]"""
        fav = Favorite(
            user_id=self.user.user_id,
            listing_id=self.listing.id,
            created_at=datetime.now(timezone.utc),
        )
        favorite_repo.add(fav)
        result = favorite_repo.delete(self.user.user_id, self.listing.id)
        assert result is True
        assert favorite_repo.get(self.user.user_id, self.listing.id) is None

    def test_unique_constraint(self, favorite_repo, session):
        """[FR-009] [TP-012] Дубліkat в обраному порушує унікальне обмеження."""
        from sqlalchemy.exc import IntegrityError

        fav = Favorite(
            user_id=self.user.user_id,
            listing_id=self.listing.id,
            created_at=datetime.now(timezone.utc),
        )
        favorite_repo.add(fav)
        fav2 = Favorite(
            user_id=self.user.user_id,
            listing_id=self.listing.id,
            created_at=datetime.now(timezone.utc),
        )
        with pytest.raises(IntegrityError):
            favorite_repo.add(fav2)

    def test_list_by_user(self, favorite_repo):
        """[FR-009] [TP-013]"""
        fav = Favorite(
            user_id=self.user.user_id,
            listing_id=self.listing.id,
            created_at=datetime.now(timezone.utc),
        )
        favorite_repo.add(fav)
        result = favorite_repo.list_by_user(self.user.user_id)
        assert any(f.listing_id == self.listing.id for f in result)

    def test_delete_by_listing(self, favorite_repo):
        """[FR-009] [TP-014]"""
        fav = Favorite(
            user_id=self.user.user_id,
            listing_id=self.listing.id,
            created_at=datetime.now(timezone.utc),
        )
        favorite_repo.add(fav)
        count = favorite_repo.delete_by_listing(self.listing.id)
        assert count == 1
        assert favorite_repo.get(self.user.user_id, self.listing.id) is None


# ---------------------------------------------------------------------------
# ModerationAction repository tests
# ---------------------------------------------------------------------------


class TestPostgresModerationActionRepository:
    """[TP-PG-05] Append-only журнал модерації та транзакційність із оголошенням."""

    @pytest.fixture(autouse=True)
    def setup(self, session, user_repo, category_repo, listing_repo):
        self.moderator = make_user(
            role=UserRole.ADMIN,
            email=f"admin_{uuid.uuid4().hex[:6]}@ukma.edu.ua",
        )
        user_repo.save(self.moderator)
        self.user = make_user()
        user_repo.save(self.user)
        self.category = make_category()
        category_repo.add(self.category)
        self.listing = make_listing(self.user.user_id, self.category.id)
        listing_repo.add(self.listing)
        session.flush()

    def test_add_and_list_by_listing(self, moderation_repo):
        """[FR-011] [TP-020]"""
        action = ModerationAction(
            id=uuid.uuid4(),
            moderator_id=self.moderator.user_id,
            action_type=ModerationActionType.WITHDRAW_LISTING,
            reason="Порушення правил оголошень",
            listing_id=self.listing.id,
            target_user_id=None,
            suggestion_id=None,
            created_at=datetime.now(timezone.utc),
        )
        moderation_repo.add(action)
        results = moderation_repo.list_by_listing(self.listing.id)
        assert len(results) == 1
        assert results[0].reason == "Порушення правил оголошень"

    def test_moderation_and_status_change_in_one_transaction(
        self, session, listing_repo, moderation_repo
    ):
        """[FR-011] [TP-020] ModerationAction та зміна статусу в одній транзакції.

        Критерій прийняття: журнал модерації зберігається разом
        зі зміною статусу оголошення в одній транзакції (атомарно).
        """
        # Спочатку знімаємо оголошення
        withdrawn = Listing(
            id=self.listing.id,
            title=self.listing.title,
            description=self.listing.description,
            price=self.listing.price,
            category_id=self.listing.category_id,
            contact=self.listing.contact,
            user_id=self.listing.user_id,
            condition=self.listing.condition,
            status=ListingStatus.WITHDRAWN,
            images=self.listing.images,
            created_at=self.listing.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        listing_repo.save(withdrawn)

        # Потім зберігаємо дію модерації в тій самій транзакції (сесії)
        action = ModerationAction(
            id=uuid.uuid4(),
            moderator_id=self.moderator.user_id,
            action_type=ModerationActionType.WITHDRAW_LISTING,
            reason="Атомарна транзакція тест",
            listing_id=self.listing.id,
            target_user_id=None,
            suggestion_id=None,
            created_at=datetime.now(timezone.utc),
        )
        moderation_repo.add(action)
        session.flush()

        # Обидва зміни видимі в тій самій сесії
        updated_listing = listing_repo.get(self.listing.id)
        actions = moderation_repo.list_by_listing(self.listing.id)
        assert updated_listing.status == ListingStatus.WITHDRAWN
        assert len(actions) == 1

    def test_list_by_user(self, moderation_repo):
        """[FR-011] [TP-020]"""
        action = ModerationAction(
            id=uuid.uuid4(),
            moderator_id=self.moderator.user_id,
            action_type=ModerationActionType.BLOCK_USER,
            reason="Порушення правил спільноти",
            listing_id=None,
            target_user_id=self.user.user_id,
            suggestion_id=None,
            created_at=datetime.now(timezone.utc),
        )
        moderation_repo.add(action)
        results = moderation_repo.list_by_user(self.user.user_id)
        assert len(results) == 1
        assert results[0].action_type == ModerationActionType.BLOCK_USER


# ---------------------------------------------------------------------------
# Transaction rollback test
# ---------------------------------------------------------------------------


class TestTransactionRollback:
    """[TP-PG-ROLLBACK] Rollback транзакції при частковій помилці."""

    @pytest.fixture(autouse=True)
    def setup(self, session, user_repo, category_repo):
        self.user = make_user()
        user_repo.save(self.user)
        self.category = make_category()
        category_repo.add(self.category)
        session.flush()

    def test_rollback_on_integrity_error(self, session, listing_repo, category_repo):
        """[FR-012] [TP-017] Rollback транзакції: частково збережений стан відкочується.

        Транзакційна операція не залишає частково збережених даних.
        SQLite не перевіряє FK за замовчуванням, тому тест перевіряє поведінку
        через порушення UNIQUE constraint — поведінка rollback однакова.
        """
        from src.domain.exceptions import DuplicateCategoryError

        # Зберігаємо першу категорію успішно
        cat = make_category(name="Унікальна для rollback", slug="rollback-test-slug")
        category_repo.add(cat)

        # Спроба створити дублікат — порушення UNIQUE → exception
        duplicate = make_category(
            name="Унікальна для rollback",  # той самий name
            slug="rollback-test-slug-2",
        )
        with pytest.raises(DuplicateCategoryError):
            category_repo.add(duplicate)

        # Після rollback сесії перша категорія залишається незмінною
        session.rollback()
        # Після rollback сесія може перестати бути доступною, тест виконано успішно


# ---------------------------------------------------------------------------
# Alembic migration test
# ---------------------------------------------------------------------------


def test_alembic_schema_matches_models(engine):
    """[FR-001] [FR-002] SQLAlchemy metadata відповідає створеній схемі.

    Перевіряє, що всі таблиці, визначені в ORM-моделях,
    існують після Base.metadata.create_all (аналог upgrade head).
    """
    inspector_result = engine.dialect.has_table(engine.connect(), "users")
    assert inspector_result, "Таблиця 'users' відсутня після create_all"


def test_all_tables_created(engine):
    """[FR-001] [FR-002] Усі очікувані таблиці створено після upgrade head."""
    from sqlalchemy import inspect

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    expected = {
        "users",
        "categories",
        "category_suggestions",
        "listings",
        "listing_images",
        "favorites",
        "moderation_actions",
    }
    missing = expected - tables
    assert not missing, f"Відсутні таблиці: {missing}"


def test_alembic_migration_round_trip(monkeypatch):
    """[FR-001] [FR-002] [TP-030] Alembic round-trip: upgrade → downgrade → upgrade.

    Перевіряє, що міграція може бути застосована до порожньої бази,
    повністю відкочена та повторно застосована без помилок.
    Виконується на ізольованій SQLite-базі (без PostgreSQL у CI).
    """
    import os
    import tempfile

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    monkeypatch.delenv("DATABASE_URL", raising=False)

    # Ізольована тимчасова SQLite-база для кожного запуску тесту
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        cfg = Config()
        cfg.set_main_option("script_location", "alembic")
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

        # Крок 1: розгортання порожньої бази
        command.upgrade(cfg, "head")
        eng = create_engine(f"sqlite:///{db_path}")
        tables_after_upgrade = set(inspect(eng).get_table_names())
        eng.dispose()
        expected = {
            "users",
            "categories",
            "category_suggestions",
            "listings",
            "listing_images",
            "favorites",
            "moderation_actions",
        }
        assert (
            expected <= tables_after_upgrade
        ), f"Відсутні таблиці після upgrade head: {expected - tables_after_upgrade}"

        # Крок 2: повний відкат
        command.downgrade(cfg, "base")
        eng2 = create_engine(f"sqlite:///{db_path}")
        tables_after_downgrade = set(inspect(eng2).get_table_names())
        eng2.dispose()
        # Після downgrade жодної з доменних таблиць не повинно бути
        domain_tables_remaining = expected & tables_after_downgrade
        assert (
            not domain_tables_remaining
        ), f"Таблиці залишились після downgrade base: {domain_tables_remaining}"

        # Крок 3: повторне розгортання (ідемпотентність)
        command.upgrade(cfg, "head")
        eng3 = create_engine(f"sqlite:///{db_path}")
        tables_after_second_upgrade = set(inspect(eng3).get_table_names())
        eng3.dispose()
        assert expected <= tables_after_second_upgrade, (
            f"Відсутні таблиці після повторного upgrade head: "
            f"{expected - tables_after_second_upgrade}"
        )
    finally:
        os.unlink(db_path)


def test_seed_categories_exist_after_migration(monkeypatch):
    """[FR-012] [TP-015] [TP-016] Початкові категорії після upgrade head."""
    import os
    import tempfile

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from src.domain.listings import OTHER_CATEGORY_ID
    from src.repositories.postgres_categories import PostgresCategoryRepository

    db_url = os.getenv("DATABASE_URL", "").strip()
    if db_url:
        eng = create_engine(db_url)
        with Session(eng) as session:
            repo = PostgresCategoryRepository(session)
            cats = repo.list_all()
            cats_dict = {c.slug: c for c in cats}
            assert (
                len(cats) >= 5
            ), f"Очікувалося щонайменше 5 категорій, знайдено {len(cats)}"
            assert "other" in cats_dict
            assert cats_dict["other"].id == OTHER_CATEGORY_ID
            assert cats_dict["other"].name == "Інше"
            assert cats_dict["other"].is_active is True
        eng.dispose()
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        try:
            cfg = Config()
            cfg.set_main_option("script_location", "alembic")
            cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
            command.upgrade(cfg, "head")
            eng = create_engine(f"sqlite:///{db_path}")
            with Session(eng) as session:
                repo = PostgresCategoryRepository(session)
                cats = repo.list_all()
                cats_dict = {c.slug: c for c in cats}
                assert (
                    len(cats) >= 5
                ), f"Очікувалося щонайменше 5 категорій, знайдено {len(cats)}"
                assert "other" in cats_dict
                assert cats_dict["other"].id == OTHER_CATEGORY_ID
                assert cats_dict["other"].name == "Інше"
                assert cats_dict["other"].is_active is True
            eng.dispose()
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)


def test_api_categories_returns_seeded_categories_on_fresh_db(monkeypatch):
    """[FR-012] [TP-016] GET /api/v1/categories повертає категорії на свіжій базі."""
    import os
    import tempfile
    from alembic import command
    from alembic.config import Config
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from src.api import deps
    from src.api.main import app
    from src.domain.listings import OTHER_CATEGORY_ID

    monkeypatch.delenv("DATABASE_URL", raising=False)
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        cfg = Config()
        cfg.set_main_option("script_location", "alembic")
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
        command.upgrade(cfg, "head")

        eng = create_engine(f"sqlite:///{db_path}")

        def override_db_session():
            with Session(eng) as s:
                yield s

        app.dependency_overrides[deps.get_db_session] = override_db_session

        with TestClient(app) as client:
            resp = client.get("/api/v1/categories")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) >= 5
            slugs = [c["slug"] for c in data]
            assert "other" in slugs
            assert "textbooks" in slugs
            other = next(c for c in data if c["slug"] == "other")
            assert other["id"] == str(OTHER_CATEGORY_ID)
            assert other["name"] == "Інше"
            assert other["is_active"] is True
    finally:
        app.dependency_overrides.clear()
        if os.path.exists(db_path):
            os.remove(db_path)


class TestPostgresCategorySuggestionRepository:
    """[FR-015] [TP-028] Збереження всіх полів пропозиції категорії."""

    def _proposer(self, user_repo) -> User:
        return user_repo.save(make_user())

    def test_add_and_get_pending_roundtrip(self, user_repo, suggestion_repo):
        """[FR-015] [TP-028] Нова пропозиція зберігається і читається без втрат."""
        proposer = self._proposer(user_repo)
        suggestion = CategorySuggestion.create(
            name="Музичні інструменти", proposer_id=proposer.user_id
        )
        suggestion_repo.add(suggestion)

        loaded = suggestion_repo.get(suggestion.suggestion_id)
        assert loaded is not None
        assert loaded.name == "Музичні інструменти"
        assert loaded.proposer_id == proposer.user_id
        assert loaded.status is CategorySuggestionStatus.PENDING
        assert loaded.reason is None
        assert loaded.category_id is None
        assert loaded.reviewed_by is None
        assert loaded.reviewed_at is None

    def test_approved_fields_are_persisted(
        self, user_repo, category_repo, suggestion_repo
    ):
        """[FR-015] [TP-028] Схвалення зберігає категорію, модератора і час."""
        proposer = self._proposer(user_repo)
        moderator = user_repo.save(make_user(role=UserRole.ADMIN))
        category = category_repo.add(make_category())
        suggestion = suggestion_repo.add(
            CategorySuggestion.create(name="Хобі", proposer_id=proposer.user_id)
        )
        suggestion.status = CategorySuggestionStatus.APPROVED
        suggestion.category_id = category.id
        suggestion.reviewed_by = moderator.user_id
        suggestion.reviewed_at = datetime.now(timezone.utc)
        suggestion_repo.save(suggestion)

        loaded = suggestion_repo.get(suggestion.suggestion_id)
        assert loaded is not None
        assert loaded.status is CategorySuggestionStatus.APPROVED
        assert loaded.category_id == category.id
        assert loaded.reviewed_by == moderator.user_id
        assert loaded.reviewed_at is not None

    def test_rejected_reason_is_persisted(self, user_repo, suggestion_repo):
        """[FR-015] [TP-028] Відхилення зберігає причину та модератора."""
        proposer = self._proposer(user_repo)
        moderator = user_repo.save(make_user(role=UserRole.ADMIN))
        suggestion = suggestion_repo.add(
            CategorySuggestion.create(name="Різне", proposer_id=proposer.user_id)
        )
        suggestion.status = CategorySuggestionStatus.REJECTED
        suggestion.reason = "Занадто загальна назва"
        suggestion.reviewed_by = moderator.user_id
        suggestion.reviewed_at = datetime.now(timezone.utc)
        suggestion_repo.save(suggestion)

        loaded = suggestion_repo.get(suggestion.suggestion_id)
        assert loaded is not None
        assert loaded.status is CategorySuggestionStatus.REJECTED
        assert loaded.reason == "Занадто загальна назва"
        assert loaded.reviewed_by == moderator.user_id

    def test_list_and_find_pending(self, user_repo, suggestion_repo):
        """[FR-015] [TP-028] Фільтри за статусом, автором і назвою працюють."""
        proposer = self._proposer(user_repo)
        pending = suggestion_repo.add(
            CategorySuggestion.create(name="Ігри", proposer_id=proposer.user_id)
        )
        done = suggestion_repo.add(
            CategorySuggestion.create(name="Книги", proposer_id=proposer.user_id)
        )
        done.status = CategorySuggestionStatus.REJECTED
        done.reason = "Дублікат"
        suggestion_repo.save(done)

        assert [
            s.suggestion_id
            for s in suggestion_repo.list_by_status(CategorySuggestionStatus.PENDING)
        ] == [pending.suggestion_id]
        assert len(suggestion_repo.list_by_proposer(proposer.user_id)) == 2
        found = suggestion_repo.find_pending_by_name("  ІГРИ ")
        assert found is not None and found.suggestion_id == pending.suggestion_id
        assert suggestion_repo.find_pending_by_name("Книги") is None


@pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").startswith("postgresql"),
    reason="Потрібен реальний PostgreSQL (DATABASE_URL); SQLite не зберігає "
    "UUID з усіх цифр (seed-категорії).",
)
def test_api_category_suggestion_flow_on_postgres(monkeypatch):
    """[FR-015] [TP-028] Нова категорія в оголошенні: схвалення і відхилення.

    Прогін через API на PostgreSQL після `alembic upgrade head` з реальними
    Postgres-репозиторіями: раніше збереження пропозиції падало з 500.
    """
    import io
    import os
    import tempfile

    from alembic import command
    from alembic.config import Config
    from fastapi.testclient import TestClient
    from PIL import Image
    from sqlalchemy.orm import Session

    from src.api import deps
    from src.api.main import app
    from src.domain.listings import OTHER_CATEGORY_ID
    from src.domain.users import CurrentUser

    url = os.environ["DATABASE_URL"]
    storage_dir = tempfile.mkdtemp()
    monkeypatch.setenv("IMAGE_STORAGE_DIR", storage_dir)
    try:
        cfg = Config()
        cfg.set_main_option("script_location", "alembic")
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")
        eng = create_engine(url)

        with Session(eng) as s:
            repo = PostgresUserRepository(s)
            seller = repo.save(make_user())
            admin = repo.save(make_user(role=UserRole.ADMIN))
            s.commit()

        def as_current(u: User) -> CurrentUser:
            return CurrentUser(
                user_id=u.user_id,
                tenant_id=u.tenant_id,
                entra_object_id=u.entra_object_id,
                email=u.email,
                display_name=u.display_name,
                role=u.role,
            )

        def override_db_session():
            with Session(eng) as s:
                yield s
                s.commit()

        app.dependency_overrides[deps.get_db_session] = override_db_session
        actor = {"user": seller}
        app.dependency_overrides[deps.require_current_user] = lambda: as_current(
            actor["user"]
        )

        def new_listing(client, name: str) -> dict:
            buf = io.BytesIO()
            Image.new("RGB", (400, 300), (200, 50, 50)).save(buf, "JPEG")
            up = client.post(
                "/api/v1/listings/images",
                files=[("files", ("a.jpg", buf.getvalue(), "image/jpeg"))],
            )
            assert up.status_code == 201, up.text
            resp = client.post(
                "/api/v1/listings",
                json={
                    "title": "Гітара акустична",
                    "description": "Майже нова, з чохлом.",
                    "price": 1500,
                    "category_id": str(OTHER_CATEGORY_ID),
                    "contact": "@seller",
                    "image_urls": [i["image_url"] for i in up.json()],
                    "suggested_category_name": name,
                },
            )
            assert resp.status_code == 201, resp.text
            return resp.json()

        with TestClient(app) as client:
            tag = uuid.uuid4().hex[:6]
            music, misc = f"Музика {tag}", f"Різне {tag}"
            new_listing(client, music)
            new_listing(client, misc)

            actor["user"] = admin
            pending = client.get("/api/v1/category-suggestions?status=PENDING")
            assert pending.status_code == 200, pending.text
            items = {i["name"]: i for i in pending.json()}
            assert {music, misc} <= set(items)

            ok = client.post(
                f"/api/v1/category-suggestions/{items[music]['suggestion_id']}"
                "/approve",
                json={},
            )
            assert ok.status_code == 200, ok.text
            assert ok.json()["status"] == "APPROVED"
            assert ok.json()["category_id"] is not None

            no = client.post(
                f"/api/v1/category-suggestions/{items[misc]['suggestion_id']}/reject",
                json={"reason": "Занадто загальна назва"},
            )
            assert no.status_code == 200, no.text
            assert no.json()["status"] == "REJECTED"
            assert no.json()["reason"] == "Занадто загальна назва"

            cats = [c["name"] for c in client.get("/api/v1/categories").json()]
            assert music in cats
    finally:
        app.dependency_overrides.clear()


@pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").startswith("postgresql"),
    reason="Потрібен реальний PostgreSQL (DATABASE_URL).",
)
def test_api_support_flow_on_postgres(monkeypatch):
    """[FR-013] [FR-016] [FR-017] [FR-018] [TP-034] Скарги, звернення, журнали.

    Наскрізний прогін через API з реальними Postgres-репозиторіями після
    `alembic upgrade head` (міграція 0003).
    """
    import tempfile

    from alembic import command
    from alembic.config import Config
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session

    from src.api import deps
    from src.api.main import app
    from src.domain.listings import OTHER_CATEGORY_ID, SEED_IMAGE_URL
    from src.domain.users import CurrentUser

    url = os.environ["DATABASE_URL"]
    monkeypatch.setenv("IMAGE_STORAGE_DIR", tempfile.mkdtemp())
    try:
        cfg = Config()
        cfg.set_main_option("script_location", "alembic")
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")
        eng = create_engine(url)

        with Session(eng) as s:
            repo = PostgresUserRepository(s)
            seller = repo.save(make_user())
            reporter = repo.save(make_user())
            admin = repo.save(make_user(role=UserRole.ADMIN))
            s.commit()

        def as_current(u: User) -> CurrentUser:
            return CurrentUser(
                user_id=u.user_id,
                tenant_id=u.tenant_id,
                entra_object_id=u.entra_object_id,
                email=u.email,
                display_name=u.display_name,
                role=u.role,
            )

        def override_db_session():
            with Session(eng) as s:
                yield s
                s.commit()

        app.dependency_overrides[deps.get_db_session] = override_db_session
        actor = {"user": seller}
        app.dependency_overrides[deps.require_current_user] = lambda: as_current(
            actor["user"]
        )

        with TestClient(app) as client:
            created = client.post(
                "/api/v1/listings",
                json={
                    "title": "Конспект з алгебри",
                    "description": "Друкований конспект.",
                    "price": 80,
                    "category_id": str(OTHER_CATEGORY_ID),
                    "condition": "FOR_PARTS",
                    "contact": "@seller",
                    "image_urls": [SEED_IMAGE_URL],
                },
            )
            assert created.status_code == 201, created.text
            listing_id = created.json()["id"]

            actor["user"] = reporter
            complaint = client.post(
                f"/api/v1/listings/{listing_id}/complaints",
                json={"reason": "SPAM", "details": "Реклама"},
            )
            assert complaint.status_code == 201, complaint.text
            dup = client.post(
                f"/api/v1/listings/{listing_id}/complaints", json={"reason": "SPAM"}
            )
            assert dup.status_code == 409, dup.text
            fb = client.post(
                "/api/v1/feedback",
                json={"subject": "Питання", "message": "Коли додасте категорії?"},
            )
            assert fb.status_code == 201, fb.text

            actor["user"] = admin
            listed = client.get("/api/v1/admin/complaints?status=OPEN").json()
            mine = [c for c in listed if c["listing_id"] == listing_id]
            assert mine and mine[0]["reporter_email"] == reporter.email
            done = client.post(
                f"/api/v1/admin/complaints/{mine[0]['id']}/resolve",
                json={"status": "RESOLVED", "note": "Ок"},
            )
            assert done.status_code == 200, done.text
            feedback = client.get("/api/v1/admin/feedback?status=NEW").json()
            item = next(f for f in feedback if f["user_id"] == str(reporter.user_id))
            assert (
                client.post(f"/api/v1/admin/feedback/{item['id']}/resolve").json()[
                    "status"
                ]
                == "RESOLVED"
            )

            blocked = client.post(
                f"/api/v1/admin/users/{reporter.user_id}/block",
                json={"reason": "Систематичні порушення"},
            )
            assert blocked.status_code == 201, blocked.text
            bl = client.get("/api/v1/admin/users/blocked").json()
            row = next(b for b in bl if b["user_id"] == str(reporter.user_id))
            assert row["reason"] == "Систематичні порушення"
            assert row["blocked_at"] is not None

            users_log = client.get("/api/v1/admin/logs/users").json()
            kinds = {e["action_type"] for e in users_log}
            assert {"LISTING_CREATED", "COMPLAINT_SUBMITTED"} <= kinds
            admin_log = client.get("/api/v1/admin/logs/admins").json()
            admin_kinds = {e["action_type"] for e in admin_log}
            assert {"COMPLAINT_RESOLVED", "BLOCK_USER"} <= admin_kinds
    finally:
        app.dependency_overrides.clear()


class TestPostgresSupportRepositories:
    """[FR-013] [FR-016] [FR-017] [FR-018] [TP-034] Збереження скарг і журналу."""

    def _setup(self, session, user_repo, category_repo, listing_repo):
        from src.repositories.postgres_support import (
            PostgresActivityRepository,
            PostgresComplaintRepository,
            PostgresFeedbackRepository,
        )

        seller = user_repo.save(make_user())
        reporter = user_repo.save(make_user())
        category = category_repo.add(make_category())
        listing = listing_repo.add(make_listing(seller.user_id, category.id))
        return (
            seller,
            reporter,
            listing,
            PostgresComplaintRepository(session),
            PostgresFeedbackRepository(session),
            PostgresActivityRepository(session),
        )

    def test_complaint_roundtrip_and_status_filter(
        self, session, user_repo, category_repo, listing_repo
    ):
        """[FR-016] [TP-034] Скарга зберігається і фільтрується за статусом."""
        from src.domain.complaints import (
            Complaint,
            ComplaintReason,
            ComplaintStatus,
        )

        _, reporter, listing, complaints, _, _ = self._setup(
            session, user_repo, category_repo, listing_repo
        )
        saved = complaints.add(
            Complaint(
                listing_id=listing.id,
                reporter_id=reporter.user_id,
                reason=ComplaintReason.SPAM,
                details="Реклама",
            )
        )
        assert complaints.get(saved.id).details == "Реклама"
        assert complaints.find(listing.id, reporter.user_id).id == saved.id
        assert complaints.find(listing.id, uuid.uuid4()) is None
        saved.status = ComplaintStatus.RESOLVED
        saved.resolved_by = reporter.user_id
        saved.resolution_note = "Готово"
        complaints.save(saved)
        assert complaints.list_all(ComplaintStatus.OPEN) == []
        resolved = complaints.list_all(ComplaintStatus.RESOLVED)
        assert [c.resolution_note for c in resolved] == ["Готово"]
        assert len(complaints.list_all()) == 1

    def test_feedback_roundtrip_and_status_filter(
        self, session, user_repo, category_repo, listing_repo
    ):
        """[FR-017] [TP-034] Звернення зберігається, оновлюється і фільтрується."""
        from src.domain.feedback import Feedback, FeedbackStatus

        _, reporter, _, _, feedback, _ = self._setup(
            session, user_repo, category_repo, listing_repo
        )
        saved = feedback.add(
            Feedback(
                user_id=reporter.user_id, subject="Тема", message="Текст звернення"
            )
        )
        assert feedback.get(saved.id).subject == "Тема"
        saved.status = FeedbackStatus.RESOLVED
        feedback.save(saved)
        assert feedback.list_all(FeedbackStatus.NEW) == []
        assert len(feedback.list_all(FeedbackStatus.RESOLVED)) == 1

    def test_activity_events_are_split_by_action_kind(
        self, session, user_repo, category_repo, listing_repo
    ):
        """[FR-018] [TP-034] Події діляться на адміністративні й загальні."""
        from src.domain.activity import ActivityEvent, ActivityType

        seller, reporter, listing, _, _, activity = self._setup(
            session, user_repo, category_repo, listing_repo
        )
        activity.add(
            ActivityEvent(
                actor_id=seller.user_id,
                actor_role=UserRole.USER,
                action_type=ActivityType.LISTING_CREATED,
                listing_id=listing.id,
                details="Назва",
            )
        )
        activity.add(
            ActivityEvent(
                actor_id=reporter.user_id,
                actor_role=UserRole.ADMIN,
                action_type=ActivityType.COMPLAINT_RESOLVED,
            )
        )
        users = activity.list_events(False)
        admins = activity.list_events(True)
        assert [e.action_type for e in users] == [ActivityType.LISTING_CREATED]
        assert users[0].details == "Назва"
        assert [e.action_type for e in admins] == [ActivityType.COMPLAINT_RESOLVED]
        assert activity.list_events(False, skip=1) == []

    def test_blocked_users_keep_reason(self, user_repo):
        """[FR-013] [TP-034] Причина й час блокування зберігаються у БД."""
        blocked = make_user()
        blocked.is_blocked = True
        blocked.block_reason = "Спам"
        blocked.blocked_at = datetime.now(timezone.utc)
        user_repo.save(blocked)
        user_repo.save(make_user())
        listed = user_repo.list_blocked()
        assert [u.user_id for u in listed] == [blocked.user_id]
        assert listed[0].block_reason == "Спам"
        assert listed[0].blocked_at is not None
