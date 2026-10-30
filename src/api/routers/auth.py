"""HTTP endpoints Microsoft Entra ID Authorization Code Flow."""

from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi import status
from fastapi.responses import RedirectResponse

from src.api.deps import (
    BLOCKED_NOTICE_COOKIE_NAME,
    OIDC_STATE_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    SessionCookie,
    get_activity_service,
    get_auth_service,
    get_auth_session_store,
    get_blocked_notice_store,
    get_entra_oidc_client,
    get_entra_settings,
    get_oidc_flow_store,
    get_profile_service,
    get_user_repository,
    require_current_user,
)
from src.api.schemas.listings import ApiValidationErrorResponse, ErrorResponse
from src.api.schemas.support import BlockedStatusResponse
from src.api.schemas.users import CurrentUserResponse, ProfileUpdate
from src.config import ConfigurationError, EntraSettings, development_auth_enabled
from src.domain.activity import ActivityType
from src.services.activity import ActivityLogService
from src.domain.exceptions import InvalidProfileError, ProfileNotFoundError
from src.domain.users import CurrentUser
from src.integrations.entra import EntraOidcClient, EntraOidcError
from src.services.auth import (
    AuthService,
    BlockedUserError,
    InvalidIdentityError,
    VerifiedEntraClaims,
)
from src.services.auth_sessions import InMemoryAuthSessionStore, InMemoryOidcFlowStore
from src.repositories.users import UserRepository
from src.services.profile import ProfileService

MAX_AVATAR_FILE_SIZE_BYTES = 10 * 1024 * 1024

router = APIRouter(prefix="/auth", tags=["Authentication"])

BlockedNoticeCookie = Annotated[
    str | None,
    Cookie(
        alias=BLOCKED_NOTICE_COOKIE_NAME,
        description="Короткий квиток для показу причини блокування",
    ),
]

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
    notices: InMemoryAuthSessionStore = Depends(get_blocked_notice_store),
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
        # Замість сирого JSON 403 показуємо сторінку з причиною блокування:
        # квиток дає доступ лише до /auth/blocked-status, не до сесії.
        response = RedirectResponse(
            _frontend_destination(settings, "/?blocked=1"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
        response.delete_cookie(OIDC_STATE_COOKIE_NAME, path="/api/v1/auth")
        if exc.user_id is not None:
            response.set_cookie(
                key=BLOCKED_NOTICE_COOKIE_NAME,
                value=notices.create(exc.user_id),
                max_age=600,
                httponly=True,
                secure=settings.session_cookie_secure,
                samesite="lax",
                path="/api/v1/auth",
            )
        return response

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


def _me_response(user: CurrentUser) -> CurrentUserResponse:
    return CurrentUserResponse(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        avatar_url=user.avatar_url,
        contact=user.contact,
    )


def _profile_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ProfileNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=[{"loc": ["body"], "msg": str(exc), "type": "value_error"}],
    )


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
    return _me_response(current_user)


@router.get(
    "/blocked-status",
    response_model=BlockedStatusResponse,
    summary="Факт і причина блокування поточного користувача",
    description=(
        "Доступний без валідної сесії: розпізнає користувача за сесією або за "
        "коротким квитком, який видає /auth/callback для заблокованого входу. "
        "Повертає лише дані про блокування самого користувача (FR-013)."
    ),
)
def blocked_status(
    session_token: SessionCookie = None,
    notice_token: BlockedNoticeCookie = None,
    sessions: InMemoryAuthSessionStore = Depends(get_auth_session_store),
    notices: InMemoryAuthSessionStore = Depends(get_blocked_notice_store),
    users: UserRepository = Depends(get_user_repository),
) -> BlockedStatusResponse:
    user_id = None
    if session_token is not None:
        user_id = sessions.resolve(session_token)
    if user_id is None and notice_token is not None:
        user_id = notices.resolve(notice_token)
    user = users.get_by_id(user_id) if user_id is not None else None
    if user is None or not user.is_blocked:
        return BlockedStatusResponse(is_blocked=False)
    return BlockedStatusResponse(
        is_blocked=True, reason=user.block_reason, blocked_at=user.blocked_at
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
    response.delete_cookie(BLOCKED_NOTICE_COOKIE_NAME, path="/api/v1/auth")
    return response


_PROFILE_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Not authenticated"},
    403: {"model": ErrorResponse, "description": "Local user is blocked"},
    422: {"model": ApiValidationErrorResponse, "description": "Validation Error"},
}


@router.patch(
    "/me",
    response_model=CurrentUserResponse,
    summary="Оновити власний профіль",
    description=(
        "Змінює ім'я та/або контакти за замовчуванням. Передані поля оновлюються, "
        "відсутні лишаються без змін; contact=null або '' очищає контакти (FR-014)."
    ),
    responses=_PROFILE_RESPONSES,
)
def update_me(
    payload: ProfileUpdate,
    current_user: CurrentUser = Depends(require_current_user),
    profiles: ProfileService = Depends(get_profile_service),
    activity: ActivityLogService = Depends(get_activity_service),
) -> CurrentUserResponse:
    fields = payload.model_fields_set
    try:
        updated = profiles.update(
            current_user,
            display_name=payload.display_name,
            update_name="display_name" in fields,
            contact=payload.contact,
            update_contact="contact" in fields,
        )
    except (InvalidProfileError, ProfileNotFoundError) as exc:
        raise _profile_error(exc) from exc
    activity.record(current_user, ActivityType.PROFILE_UPDATED)
    return _me_response(updated)


@router.put(
    "/me/avatar",
    response_model=CurrentUserResponse,
    summary="Завантажити аватарку",
    description=(
        "Приймає один файл (JPEG, PNG, WebP, HEIC/HEIF до 10 МБ), перевіряє "
        "декодування, видаляє метадані, нормалізує до WebP і замінює попередню "
        "аватарку (FR-014, TM-03)."
    ),
    responses=_PROFILE_RESPONSES,
)
def put_avatar(
    file: UploadFile = File(..., description="Файл аватарки"),
    current_user: CurrentUser = Depends(require_current_user),
    profiles: ProfileService = Depends(get_profile_service),
) -> CurrentUserResponse:
    try:
        data = file.file.read(MAX_AVATAR_FILE_SIZE_BYTES + 1)
    finally:
        file.file.close()
    if len(data) > MAX_AVATAR_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[
                {
                    "loc": ["body", "file"],
                    "msg": "Розмір файла перевищує максимально допустимі 10 МБ",
                    "type": "value_error",
                }
            ],
        )
    try:
        updated = profiles.set_avatar(current_user, data)
    except (InvalidProfileError, ProfileNotFoundError) as exc:
        raise _profile_error(exc) from exc
    return _me_response(updated)


@router.delete(
    "/me/avatar",
    response_model=CurrentUserResponse,
    summary="Видалити аватарку",
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Local user is blocked"},
        404: {"model": ErrorResponse, "description": "Profile not found"},
    },
)
def delete_avatar(
    current_user: CurrentUser = Depends(require_current_user),
    profiles: ProfileService = Depends(get_profile_service),
) -> CurrentUserResponse:
    try:
        updated = profiles.remove_avatar(current_user)
    except ProfileNotFoundError as exc:
        raise _profile_error(exc) from exc
    return _me_response(updated)
