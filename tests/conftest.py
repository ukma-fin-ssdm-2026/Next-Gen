"""Спільні фікстури: ізольований Listing Service на кожен тест."""

from collections.abc import Callable
import io
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from src.api.deps import (
    SESSION_COOKIE_NAME,
    get_activity_service,
    get_auth_service,
    get_auth_session_store,
    get_blocked_notice_store,
    get_category_service,
    get_category_suggestion_service,
    get_complaint_service,
    get_contact_service,
    get_favorite_service,
    get_feedback_service,
    get_image_storage,
    get_listing_service,
    get_moderation_service,
    get_profile_service,
    get_user_moderation_service,
    get_user_repository,
)
from src.api.main import app
from src.domain.listings import SEED_CATEGORY_ID, SEED_IMAGE_URL
from src.domain.users import User, UserRole
from src.repositories.categories import InMemoryCategoryRepository
from src.repositories.category_suggestions import (
    InMemoryCategorySuggestionRepository,
)
from src.repositories.favorites import InMemoryFavoriteRepository
from src.repositories.image_storage import InMemoryImageStorage
from src.repositories.listings import InMemoryListingRepository
from src.repositories.moderation import InMemoryModerationActionRepository
from src.repositories.support import (
    InMemoryActivityRepository,
    InMemoryComplaintRepository,
    InMemoryFeedbackRepository,
)
from src.repositories.users import InMemoryUserRepository
from src.services.activity import ActivityLogService
from src.services.auth import AuthService, EntraAuthConfig
from src.services.auth_sessions import InMemoryAuthSessionStore
from src.services.categories import CategoryService
from src.services.complaints import ComplaintService
from src.services.feedback import FeedbackService
from src.services.category_suggestions import CategorySuggestionService
from src.services.contacts import SellerContactService
from src.services.favorites import FavoriteService
from src.services.listings import ListingService
from src.services.moderation import ModerationService
from src.services.profile import ProfileService
from src.services.user_moderation import UserModerationService


def make_dummy_jpeg(w: int = 100, h: int = 100, color=(255, 0, 0)) -> bytes:
    im = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    im.save(buf, format="JPEG")
    return buf.getvalue()


def make_dummy_png(w: int = 100, h: int = 100, color=(0, 255, 0)) -> bytes:
    im = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def make_dummy_webp(w: int = 100, h: int = 100, color=(0, 0, 255)) -> bytes:
    im = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    im.save(buf, format="WEBP")
    return buf.getvalue()


@pytest.fixture
def category_repository() -> InMemoryCategoryRepository:
    return InMemoryCategoryRepository.with_seed()


@pytest.fixture
def category_service(
    category_repository: InMemoryCategoryRepository,
) -> CategoryService:
    return CategoryService(category_repository)


@pytest.fixture
def category_suggestion_repository() -> InMemoryCategorySuggestionRepository:
    return InMemoryCategorySuggestionRepository()


@pytest.fixture
def listing_repository() -> InMemoryListingRepository:
    return InMemoryListingRepository.with_seed()


@pytest.fixture
def image_storage() -> InMemoryImageStorage:
    return InMemoryImageStorage()


@pytest.fixture
def favorite_repository() -> InMemoryFavoriteRepository:
    return InMemoryFavoriteRepository()


@pytest.fixture
def moderation_actions() -> InMemoryModerationActionRepository:
    return InMemoryModerationActionRepository()


@pytest.fixture
def category_suggestion_service(
    category_suggestion_repository: InMemoryCategorySuggestionRepository,
    category_repository: InMemoryCategoryRepository,
    category_service: CategoryService,
    listing_repository: InMemoryListingRepository,
    moderation_actions: InMemoryModerationActionRepository,
) -> CategorySuggestionService:
    return CategorySuggestionService(
        suggestions=category_suggestion_repository,
        categories=category_repository,
        category_service=category_service,
        listings=listing_repository,
        actions=moderation_actions,
    )


@pytest.fixture
def listing_service(
    listing_repository: InMemoryListingRepository,
    favorite_repository: InMemoryFavoriteRepository,
    image_storage: InMemoryImageStorage,
    category_service: CategoryService,
    category_suggestion_service: CategorySuggestionService,
) -> ListingService:
    return ListingService(
        listing_repository,
        image_storage=image_storage,
        favorites=favorite_repository,
        category_validator=category_service.is_valid_category_id,
        category_suggestion_service=category_suggestion_service,
    )


@pytest.fixture
def favorite_service(
    favorite_repository: InMemoryFavoriteRepository,
    listing_repository: InMemoryListingRepository,
) -> FavoriteService:
    return FavoriteService(favorite_repository, listing_repository)


@pytest.fixture
def contact_service(
    listing_repository: InMemoryListingRepository,
) -> SellerContactService:
    return SellerContactService(listing_repository)


@pytest.fixture
def moderation_service(
    listing_repository: InMemoryListingRepository,
    favorite_repository: InMemoryFavoriteRepository,
    moderation_actions: InMemoryModerationActionRepository,
) -> ModerationService:
    return ModerationService(
        listing_repository, favorite_repository, moderation_actions
    )


