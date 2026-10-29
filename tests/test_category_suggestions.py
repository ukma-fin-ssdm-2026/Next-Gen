"""Unit-тести домену та сервісу пропозицій категорій (FR-015 / US-010)."""

from dataclasses import replace
from uuid import uuid4

import pytest

from src.domain.category_suggestions import (
    CategorySuggestionStatus,
    build_category_slug,
    normalize_suggestion_name,
)
from src.domain.exceptions import (
    CategorySuggestionConflictError,
    CategorySuggestionNotFoundError,
    CategorySuggestionQuotaError,
    DuplicateCategorySuggestionError,
    InvalidCategorySuggestionError,
    InvalidModerationReasonError,
    ListingForbiddenError,
    ListingUnauthorizedError,
    ModerationForbiddenError,
)
from src.domain.listings import (
    OTHER_CATEGORY_ID,
    SEED_CATEGORY_ID,
    SEED_IMAGE_URL,
    ListingStatus,
)
from src.domain.moderation import ModerationActionType
from src.domain.users import CurrentUser, User, UserRole
from src.repositories.categories import InMemoryCategoryRepository
from src.repositories.category_suggestions import (
    InMemoryCategorySuggestionRepository,
)
from src.repositories.image_storage import InMemoryImageStorage
from src.repositories.listings import InMemoryListingRepository
from src.repositories.moderation import InMemoryModerationActionRepository
from src.services.categories import CategoryService
from src.services.category_suggestions import CategorySuggestionService
from src.services.listings import ListingService


def _make_user(
    role: UserRole = UserRole.USER, is_blocked: bool = False
) -> CurrentUser | User:
    if is_blocked:
        return User(
            user_id=uuid4(),
            tenant_id=uuid4(),
            entra_object_id=uuid4(),
            email="blocked@ukma.edu.ua",
            display_name="Blocked Student",
            role=role,
            is_blocked=True,
        )
    return CurrentUser(
        user_id=uuid4(),
        tenant_id=uuid4(),
        entra_object_id=uuid4(),
        email="student@ukma.edu.ua",
        display_name="Student",
        role=role,
    )


def test_normalize_and_slug_validation() -> None:
    """[TP-026] [TP-028] [FR-015] [US-010] Валідація назви та slug."""
    assert normalize_suggestion_name("  Музичні інструменти  ") == "Музичні інструменти"
    assert build_category_slug("Музичні інструменти") == "muzychni-instrumenty"

    for invalid in ("", " ", "А", "x" * 41, "Назва\x00", "Назва\nНова", "Назва\x7f"):
        with pytest.raises(InvalidCategorySuggestionError):
            normalize_suggestion_name(invalid)


def test_submit_and_quota_and_duplicates(
    category_suggestion_service: CategorySuggestionService,
    category_service: CategoryService,
) -> None:
    """[TP-026] [TP-028] [FR-015] [US-010] Дублікати категорій та ліміт 3 PENDING."""
    seller = _make_user()

    # Дублікат існуючої активної категорії (без урахування регістру та пробілів)
    with pytest.raises(DuplicateCategorySuggestionError) as exc_info:
        category_suggestion_service.submit(seller, "  інШЕ ")
    assert str(OTHER_CATEGORY_ID) in str(exc_info.value)

    # Дублікат деактивованої категорії
    deactivated = category_service.create(name="Архівні речі", slug="archive-items")
    category_service.deactivate(deactivated.id)
    with pytest.raises(DuplicateCategorySuggestionError) as deact_exc:
        category_suggestion_service.submit(seller, "архівні речі")
    assert str(deactivated.id) in str(deact_exc.value)

    # Створення 3 пропозицій у статусі PENDING
    first = category_suggestion_service.submit(seller, "Музичні інструменти")
    assert first.status == CategorySuggestionStatus.PENDING
    assert first.proposer_id == seller.user_id

    # Дублікат існуючої PENDING-пропозиції від іншого продавця
    other_seller = _make_user()
    with pytest.raises(DuplicateCategorySuggestionError):
        category_suggestion_service.submit(other_seller, "  музичні ІНСТРУМЕНТИ ")

    category_suggestion_service.submit(seller, "Настільні ігри")
    category_suggestion_service.submit(seller, "Спортивне спорядження")

    # 4-та PENDING-пропозиція від того самого користувача -> квота
    with pytest.raises(CategorySuggestionQuotaError):
        category_suggestion_service.submit(seller, "Велосипеди та самокати")


