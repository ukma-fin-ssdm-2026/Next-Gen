"""Залежності FastAPI: збирає сервіси на краю застосунку.

PostgreSQL-адаптери підключаються через DATABASE_URL (ADR-002).
Якщо DATABASE_URL не задано, використовується in-memory fallback
(лише для локальної розробки без Docker).
"""

import os
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.config import (
    ConfigurationError,
    EntraSettings,
    get_admin_emails,
    get_image_storage_dir,
)
from src.domain.users import CurrentUser
from src.integrations.entra import EntraOidcClient, MsalEntraOidcClient
from src.repositories.categories import InMemoryCategoryRepository
from src.repositories.category_suggestions import (
    InMemoryCategorySuggestionRepository,
)
from src.repositories.favorites import InMemoryFavoriteRepository
from src.repositories.image_storage import ImageStorage, LocalImageStorage
from src.repositories.listings import InMemoryListingRepository
from src.repositories.moderation import InMemoryModerationActionRepository
from src.repositories.users import InMemoryUserRepository
from src.services.auth import (
    AuthService,
    BlockedUserError,
    EntraAuthConfig,
    InvalidSessionError,
)
from src.services.auth_sessions import InMemoryAuthSessionStore, InMemoryOidcFlowStore
from src.services.categories import CategoryService
from src.services.category_suggestions import CategorySuggestionService
from src.services.contacts import SellerContactService
from src.services.favorites import FavoriteService
from src.services.listings import ListingService
from src.services.moderation import ModerationService
from src.services.profile import ProfileService
from src.services.user_moderation import UserModerationService

# ---------------------------------------------------------------------------
# Визначаємо, чи доступний PostgreSQL
# ---------------------------------------------------------------------------

_USE_POSTGRES = bool(os.getenv("DATABASE_URL", "").strip())

# ---------------------------------------------------------------------------
# Singleton репозиторії (in-memory fallback для розробки без Docker)
# ---------------------------------------------------------------------------

image_storage: ImageStorage = LocalImageStorage(get_image_storage_dir())
oidc_flow_store = InMemoryOidcFlowStore()
auth_session_store = InMemoryAuthSessionStore()

# In-memory singletons (використовуються якщо немає DATABASE_URL)
_inmem_category_repository = InMemoryCategoryRepository.with_seed()
_inmem_category_suggestion_repository = InMemoryCategorySuggestionRepository()
_inmem_listing_repository = InMemoryListingRepository.with_seed()
_inmem_favorite_repository = InMemoryFavoriteRepository()
_inmem_moderation_action_repository = InMemoryModerationActionRepository()
_inmem_user_repository = InMemoryUserRepository()

SESSION_COOKIE_NAME = "baraholka_session"
OIDC_STATE_COOKIE_NAME = "baraholka_oidc_state"


# ---------------------------------------------------------------------------
# FastAPI залежність: сесія БД (PostgreSQL або None для in-memory)
# ---------------------------------------------------------------------------


def get_db_session():
    """FastAPI залежність: повертає SQLAlchemy Session або None."""
    if not _USE_POSTGRES:
        yield None
        return
    from src.db.engine import get_db_session as _get_session

    yield from _get_session()


DbSession = Annotated[Session | None, Depends(get_db_session)]


# ---------------------------------------------------------------------------
# Repository factories (вибирають PostgreSQL або in-memory залежно від конфігурації)
# ---------------------------------------------------------------------------


def get_user_repository(session: DbSession = None):
    """Повертає PostgreSQL або in-memory репозиторій користувачів."""
    if session is not None:
        from src.repositories.postgres_users import PostgresUserRepository

        return PostgresUserRepository(session)
    return _inmem_user_repository


def get_category_repository(session: DbSession = None):
    """Повертає PostgreSQL або in-memory репозиторій категорій."""
    if session is not None:
        from src.repositories.postgres_categories import PostgresCategoryRepository

        return PostgresCategoryRepository(session)
    return _inmem_category_repository


def get_category_suggestion_repository(session: DbSession = None):
    """Повертає PostgreSQL або in-memory репозиторій пропозицій категорій."""
    if session is not None:
        from src.repositories.postgres_category_suggestions import (
            PostgresCategorySuggestionRepository,
        )

        return PostgresCategorySuggestionRepository(session)
    return _inmem_category_suggestion_repository


def get_listing_repository(session: DbSession = None):
    """Повертає PostgreSQL або in-memory репозиторій оголошень."""
    if session is not None:
        from src.repositories.postgres_listings import PostgresListingRepository

        return PostgresListingRepository(session)
    return _inmem_listing_repository


def get_favorite_repository(session: DbSession = None):
    """Повертає PostgreSQL або in-memory репозиторій обраного."""
    if session is not None:
        from src.repositories.postgres_favorites_moderation import (
            PostgresFavoriteRepository,
        )

        return PostgresFavoriteRepository(session)
    return _inmem_favorite_repository


