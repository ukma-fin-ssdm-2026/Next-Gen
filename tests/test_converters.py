"""Характеризаційні тести для ORM-Domain конвертерів (Lab 08, Bonus 2).

Ці тести фіксують точну поведінку функцій у src/db/converters.py перед рефакторингом,
гарантуючи, що мапінг сутностей (User, Category, ListingImage, Listing, Favorite,
ModerationAction), обробка existing-рядків, enum-значень та граничних умов
залишаються повністю незмінними.
"""

from datetime import datetime, timezone
from uuid import uuid4

from src.db.converters import (
    category_domain_to_row,
    category_row_to_domain,
    favorite_domain_to_row,
    favorite_row_to_domain,
    image_domain_to_row,
    image_row_to_domain,
    listing_domain_to_row,
    listing_row_to_domain,
    moderation_domain_to_row,
    moderation_row_to_domain,
    user_domain_to_row,
    user_row_to_domain,
)
from src.db.models import (
    CategoryRow,
    FavoriteRow,
    ListingImageRow,
    ListingRow,
    ModerationActionRow,
    UserRow,
)
from src.domain.categories import Category
from src.domain.favorites import Favorite
from src.domain.listings import (
    Listing,
    ListingCondition,
    ListingImage,
    ListingStatus,
)
from src.domain.moderation import ModerationAction, ModerationActionType
from src.domain.users import User, UserRole

# ---------------------------------------------------------------------------
# User Converters
# ---------------------------------------------------------------------------


class TestUserConverters:
    """Тести конвертації між UserRow та User domain."""

    def test_user_row_to_domain_full(self) -> None:
        """[FR-001] [TP-029] Конвертує заповнений UserRow у User domain."""
        user_id = uuid4()
        now = datetime.now(timezone.utc)
        row = UserRow(
            user_id=user_id,
            tenant_id="tenant-123",
            entra_object_id="entra-obj-456",
            email="student@ukma.edu.ua",
            display_name="Оксана Петренко",
            role="USER",
            is_blocked=False,
            display_name_customized=True,
            avatar_url="https://storage.baraholka.ua/avatars/u1.png",
            contact="@oksana_telegram",
            created_at=now,
        )

        user = user_row_to_domain(row)

        assert user.user_id == user_id
        assert user.tenant_id == "tenant-123"
        assert user.entra_object_id == "entra-obj-456"
        assert user.email == "student@ukma.edu.ua"
        assert user.display_name == "Оксана Петренко"
        assert user.role == UserRole.USER
        assert user.is_blocked is False
        assert user.display_name_customized is True
        assert user.avatar_url == "https://storage.baraholka.ua/avatars/u1.png"
        assert user.contact == "@oksana_telegram"
        assert user.created_at == now

    def test_user_row_to_domain_nullable_fields(self) -> None:
        """[FR-001] [TP-029] Конвертує UserRow з nullable полями в User domain."""
        user_id = uuid4()
        now = datetime.now(timezone.utc)
        row = UserRow(
            user_id=user_id,
            tenant_id="tenant-1",
            entra_object_id="entra-1",
            email="admin@ukma.edu.ua",
            display_name="Admin",
            role="ADMIN",
            is_blocked=True,
            display_name_customized=False,
            avatar_url=None,
            contact=None,
            created_at=now,
        )

        user = user_row_to_domain(row)
        assert user.role == UserRole.ADMIN
        assert user.avatar_url is None
        assert user.contact is None
        assert user.is_blocked is True

    def test_user_domain_to_row_new_instance(self) -> None:
        """[FR-001] [TP-029] Створює новий UserRow з User domain об'єкта."""
        user_id = uuid4()
        now = datetime.now(timezone.utc)
        user = User(
            user_id=user_id,
            tenant_id="tenant-9",
            entra_object_id="entra-9",
            email="user@ukma.edu.ua",
            display_name="Студент",
            role=UserRole.USER,
            is_blocked=False,
            display_name_customized=False,
            avatar_url=None,
            contact=None,
            created_at=now,
        )

        row = user_domain_to_row(user)

        assert isinstance(row, UserRow)
        assert row.user_id == user_id
        assert row.role == "USER"
        assert row.email == "user@ukma.edu.ua"
        assert row.created_at == now

    def test_user_domain_to_row_mutates_existing_instance(self) -> None:
        """[FR-001] [TP-029] Мутує існуючий UserRow екземпляр значеннями з User."""
        existing_row = UserRow(
            user_id=uuid4(),
            email="old@ukma.edu.ua",
            display_name="Old Name",
            role="USER",
        )
        now = datetime.now(timezone.utc)
        updated_user = User(
            user_id=existing_row.user_id,
            tenant_id="new-tenant",
            entra_object_id="new-entra",
            email="updated@ukma.edu.ua",
            display_name="New Name",
            role=UserRole.ADMIN,
            is_blocked=False,
            display_name_customized=True,
            avatar_url="https://img.example/a.png",
            contact="@new_contact",
            created_at=now,
        )

        result_row = user_domain_to_row(updated_user, existing=existing_row)

        assert result_row is existing_row
        assert existing_row.email == "updated@ukma.edu.ua"
        assert existing_row.role == "ADMIN"
        assert existing_row.display_name == "New Name"
        assert existing_row.avatar_url == "https://img.example/a.png"

    def test_user_round_trip(self) -> None:
        """[FR-001] [TP-029] Round-trip перетворення User -> UserRow -> User."""
        user_id = uuid4()
        now = datetime.now(timezone.utc)
        original = User(
            user_id=user_id,
            tenant_id="t1",
            entra_object_id="e1",
            email="rt@ukma.edu.ua",
            display_name="Round Trip",
            role=UserRole.USER,
            is_blocked=False,
            display_name_customized=False,
            avatar_url=None,
            contact="contact",
            created_at=now,
        )

        row = user_domain_to_row(original)
        reconstructed = user_row_to_domain(row)

        assert reconstructed == original