def test_auth_and_blocked_user_guards(
    category_suggestion_service: CategorySuggestionService,
) -> None:
    """[TP-027] [TP-028] [FR-015] [US-010] Захист від анонімів і не-ADMIN."""
    with pytest.raises(ListingUnauthorizedError):
        category_suggestion_service.submit(None, "Нова категорія")

    blocked = _make_user(is_blocked=True)
    with pytest.raises(ListingForbiddenError):
        category_suggestion_service.submit(blocked, "Нова категорія")

    regular = _make_user(role=UserRole.USER)
    with pytest.raises(ModerationForbiddenError):
        category_suggestion_service.list_pending(regular)


def test_approve_moves_only_active_other_listings_and_records_audit(
    category_suggestion_service: CategorySuggestionService,
    category_service: CategoryService,
    listing_service: ListingService,
    listing_repository: InMemoryListingRepository,
    moderation_actions: InMemoryModerationActionRepository,
) -> None:
    """[TP-027] [TP-028] [FR-015] [US-010] Схвалення та перенесення з «Інше»."""
    seller = _make_user()
    admin = _make_user(role=UserRole.ADMIN)

    # Оголошення 1: активне в «Інше» (має перейти в нову категорію)
    l1 = listing_service.create(
        actor_id=seller,
        title="Акустична гітара Yamaha",
        description="Чудовий стан",
        price=3500.0,
        contact="@guitar_seller",
        image_urls=[SEED_IMAGE_URL],
        suggested_category_name="Музичні інструменти",
    )
    assert l1.category_id == OTHER_CATEGORY_ID
    assert l1.suggested_category_id is not None
    assert listing_service.get_suggested_category_name(l1) == "Музичні інструменти"

    suggestion_id = l1.suggested_category_id

    # Оголошення 2: прив'язане до тієї ж пропозиції, але зняте власником (WITHDRAWN)
    l2 = listing_service.create(
        actor_id=seller,
        title="Медіатори Fender",
        description="Набір 6 шт",
        price=120.0,
        category_id=OTHER_CATEGORY_ID,
        contact="@guitar_seller",
        image_urls=[SEED_IMAGE_URL],
    )
    listing_repository.save(replace(l2, suggested_category_id=suggestion_id))
    listing_service.delete(l2.id, seller)

    # Оголошення 3: категорія вже змінена вручну на SEED_CATEGORY_ID
    l3 = listing_service.create(
        actor_id=seller,
        title="Нотний зошит",
        description="Чистий",
        price=50.0,
        category_id=SEED_CATEGORY_ID,
        contact="@guitar_seller",
        image_urls=[SEED_IMAGE_URL],
    )
    listing_repository.save(replace(l3, suggested_category_id=suggestion_id))

    queue = category_suggestion_service.list_pending(admin)
    assert len(queue) == 1
    assert queue[0][0].suggestion_id == suggestion_id
    assert queue[0][1] == 2  # l1 та l3 активні

    approved = category_suggestion_service.approve(
        admin, suggestion_id, name="Музичні інструменти та звук"
    )
    assert approved.status == CategorySuggestionStatus.APPROVED
    assert approved.category_id is not None
    assert approved.reviewed_by == admin.user_id
    assert approved.reviewed_at is not None

    # Нова категорія з'явилася в активному каталозі
    active_ids = {cat.id for cat in category_service.list_active()}
    assert approved.category_id in active_ids

    # Перевірка перенесення оголошень
    assert listing_repository.get(l1.id).category_id == approved.category_id
    assert listing_repository.get(l2.id).category_id == OTHER_CATEGORY_ID
    assert listing_repository.get(l2.id).status == ListingStatus.WITHDRAWN
    assert listing_repository.get(l3.id).category_id == SEED_CATEGORY_ID

    # Запис у журналі модерації
    actions = moderation_actions.list_by_suggestion(suggestion_id)
    assert len(actions) == 1
    assert actions[0].action_type == ModerationActionType.APPROVE_CATEGORY
    assert actions[0].moderator_id == admin.user_id

    # Повторне схвалення або відхилення повертає конфлікт
    with pytest.raises(CategorySuggestionConflictError):
        category_suggestion_service.approve(admin, suggestion_id)
    with pytest.raises(CategorySuggestionConflictError):
        category_suggestion_service.reject(admin, suggestion_id, reason="Запізно")


