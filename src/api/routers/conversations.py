"""HTTP-роутер приватного чату між користувачами (ADR-005, FR-021, FR-022, SEC-003)."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from src.api.deps import get_conversation_service, require_current_user
from src.api.schemas.conversations import (
    ConversationPageResponse,
    MessagePageResponse,
    MessageResponse,
    SendMessageRequest,
    StartConversationRequest,
    StartConversationResponse,
    UnreadCountResponse,
)
from src.api.schemas.listings import ApiValidationErrorResponse, ErrorResponse
from src.domain.exceptions import (
    ChatRateLimitError,
    ConversationForbiddenError,
    ConversationNotFoundError,
    InvalidChatCursorError,
    InvalidMessageError,
    ListingNotFoundError,
    ListingUnauthorizedError,
)
from src.domain.users import CurrentUser
from src.services.conversations import (
    CONVERSATIONS_PAGE_DEFAULT,
    CONVERSATIONS_PAGE_MAX,
    MESSAGES_PAGE_DEFAULT,
    MESSAGES_PAGE_MAX,
    ConversationService,
)

router = APIRouter(tags=["Conversations"])

Actor = Annotated[CurrentUser, Depends(require_current_user)]
Service = Annotated[ConversationService, Depends(get_conversation_service)]

UNAUTHENTICATED = {"model": ErrorResponse, "description": "Потрібна чинна сесія"}
FORBIDDEN = {"model": ErrorResponse, "description": "Дія заборонена"}
LISTING_NOT_FOUND = {
    "model": ErrorResponse,
    "description": "Оголошення не знайдено або недоступне",
}
CONVERSATION_NOT_FOUND = {
    "model": ErrorResponse,
    "description": "Розмову не знайдено",
}
INVALID_INPUT = {"model": ApiValidationErrorResponse, "description": "Невалідні дані"}
RATE_LIMITED = {
    "model": ErrorResponse,
    "description": "Перевищено сервісний ліміт повідомлень або нових розмов",
    "headers": {
        "Retry-After": {
            "description": "Через скільки секунд варто повторити запит",
            "schema": {"type": "integer", "example": 60},
        }
    },
}


@contextmanager
def _chat_errors(cursor_field: str | None = "cursor") -> Iterator[None]:
    """Перетворює доменні винятки чату на HTTP-коди без витоку body чи cookie."""
    try:
        yield
    except ListingUnauthorizedError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ConversationForbiddenError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except (ListingNotFoundError, ConversationNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidMessageError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[{"loc": ["body", "body"], "msg": str(exc), "type": "value_error"}],
        ) from exc
    except InvalidChatCursorError as exc:
        loc = ["query", cursor_field] if cursor_field else ["query"]
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[{"loc": loc, "msg": str(exc), "type": "value_error"}],
        ) from exc
    except ChatRateLimitError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc


@router.post(
    "/listings/{listing_id}/conversation",
    response_model=StartConversationResponse,
    summary="Почати або продовжити розмову зі сторінки оголошення",
    description=(
        "Знаходить наявну або створює нову розмову з продавцем активного оголошення "
        "та атомарно надсилає перше повідомлення з безпечною карткою цього оголошення "
        "(FR-021). Повертає 201 для нової розмови та 200, якщо розмова вже існувала."
    ),
    responses={
        200: {
            "model": StartConversationResponse,
            "description": "Повідомлення надіслано в наявну розмову",
        },
        201: {
            "model": StartConversationResponse,
            "description": "Розмову створено та перше повідомлення надіслано",
        },
        401: UNAUTHENTICATED,
        403: FORBIDDEN,
        404: LISTING_NOT_FOUND,
        422: INVALID_INPUT,
        429: RATE_LIMITED,
    },
)
def start_listing_conversation(
    listing_id: UUID,
    payload: StartConversationRequest,
    response: Response,
    actor: Actor,
    service: Service,
) -> StartConversationResponse:
    with _chat_errors():
        result = service.start_from_listing(actor, listing_id, payload.body)
    response.headers["Cache-Control"] = "no-store"
    if result.created:
        response.status_code = status.HTTP_201_CREATED
    return StartConversationResponse.model_validate(result)


@router.get(
    "/conversations",
    response_model=ConversationPageResponse,
    summary="Отримати список власних розмов",
    description=(
        "Повертає сторінку розмов поточного користувача від найсвіжішої активності "
        "без розкриття email чи контактів співрозмовника (FR-022, SEC-002)."
    ),
    responses={
        401: UNAUTHENTICATED,
        403: FORBIDDEN,
        422: INVALID_INPUT,
    },
)
def list_conversations(
    response: Response,
    actor: Actor,
    service: Service,
    limit: Annotated[
        int, Query(ge=1, le=CONVERSATIONS_PAGE_MAX)
    ] = CONVERSATIONS_PAGE_DEFAULT,
    cursor: Annotated[str | None, Query()] = None,
) -> ConversationPageResponse:
    with _chat_errors(cursor_field="cursor"):
        page = service.list_conversations(actor, limit=limit, cursor=cursor)
    response.headers["Cache-Control"] = "no-store"
    return ConversationPageResponse.model_validate(page)


@router.get(
    "/conversations/unread-count",
    response_model=UnreadCountResponse,
    summary="Отримати сумарну кількість непрочитаних повідомлень",
    description=(
        "Повертає лише сумарне число непрочитаних повідомлень поточного користувача "
        "в усіх його розмовах (FR-022)."
    ),
    responses={
        401: UNAUTHENTICATED,
        403: FORBIDDEN,
    },
)
def get_unread_count(
    response: Response,
    actor: Actor,
    service: Service,
) -> UnreadCountResponse:
    with _chat_errors():
        count = service.unread_count(actor)
    response.headers["Cache-Control"] = "no-store"
    return UnreadCountResponse(unread_count=count)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessagePageResponse,
    summary="Отримати повідомлення розмови з курсорною пагінацією та polling",
    description=(
        "Повертає повідомлення розмови лише для її учасників; для не-учасника або "
        "неіснуючого ID повертає однаковий 404 (SEC-003). Курсори `after` (polling) "
        "та `before` (історія) є взаємовиключними."
    ),
    responses={
        401: UNAUTHENTICATED,
        403: FORBIDDEN,
        404: CONVERSATION_NOT_FOUND,
        422: INVALID_INPUT,
    },
)
def list_conversation_messages(
    conversation_id: UUID,
    response: Response,
    actor: Actor,
    service: Service,
    after: Annotated[str | None, Query()] = None,
    before: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MESSAGES_PAGE_MAX)] = MESSAGES_PAGE_DEFAULT,
) -> MessagePageResponse:
    cursor_field: str | None = None
    if after is not None and before is None:
        cursor_field = "after"
    elif before is not None and after is None:
        cursor_field = "before"
    with _chat_errors(cursor_field=cursor_field):
        page = service.list_messages(
            actor, conversation_id, after=after, before=before, limit=limit
        )
    response.headers["Cache-Control"] = "no-store"
    return MessagePageResponse.model_validate(page)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Надіслати повідомлення в розмову",
    description=(
        "Надсилає текстове повідомлення в наявну розмову учасником із перевіреної "
        "сесії; за потреби прикріплює картку активного оголошення одного з "
        "учасників (FR-022, SEC-003)."
    ),
    responses={
        401: UNAUTHENTICATED,
        403: FORBIDDEN,
        404: {
            "model": ErrorResponse,
            "description": "Розмову або прикріплене оголошення не знайдено",
        },
        422: INVALID_INPUT,
        429: RATE_LIMITED,
    },
)
def send_conversation_message(
    conversation_id: UUID,
    payload: SendMessageRequest,
    response: Response,
    actor: Actor,
    service: Service,
) -> MessageResponse:
    with _chat_errors():
        message = service.send_message(
            actor,
            conversation_id,
            payload.body,
            listing_id=payload.listing_id,
        )
    response.headers["Cache-Control"] = "no-store"
    return MessageResponse.model_validate(message)


@router.post(
    "/conversations/{conversation_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Позначити розмову прочитаною",
    description=(
        "Пересуває позначку прочитаного для поточного учасника до останнього "
        "повідомлення в розмові (FR-022); для не-учасника повертає 404 (SEC-003)."
    ),
    responses={
        401: UNAUTHENTICATED,
        403: FORBIDDEN,
        404: CONVERSATION_NOT_FOUND,
        422: INVALID_INPUT,
    },
)
def mark_conversation_read(
    conversation_id: UUID,
    response: Response,
    actor: Actor,
    service: Service,
) -> None:
    with _chat_errors():
        service.mark_read(actor, conversation_id)
    response.headers["Cache-Control"] = "no-store"
