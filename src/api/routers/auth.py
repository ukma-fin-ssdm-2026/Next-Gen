"""HTTP endpoints Microsoft Entra ID Authorization Code Flow."""

from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response
from fastapi import status
from fastapi.responses import RedirectResponse

from src.api.deps import (
    OIDC_STATE_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    SessionCookie,
    get_auth_service,
    get_auth_session_store,
    get_entra_oidc_client,
    get_entra_settings,
    get_oidc_flow_store,
    require_current_user,
)
from src.api.schemas.listings import ErrorResponse
from src.api.schemas.users import CurrentUserResponse
from src.config import ConfigurationError, EntraSettings, development_auth_enabled
from src.domain.users import CurrentUser
from src.integrations.entra import EntraOidcClient, EntraOidcError
from src.services.auth import (
    AuthService,
    BlockedUserError,
    InvalidIdentityError,
    VerifiedEntraClaims,
)
from src.services.auth_sessions import InMemoryAuthSessionStore, InMemoryOidcFlowStore

router = APIRouter(prefix="/auth", tags=["Authentication"])

OidcStateCookie = Annotated[
    str | None,
    Cookie(alias=OIDC_STATE_COOKIE_NAME, description="Одноразовий state потоку OIDC"),
]


def _safe_return_path(value: str | None) -> str | None:
    """Дозволяє повернення лише на внутрішні маршрути цього сайту."""
    if (
        not value
        or not value.startswith("/")
        or value.startswith("//")
        or "\\" in value
    ):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme or parsed.netloc:
        return None
    return value


def _frontend_destination(settings: EntraSettings, return_to: str | None) -> str:
    destination = settings.frontend_url
    safe_return_to = _safe_return_path(return_to)
    if safe_return_to is not None:
        frontend = urlsplit(settings.frontend_url)
        requested = urlsplit(safe_return_to)
        destination = frontend._replace(
            path=requested.path,
            query=requested.query,
            fragment=requested.fragment,
        ).geturl()
    return destination


def _development_login_response(
    settings: EntraSettings,
    sessions: InMemoryAuthSessionStore,
    service: AuthService,
    return_to: str | None,
) -> RedirectResponse:
    """Creates a normal server-side session without contacting Entra locally."""
    claims = VerifiedEntraClaims(
        tenant_id=settings.tenant_id,
        object_id=UUID("00000000-0000-0000-0000-000000000002"),
        issuer=settings.issuer,
        audience=settings.client_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        email="developer@ukma.edu.ua",
        display_name="Local Developer",
    )
    current_user = service.authenticate_verified_claims(claims)
    response = RedirectResponse(
        _safe_return_path(return_to) or "/",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=sessions.create(current_user.user_id),
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.get(
    "/login",
    summary="Розпочати вхід Microsoft Entra ID",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    responses={
        502: {"model": ErrorResponse, "description": "Microsoft Entra unavailable"},
        503: {"model": ErrorResponse, "description": "Entra ID not configured"},
    },
)
def login(
    return_to: Annotated[
        str | None,
        Query(
            alias="next",
            max_length=2048,
            description="Внутрішній маршрут для повернення після входу",
        ),
    ] = None,
    settings: EntraSettings = Depends(get_entra_settings),
    oidc: EntraOidcClient = Depends(get_entra_oidc_client),
    flows: InMemoryOidcFlowStore = Depends(get_oidc_flow_store),
    sessions: InMemoryAuthSessionStore = Depends(get_auth_session_store),
    service: AuthService = Depends(get_auth_service),
) -> RedirectResponse:
    try:
        if development_auth_enabled(settings):
            return _development_login_response(
                settings,
                sessions,
                service,
                return_to,
            )
    except ConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    try:
        flow = oidc.begin()
    except EntraOidcError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    state_value = str(flow["state"])
    flow["return_to"] = _safe_return_path(return_to)
    flows.save(state_value, flow)
    response = RedirectResponse(str(flow["auth_uri"]))
    response.set_cookie(
        key=OIDC_STATE_COOKIE_NAME,
        value=state_value,
        max_age=settings.oidc_flow_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
    )
    return response


@router.get(
    "/callback",
    summary="Завершити Microsoft Entra ID callback",
    status_code=status.HTTP_303_SEE_OTHER,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid OIDC state"},
        401: {"model": ErrorResponse, "description": "Microsoft sign-in rejected"},
        403: {"model": ErrorResponse, "description": "Local user is blocked"},
        503: {"model": ErrorResponse, "description": "Entra ID not configured"},
    },
)
def callback(
    request: Request,
    state: str | None = Query(None, description="state, який повернув Microsoft"),
    oidc_state: OidcStateCookie = None,
    settings: EntraSettings = Depends(get_entra_settings),
    oidc: EntraOidcClient = Depends(get_entra_oidc_client),
    flows: InMemoryOidcFlowStore = Depends(get_oidc_flow_store),
    sessions: InMemoryAuthSessionStore = Depends(get_auth_session_store),
    service: AuthService = Depends(get_auth_service),
) -> RedirectResponse:
    if state is None or oidc_state is None or state != oidc_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Невалідний OIDC state",
        )
    flow = flows.pop(state)
    if flow is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC flow не знайдено або він завершився",
        )

    return_to = _safe_return_path(flow.pop("return_to", None))

    try:
        claims = oidc.complete(flow, dict(request.query_params))
        current_user = service.authenticate_verified_claims(claims)
    except (EntraOidcError, InvalidIdentityError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except BlockedUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    session_token = sessions.create(current_user.user_id)
    response = RedirectResponse(
        _frontend_destination(settings, return_to),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.delete_cookie(OIDC_STATE_COOKIE_NAME, path="/api/v1/auth")
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Отримати поточного користувача",
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Local user is blocked"},
        503: {"model": ErrorResponse, "description": "Entra ID not configured"},
    },
)
def me(
    current_user: CurrentUser = Depends(require_current_user),
) -> CurrentUserResponse:
    return CurrentUserResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        display_name=current_user.display_name,
        role=current_user.role,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Завершити локальну сесію",
)
def logout(
    session_token: SessionCookie = None,
    sessions: InMemoryAuthSessionStore = Depends(get_auth_session_store),
) -> Response:
    if session_token is not None:
        sessions.revoke(session_token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response