def test_reject_keeps_listing_in_other_and_clears_link(
    category_suggestion_service: CategorySuggestionService,
    listing_service: ListingService,
    listing_repository: InMemoryListingRepository,
    moderation_actions: InMemoryModerationActionRepository,
) -> None:
    """[TP-027] [TP-028] [FR-015] [US-010] Відхилення пропозиції з причиною."""
    seller = _make_user()
    admin = _make_user(role=UserRole.ADMIN)

    listing = listing_service.create(
        actor_id=seller,
        title="Настільна лампа",
        description="Світлодіодна",
        price=400.0,
        contact="@lamp_seller",
        image_urls=[SEED_IMAGE_URL],
        suggested_category_name="Освітлення для кімнати",
    )
    suggestion_id = listing.suggested_category_id
    assert suggestion_id is not None

    with pytest.raises(InvalidModerationReasonError):
        category_suggestion_service.reject(admin, suggestion_id, reason="Мало")

    rejected = category_suggestion_service.reject(
        admin,
        suggestion_id,
        reason="Використовуйте категорію Канцелярія та побут або Інше",
    )
    assert rejected.status == CategorySuggestionStatus.REJECTED
    assert rejected.reason == "Використовуйте категорію Канцелярія та побут або Інше"

    updated_listing = listing_repository.get(listing.id)
    assert updated_listing.category_id == OTHER_CATEGORY_ID
    assert updated_listing.suggested_category_id is None

    actions = moderation_actions.list_by_suggestion(suggestion_id)
    assert len(actions) == 1
    assert actions[0].action_type == ModerationActionType.REJECT_CATEGORY


def test_atomic_rollback_on_approve_and_listing_create_failure(
    category_repository: InMemoryCategoryRepository,
    category_suggestion_repository: InMemoryCategorySuggestionRepository,
    category_service: CategoryService,
    listing_repository: InMemoryListingRepository,
    listing_service: ListingService,
) -> None:
    """[TP-028] [FR-015] [US-010] Атомарний відкат при збої."""
    seller = _make_user()
    admin = _make_user(role=UserRole.ADMIN)

    # Збій створення оголошення не залишає осиротілу пропозицію
    with pytest.raises(Exception):
        listing_service.create(
            actor_id=seller,
            title="Килимок для йоги",
            description="Новий",
            price=300.0,
            contact="@yoga",
            image_urls=[],
            suggested_category_name="Йога та фітнес",
        )
    assert category_suggestion_repository.list_all() == []

    # Збій запису ModerationAction при approve відкочує всі зміни
    class FailingActions(InMemoryModerationActionRepository):
        def add(self, action):
            raise RuntimeError("DB failure during audit log")

    failing_service = CategorySuggestionService(
        suggestions=category_suggestion_repository,
        categories=category_repository,
        category_service=category_service,
        listings=listing_repository,
        actions=FailingActions(),
    )
    created_listing = listing_service.create(
        actor_id=seller,
        title="Гантелі 5 кг",
        description="Пара",
        price=700.0,
        contact="@gym",
        image_urls=[SEED_IMAGE_URL],
        suggested_category_name="Силовий спорт",
    )
    sid = created_listing.suggested_category_id
    assert sid is not None

    with pytest.raises(RuntimeError):
        failing_service.approve(admin, sid)

    assert (
        category_suggestion_repository.get(sid).status
        == CategorySuggestionStatus.PENDING
    )
    assert listing_repository.get(created_listing.id).category_id == OTHER_CATEGORY_ID
    assert category_repository.get_by_name("Силовий спорт") is None

    with pytest.raises(CategorySuggestionNotFoundError):
        failing_service.approve(admin, uuid4())


