"""Спільні фікстури: ізольований Listing Service на кожен тест."""

from collections.abc import Callable
import io
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from src.api.deps import (
    SESSION_COOKIE_NAME,
    category_service,
    get_auth_service,
    get_auth_session_store,
    get_contact_service,
    get_favorite_service,
    get_image_storage,
    get_listing_service,
    get_moderation_service,
)
from src.api.main import app
from src.domain.listings import SEED_CATEGORY_ID, SEED_IMAGE_URL
from src.domain.users import User, UserRole
from src.repositories.favorites import InMemoryFavoriteRepository
from src.repositories.image_storage import InMemoryImageStorage
from src.repositories.listings import InMemoryListingRepository
from src.repositories.moderation import InMemoryModerationActionRepository
from src.repositories.users import InMemoryUserRepository
from src.services.auth import AuthService, EntraAuthConfig
from src.services.auth_sessions import InMemoryAuthSessionStore
from src.services.contacts import SellerContactService
from src.services.favorites import FavoriteService
from src.services.listings import ListingService
from src.services.moderation import ModerationService


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
def listing_repository() -> InMemoryListingRepository:
    return InMemoryListingRepository.with_seed()


@pytest.fixture
def image_storage() -> InMemoryImageStorage:
    return InMemoryImageStorage()


@pytest.fixture
def favorite_repository() -> InMemoryFavoriteRepository:
    return InMemoryFavoriteRepository()


@pytest.fixture
def listing_service(
    listing_repository: InMemoryListingRepository,
    favorite_repository: InMemoryFavoriteRepository,
    image_storage: InMemoryImageStorage,
) -> ListingService:
    return ListingService(
        listing_repository,
        image_storage=image_storage,
        favorites=favorite_repository,
        category_validator=category_service.is_valid_category_id,
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
def moderation_actions() -> InMemoryModerationActionRepository:
    return InMemoryModerationActionRepository()


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
def client(
    listing_service: ListingService,
    favorite_service: FavoriteService,
    contact_service: SellerContactService,
    moderation_service: ModerationService,
    image_storage: InMemoryImageStorage,
):
    app.dependency_overrides[get_listing_service] = lambda: listing_service
    app.dependency_overrides[get_favorite_service] = lambda: favorite_service
    app.dependency_overrides[get_contact_service] = lambda: contact_service
    app.dependency_overrides[get_moderation_service] = lambda: moderation_service
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
def login_as(client: TestClient) -> LoginAs:
    """Створює локального користувача і справжню серверну сесію в cookie клієнта.

    Не підміняє `require_current_user`: перевіряється реальний шлях
    cookie -> InMemoryAuthSessionStore -> AuthService.get_current_user.
    """
    users = InMemoryUserRepository()
    sessions = InMemoryAuthSessionStore()
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