def get_moderation_repository(session: DbSession = None):
    """Повертає PostgreSQL або in-memory репозиторій дій модерації."""
    if session is not None:
        from src.repositories.postgres_favorites_moderation import (
            PostgresModerationActionRepository,
        )

        return PostgresModerationActionRepository(session)
    return _inmem_moderation_action_repository


# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------


def get_image_storage() -> ImageStorage:
    """Повертає сховище зображень для ін'єкції в роутери."""
    return image_storage


def get_category_service(
    session: DbSession = None,
) -> CategoryService:
    """Повертає Category Service для ін'єкції в роутери."""
    return CategoryService(get_category_repository(session))


def get_category_suggestion_service(
    session: DbSession = None,
) -> CategorySuggestionService:
    """Повертає Category Suggestion Service для ін'єкції в роутери (FR-015)."""
    cat_repo = get_category_repository(session)
    cat_service = CategoryService(cat_repo)
    return CategorySuggestionService(
        suggestions=get_category_suggestion_repository(session),
        categories=cat_repo,
        category_service=cat_service,
        listings=get_listing_repository(session),
        actions=get_moderation_repository(session),
    )


def get_listing_service(
    session: DbSession = None,
) -> ListingService:
    """Повертає Listing Service для ін'єкції в роутери."""
    cat_repo = get_category_repository(session)
    cat_service = CategoryService(cat_repo)
    cat_suggestion_service = CategorySuggestionService(
        suggestions=get_category_suggestion_repository(session),
        categories=cat_repo,
        category_service=cat_service,
        listings=get_listing_repository(session),
        actions=get_moderation_repository(session),
    )
    return ListingService(
        get_listing_repository(session),
        image_storage=image_storage,
        favorites=get_favorite_repository(session),
        category_validator=cat_service.is_valid_category_id,
        category_suggestion_service=cat_suggestion_service,
    )


def get_favorite_service(
    session: DbSession = None,
) -> FavoriteService:
    """Повертає Favorite Service, що ділить сховища з Listing Service."""
    return FavoriteService(
        get_favorite_repository(session), get_listing_repository(session)
    )


def get_contact_service(
    session: DbSession = None,
) -> SellerContactService:
    """Повертає Seller Contact Service, що читає те саме сховище оголошень."""
    return SellerContactService(get_listing_repository(session))


def get_moderation_service(
    session: DbSession = None,
) -> ModerationService:
    """Повертає Moderation Service зі спільними сховищами оголошень і обраного."""
    return ModerationService(
        get_listing_repository(session),
        get_favorite_repository(session),
        get_moderation_repository(session),
    )


def get_entra_settings() -> EntraSettings:
    try:
        return EntraSettings.from_env()
    except ConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Microsoft Entra ID ще не сконфігуровано",
        ) from exc


def get_auth_service(
    settings: EntraSettings = Depends(get_entra_settings),
) -> AuthService:
    try:
        admin_emails = get_admin_emails()
    except ConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Список адміністраторів налаштовано некоректно",
        ) from exc
    return AuthService(
        _inmem_user_repository,
        EntraAuthConfig(
            tenant_id=settings.tenant_id,
            issuer=settings.issuer,
            audience=settings.client_id,
        ),
        admin_emails,
    )


def get_user_moderation_service(
    session: DbSession = None,
) -> UserModerationService:
    """Повертає User Moderation Service для ін'єкції в роутери (FR-013)."""
    return UserModerationService(
        get_user_repository(session),
        get_moderation_repository(session),
        auth_session_store,
    )


def get_profile_service(
    session: DbSession = None,
) -> ProfileService:
    """Повертає Profile Service для ін'єкції в роутери (FR-014)."""
    return ProfileService(get_user_repository(session), image_storage)


def get_entra_oidc_client(
    settings: EntraSettings = Depends(get_entra_settings),
) -> EntraOidcClient:
    return MsalEntraOidcClient(settings)


def get_oidc_flow_store() -> InMemoryOidcFlowStore:
    return oidc_flow_store


def get_auth_session_store() -> InMemoryAuthSessionStore:
    return auth_session_store


SessionCookie = Annotated[
    str | None,
    Cookie(alias=SESSION_COOKIE_NAME, description="Непрозорий ID серверної сесії"),
]


def _resolve_auth_service(request: Request) -> AuthService:
    if get_auth_service in request.app.dependency_overrides:
        return request.app.dependency_overrides[get_auth_service]()
    return get_auth_service(get_entra_settings())


def require_current_user(
    request: Request,
    session_token: SessionCookie = None,
    sessions: InMemoryAuthSessionStore = Depends(get_auth_session_store),
) -> CurrentUser:
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Потрібен вхід через Microsoft",
        )
    user_id = sessions.resolve(session_token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сесія недійсна або завершилася",
        )
    service = _resolve_auth_service(request)
    try:
        return service.get_current_user(user_id)
    except InvalidSessionError as exc:
        sessions.revoke(session_token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except BlockedUserError as exc:
        sessions.revoke(session_token)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