def test_approve_preserves_concurrent_withdrawal_and_atomic_publication(
    category_repository: InMemoryCategoryRepository,
    category_suggestion_repository: InMemoryCategorySuggestionRepository,
    category_service: CategoryService,
    listing_repository: InMemoryListingRepository,
    moderation_actions: InMemoryModerationActionRepository,
    category_suggestion_service: CategorySuggestionService,
    listing_service: ListingService,
) -> None:
    """[TP-028] [FR-015] [US-010] Конкурентне зняття та атомарна публікація."""
    seller = _make_user()
    admin = _make_user(role=UserRole.ADMIN)

    # 1. Якщо власник знімає оголошення під час створення категорії в approve(),
    # воно має залишитися WITHDRAWN і не ставати знову ACTIVE.
    withdrawn_during_approve = listing_service.create(
        actor_id=seller,
        title="Монітор 27 дюймів",
        description="IPS",
        price=4500.0,
        contact="@mon",
        image_urls=[SEED_IMAGE_URL],
        suggested_category_name="Комп'ютерна периферія",
    )
    sid = withdrawn_during_approve.suggested_category_id
    assert sid is not None

    class WithdrawingCategoryService(CategoryService):
        def create(self, name: str, slug: str, description: str | None = None):
            created = super().create(name=name, slug=slug, description=description)
            listing_service.delete(withdrawn_during_approve.id, seller)
            return created

    interleaved_service = CategorySuggestionService(
        suggestions=category_suggestion_repository,
        categories=category_repository,
        category_service=WithdrawingCategoryService(category_repository),
        listings=listing_repository,
        actions=moderation_actions,
    )
    approved = interleaved_service.approve(admin, sid)
    assert approved.status == CategorySuggestionStatus.APPROVED
    after_approve = listing_repository.get(withdrawn_during_approve.id)
    assert after_approve is not None
    assert after_approve.status == ListingStatus.WITHDRAWN
    assert after_approve.category_id == OTHER_CATEGORY_ID

    # 2. Під час save_images() пропозиція ще не експонується як PENDING без оголошення
    observed_pending_during_images: list[tuple] = []

    class InspectingImageStorage(InMemoryImageStorage):
        def save_images(self, listing_id, image_urls, actor_id=None):
            observed_pending_during_images.extend(
                category_suggestion_service.list_pending(admin)
            )
            return super().save_images(listing_id, image_urls, actor_id=actor_id)

    atomic_listing_service = ListingService(
        repository=listing_repository,
        image_storage=InspectingImageStorage(),
        category_suggestion_service=category_suggestion_service,
    )
    created_atomic = atomic_listing_service.create(
        actor_id=seller,
        title="Мікрофон USB",
        description="Студійний",
        price=1800.0,
        contact="@mic",
        image_urls=[SEED_IMAGE_URL],
        suggested_category_name="Аудіообладнання",
    )
    assert observed_pending_during_images == []
    assert created_atomic.suggested_category_id is not None
    approved_audio = category_suggestion_service.approve(
        admin, created_atomic.suggested_category_id
    )
    assert (
        listing_repository.get(created_atomic.id).category_id
        == approved_audio.category_id
    )
