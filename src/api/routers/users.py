"""Публічний профіль користувача: ім'я та аватарка продавця (FR-014)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import get_profile_service, require_current_user
from src.api.schemas.listings import ApiValidationErrorResponse, ErrorResponse
from src.api.schemas.users import PublicProfileResponse
from src.domain.exceptions import ProfileNotFoundError
from src.domain.users import CurrentUser
from src.services.profile import ProfileService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/{user_id}",
    response_model=PublicProfileResponse,
    summary="Отримати публічний профіль користувача",
    description=(
        "Повертає лише ім'я й аватарку; email, роль і контакти не включаються "
        "(FR-014, SEC-002). Потрібна автентифікація."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Local user is blocked"},
        404: {"model": ErrorResponse, "description": "User not found"},
        422: {"model": ApiValidationErrorResponse, "description": "Validation Error"},
    },
)
def get_public_profile(
    user_id: UUID,
    _current_user: CurrentUser = Depends(require_current_user),
    profiles: ProfileService = Depends(get_profile_service),
) -> PublicProfileResponse:
    try:
        user = profiles.get_public(user_id)
    except ProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return PublicProfileResponse(
        user_id=user.user_id,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
    )