# ---------------------------------------------------------------------------
# Category Converters
# ---------------------------------------------------------------------------


class TestCategoryConverters:
    """Тести конвертації між CategoryRow та Category domain."""

    def test_category_row_to_domain(self) -> None:
        """[FR-012] [TP-015] Конвертує CategoryRow в Category domain."""
        cat_id = uuid4()
        now = datetime.now(timezone.utc)
        row = CategoryRow(
            category_id=cat_id,
            name="Книги та підручники",
            slug="books",
            description="Навчальні матеріали та література",
            is_active=True,
            created_at=now,
        )

        cat = category_row_to_domain(row)

        assert cat.id == cat_id
        assert cat.name == "Книги та підручники"
        assert cat.slug == "books"
        assert cat.description == "Навчальні матеріали та література"
        assert cat.is_active is True
        assert cat.created_at == now

    def test_category_domain_to_row_new_and_existing(self) -> None:
        """[FR-012] [TP-015] Конвертує Category в новий або існуючий CategoryRow."""
        cat_id = uuid4()
        now = datetime.now(timezone.utc)
        cat = Category(
            id=cat_id,
            name="Електроніка",
            slug="electronics",
            description=None,
            is_active=False,
            created_at=now,
        )

        # New instance
        new_row = category_domain_to_row(cat)
        assert isinstance(new_row, CategoryRow)
        assert new_row.category_id == cat_id
        assert new_row.is_active is False
        assert new_row.description is None

        # Existing instance mutation
        existing = CategoryRow(category_id=cat_id, name="Old", slug="old")
        returned = category_domain_to_row(cat, existing=existing)
        assert returned is existing
        assert existing.name == "Електроніка"
        assert existing.slug == "electronics"

    def test_category_round_trip(self) -> None:
        """[FR-012] [TP-015] Round-trip перетворення
        Category -> CategoryRow -> Category.
        """
        original = Category(
            id=uuid4(),
            name="Одяг",
            slug="clothing",
            description="Студентський мерч",
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

        row = category_domain_to_row(original)
        reconstructed = category_row_to_domain(row)

        assert reconstructed == original


# ---------------------------------------------------------------------------
# ListingImage Converters
# ---------------------------------------------------------------------------


class TestListingImageConverters:
    """Тести конвертації між ListingImageRow та ListingImage domain."""

    def test_image_row_to_domain(self) -> None:
        """[FR-002] [TP-001] Конвертує ListingImageRow в ListingImage domain."""
        img_id = uuid4()
        listing_id = uuid4()
        row = ListingImageRow(
            image_id=img_id,
            listing_id=listing_id,
            image_url="https://storage.baraholka.ua/img.jpg",
            thumbnail_url="https://storage.baraholka.ua/thumb.jpg",
            storage_key="listings/img.jpg",
            display_order=0,
            width=1600,
            height=1200,
            thumbnail_width=400,
            thumbnail_height=300,
        )

        img = image_row_to_domain(row)

        assert img.image_id == img_id
        assert img.listing_id == listing_id
        assert img.image_url == "https://storage.baraholka.ua/img.jpg"
        assert img.thumbnail_url == "https://storage.baraholka.ua/thumb.jpg"
        assert img.storage_key == "listings/img.jpg"
        assert img.display_order == 0
        assert img.width == 1600
        assert img.height == 1200
        assert img.thumbnail_width == 400
        assert img.thumbnail_height == 300

    def test_image_domain_to_row_new_and_existing(self) -> None:
        """[FR-002] [TP-001] Конвертує ListingImage в новий або існуючий
        ListingImageRow.
        """
        img = ListingImage(
            image_id=uuid4(),
            listing_id=uuid4(),
            image_url="https://example.com/pic.png",
            thumbnail_url=None,
            storage_key="key-123",
            display_order=1,
            width=800,
            height=600,
            thumbnail_width=None,
            thumbnail_height=None,
        )

        # New instance
        row = image_domain_to_row(img)
        assert isinstance(row, ListingImageRow)
        assert row.image_id == img.image_id
        assert row.listing_id == img.listing_id
        assert row.storage_key == "key-123"
        assert row.display_order == 1
        assert row.width == 800
        assert row.thumbnail_url is None

        # Existing instance
        existing = ListingImageRow(image_id=img.image_id, display_order=0)
        mutated = image_domain_to_row(img, existing=existing)
        assert mutated is existing
        assert mutated.display_order == 1

    def test_image_round_trip(self) -> None:
        """[FR-002] [TP-001] Round-trip перетворення
        ListingImage -> ListingImageRow -> ListingImage.
        """
        original = ListingImage(
            image_id=uuid4(),
            listing_id=uuid4(),
            image_url="https://example.com/orig.jpg",
            thumbnail_url="https://example.com/thumb.jpg",
            storage_key="s-key",
            display_order=2,
            width=1024,
            height=768,
            thumbnail_width=256,
            thumbnail_height=192,
        )

        row = image_domain_to_row(original)
        reconstructed = image_row_to_domain(row)

        assert reconstructed == original


# ---------------------------------------------------------------------------
# Listing Converters
# ---------------------------------------------------------------------------


class TestListingConverters:
    """Тести конвертації між ListingRow та Listing domain."""

    def test_listing_row_to_domain_with_images(self) -> None:
        """[FR-002] [TP-001] Конвертує ListingRow з колекцією зображень у Listing."""
        listing_id = uuid4()
        user_id = uuid4()
        cat_id = uuid4()
        now = datetime.now(timezone.utc)

        img_row = ListingImageRow(
            image_id=uuid4(),
            listing_id=listing_id,
            image_url="https://example.com/img1.jpg",
            thumbnail_url=None,
            storage_key="key1",
            display_order=0,
            width=1000,
            height=800,
            thumbnail_width=None,
            thumbnail_height=None,
        )

        row = ListingRow(
            listing_id=listing_id,
            title="Підручник з алгоритмів",
            description="Кормен, 3-тє видання",
            price=450.0,
            category_id=cat_id,
            contact="@student",
            user_id=user_id,
            condition="GOOD",
            status="ACTIVE",
            suggested_category_id=None,
            created_at=now,
            updated_at=now,
            images=[img_row],
        )

        listing = listing_row_to_domain(row)

        assert listing.id == listing_id
        assert listing.title == "Підручник з алгоритмів"
        assert listing.price == 450.0
        assert listing.condition == ListingCondition.GOOD
        assert listing.status == ListingStatus.ACTIVE
        assert len(listing.images) == 1
        assert listing.images[0].image_url == "https://example.com/img1.jpg"

    def test_listing_row_to_domain_empty_images(self) -> None:
        """[FR-002] [TP-001] Конвертує ListingRow без зображень у Listing."""
        listing_id = uuid4()
        now = datetime.now(timezone.utc)
        row = ListingRow(
            listing_id=listing_id,
            title="Без фото",
            description="Опис",
            price=100.0,
            category_id=uuid4(),
            contact="contact",
            user_id=uuid4(),
            condition="LIKE_NEW",
            status="WITHDRAWN",
            suggested_category_id=None,
            created_at=now,
            updated_at=now,
            images=[],
        )

        listing = listing_row_to_domain(row)
        assert listing.images == []

    def test_listing_domain_to_row_new_and_existing(self) -> None:
        """[FR-002] [TP-001] Конвертує Listing у новий або існуючий ListingRow."""
        listing_id = uuid4()
        cat_id = uuid4()
        user_id = uuid4()
        sug_id = uuid4()
        now = datetime.now(timezone.utc)

        listing = Listing(
            id=listing_id,
            title="Ноутбук",
            description="ThinkPad T480",
            price=12000.0,
            category_id=cat_id,
            contact="telegram @tech",
            user_id=user_id,
            condition=ListingCondition.GOOD,
            status=ListingStatus.WITHDRAWN,
            images=[],
            suggested_category_id=sug_id,
            created_at=now,
            updated_at=now,
        )

        # New instance
        row = listing_domain_to_row(listing)
        assert isinstance(row, ListingRow)
        assert row.listing_id == listing_id
        assert row.condition == "GOOD"
        assert row.status == "WITHDRAWN"
        assert row.suggested_category_id == sug_id

        # Existing mutation
        existing = ListingRow(listing_id=listing_id, title="Old Title")
        mutated = listing_domain_to_row(listing, existing=existing)
        assert mutated is existing
        assert mutated.title == "Ноутбук"
        assert mutated.price == 12000.0


# ---------------------------------------------------------------------------
# Favorite Converters
# ---------------------------------------------------------------------------


class TestFavoriteConverters:
    """Тести конвертації між FavoriteRow та Favorite domain."""

    def test_favorite_row_to_domain(self) -> None:
        """[FR-009] [TP-012] Конвертує FavoriteRow у Favorite domain."""
        user_id = uuid4()
        listing_id = uuid4()
        now = datetime.now(timezone.utc)
        row = FavoriteRow(user_id=user_id, listing_id=listing_id, created_at=now)

        fav = favorite_row_to_domain(row)

        assert fav.user_id == user_id
        assert fav.listing_id == listing_id
        assert fav.created_at == now

    def test_favorite_domain_to_row_new_and_existing(self) -> None:
        """[FR-009] [TP-012] Конвертує Favorite у новий або існуючий FavoriteRow."""
        user_id = uuid4()
        listing_id = uuid4()
        now = datetime.now(timezone.utc)
        fav = Favorite(user_id=user_id, listing_id=listing_id, created_at=now)

        # New instance
        row = favorite_domain_to_row(fav)
        assert isinstance(row, FavoriteRow)
        assert row.user_id == user_id
        assert row.listing_id == listing_id

        # Existing instance
        existing = FavoriteRow(user_id=user_id, listing_id=listing_id)
        mutated = favorite_domain_to_row(fav, existing=existing)
        assert mutated is existing
        assert mutated.created_at == now

    def test_favorite_round_trip(self) -> None:
        """[FR-009] [TP-012] Round-trip перетворення
        Favorite -> FavoriteRow -> Favorite.
        """
        original = Favorite(
            user_id=uuid4(),
            listing_id=uuid4(),
            created_at=datetime.now(timezone.utc),
        )

        row = favorite_domain_to_row(original)
        reconstructed = favorite_row_to_domain(row)

        assert reconstructed == original


# ---------------------------------------------------------------------------
# ModerationAction Converters
# ---------------------------------------------------------------------------


class TestModerationActionConverters:
    """Тести конвертації між ModerationActionRow та ModerationAction domain."""

    def test_moderation_row_to_domain(self) -> None:
        """[FR-011] [TP-020] Конвертує ModerationActionRow у ModerationAction domain."""
        action_id = uuid4()
        mod_id = uuid4()
        target_id = uuid4()
        now = datetime.now(timezone.utc)
        row = ModerationActionRow(
            action_id=action_id,
            moderator_id=mod_id,
            action_type="BLOCK_USER",
            reason="Спам у контактних даних",
            listing_id=None,
            target_user_id=target_id,
            suggestion_id=None,
            created_at=now,
        )

        action = moderation_row_to_domain(row)

        assert action.id == action_id
        assert action.moderator_id == mod_id
        assert action.action_type == ModerationActionType.BLOCK_USER
        assert action.reason == "Спам у контактних даних"
        assert action.target_user_id == target_id
        assert action.listing_id is None
        assert action.created_at == now

    def test_moderation_domain_to_row_new_and_existing(self) -> None:
        """[FR-011] [TP-020] Конвертує ModerationAction у новий або існуючий
        ModerationActionRow.
        """
        action = ModerationAction(
            id=uuid4(),
            moderator_id=uuid4(),
            action_type=ModerationActionType.WITHDRAW_LISTING,
            reason="Неприйнятний контент",
            listing_id=uuid4(),
            target_user_id=None,
            suggestion_id=None,
            created_at=datetime.now(timezone.utc),
        )

        # New instance
        row = moderation_domain_to_row(action)
        assert isinstance(row, ModerationActionRow)
        assert row.action_type == "WITHDRAW_LISTING"
        assert row.reason == "Неприйнятний контент"

        # Existing instance
        existing = ModerationActionRow(action_id=action.id)
        mutated = moderation_domain_to_row(action, existing=existing)
        assert mutated is existing
        assert mutated.action_type == "WITHDRAW_LISTING"

    def test_moderation_round_trip(self) -> None:
        """[FR-011] [TP-020] Round-trip перетворення
        ModerationAction -> ModerationActionRow -> ModerationAction.
        """
        original = ModerationAction(
            id=uuid4(),
            moderator_id=uuid4(),
            action_type=ModerationActionType.APPROVE_CATEGORY,
            reason="Відповідає правилам",
            listing_id=None,
            target_user_id=None,
            suggestion_id=uuid4(),
            created_at=datetime.now(timezone.utc),
        )

        row = moderation_domain_to_row(original)
        reconstructed = moderation_row_to_domain(row)

        assert reconstructed == original