@pytest.fixture
def activity_repository() -> InMemoryActivityRepository:
    return InMemoryActivityRepository()


@pytest.fixture
def complaint_repository() -> InMemoryComplaintRepository:
    return InMemoryComplaintRepository()


@pytest.fixture
def feedback_repository() -> InMemoryFeedbackRepository:
    return InMemoryFeedbackRepository()


def wire_support_services(
    users: InMemoryUserRepository,
    activity_repository: InMemoryActivityRepository,
    complaint_repository: InMemoryComplaintRepository,
    feedback_repository: InMemoryFeedbackRepository,
    listing_repository: InMemoryListingRepository,
    moderation_actions: InMemoryModerationActionRepository,
) -> ActivityLogService:
    """Підміняє сервіси скарг/звернень/журналу на ізольовані для тесту."""
    activity = ActivityLogService(activity_repository, users, moderation_actions)
    complaints = ComplaintService(
        complaint_repository, listing_repository, users, activity
    )
    feedback = FeedbackService(feedback_repository, users, activity)
    app.dependency_overrides[get_activity_service] = lambda: activity
    app.dependency_overrides[get_complaint_service] = lambda: complaints
    app.dependency_overrides[get_feedback_service] = lambda: feedback
    app.dependency_overrides[get_user_repository] = lambda: users
    return activity


@pytest.fixture
def client(
    listing_service: ListingService,
    favorite_service: FavoriteService,
    contact_service: SellerContactService,
    moderation_service: ModerationService,
    category_service: CategoryService,
    category_suggestion_service: CategorySuggestionService,
    image_storage: InMemoryImageStorage,
    activity_repository: InMemoryActivityRepository,
    complaint_repository: InMemoryComplaintRepository,
    feedback_repository: InMemoryFeedbackRepository,
    listing_repository: InMemoryListingRepository,
    moderation_actions: InMemoryModerationActionRepository,
):
    wire_support_services(
        InMemoryUserRepository(),
        activity_repository,
        complaint_repository,
        feedback_repository,
        listing_repository,
        moderation_actions,
    )
    app.dependency_overrides[get_listing_service] = lambda: listing_service
    app.dependency_overrides[get_favorite_service] = lambda: favorite_service
    app.dependency_overrides[get_contact_service] = lambda: contact_service
    app.dependency_overrides[get_moderation_service] = lambda: moderation_service
    app.dependency_overrides[get_category_service] = lambda: category_service
    app.dependency_overrides[get_category_suggestion_service] = (
        lambda: category_suggestion_service
    )
    app.dependency_overrides[get_image_storage] = lambda: image_storage
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def listing_payload() -> dict[str, object]:
    """Валідне тіло створення оголошення для HTTP-тестів."""
    return {
        "title": "Конспект з алгебри",
        "description": "Друкований конспект, майже не користувався.",
        "price": 80.0,
        "category_id": str(SEED_CATEGORY_ID),
        "contact": "@someone",
        "image_urls": [SEED_IMAGE_URL],
    }


LoginAs = Callable[..., User]


@pytest.fixture
def login_as(
    client: TestClient,
    image_storage: InMemoryImageStorage,
    moderation_actions: InMemoryModerationActionRepository,
    activity_repository: InMemoryActivityRepository,
    complaint_repository: InMemoryComplaintRepository,
    feedback_repository: InMemoryFeedbackRepository,
    listing_repository: InMemoryListingRepository,
) -> LoginAs:
    """Створює локального користувача і справжню серверну сесію в cookie клієнта.

    Не підміняє `require_current_user`: перевіряється реальний шлях
    cookie -> InMemoryAuthSessionStore -> AuthService.get_current_user.
    """
    users = InMemoryUserRepository()
    sessions = InMemoryAuthSessionStore()
    notices = InMemoryAuthSessionStore()
    service = AuthService(
        users,
        EntraAuthConfig(
            tenant_id=uuid4(),
            issuer="https://login.microsoftonline.com/test/v2.0",
            audience="baraholka-test",
        ),
    )
    app.dependency_overrides[get_auth_session_store] = lambda: sessions
    app.dependency_overrides[get_auth_service] = lambda: service
    profiles = ProfileService(users, image_storage)
    app.dependency_overrides[get_profile_service] = lambda: profiles
    user_moderation = UserModerationService(users, moderation_actions, sessions)
    app.dependency_overrides[get_user_moderation_service] = lambda: user_moderation
    wire_support_services(
        users,
        activity_repository,
        complaint_repository,
        feedback_repository,
        listing_repository,
        moderation_actions,
    )
    app.dependency_overrides[get_blocked_notice_store] = lambda: notices

    def _login(
        role: UserRole = UserRole.USER,
        is_blocked: bool = False,
        user_id: UUID | None = None,
    ) -> User:
        user = users.save(
            User(
                user_id=user_id or uuid4(),
                tenant_id=uuid4(),
                entra_object_id=uuid4(),
                email=f"user-{uuid4().hex[:8]}@ukma.edu.ua",
                display_name="Test User",
                role=role,
                is_blocked=is_blocked,
            )
        )
        client.cookies.set(SESSION_COOKIE_NAME, sessions.create(user.user_id))
        return user

    return _login
