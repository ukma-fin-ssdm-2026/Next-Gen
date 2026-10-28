"""Залежності FastAPI: збирає сервіси на краю застосунку."""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from src.config import ConfigurationError, EntraSettings
from src.domain.users import CurrentUser
from src.integrations.entra import EntraOidcClient, MsalEntraOidcClient
from src.repositories.favorites import InMemoryFavoriteRepository
from src.repositories.listings import InMemoryListingRepository
from src.repositories.users import InMemoryUserRepository
from src.services.auth import (
    AuthService,
    BlockedUserError,
    EntraAuthConfig,
    InvalidSessionError,
)
from src.services.auth_sessions import InMemoryAuthSessionStore, InMemoryOidcFlowStore
from src.services.favorites import FavoriteService
from src.services.listings import ListingService

listing_repository = InMemoryListingRepository.with_seed()
favorite_repository = InMemoryFavoriteRepository()
listing_service = ListingService(listing_repository, favorites=favorite_repository)
favorite_service = FavoriteService(favorite_repository, listing_repository)
user_repository = InMemoryUserRepository()
oidc_flow_store = InMemoryOidcFlowStore()
auth_session_store = InMemoryAuthSessionStore()

SESSION_COOKIE_NAME = "baraholka_session"
OIDC_STATE_COOKIE_NAME = "baraholka_oidc_state"


def get_listing_service() -> ListingService:
    """Повертає Listing Service для ін'єкції в роутери."""
    return listing_service


def get_favorite_service() -> FavoriteService:
    """Повертає Favorite Service, що ділить сховища з Listing Service."""
    return favorite_service


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
    return AuthService(
        user_repository,
        EntraAuthConfig(
            tenant_id=settings.tenant_id,
            issuer=settings.issuer,
            audience=settings.client_id,
        ),
    )


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


def require_current_user(
    session_token: SessionCookie = None,
    sessions: InMemoryAuthSessionStore = Depends(get_auth_session_store),
    service: AuthService = Depends(get_auth_service),
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
