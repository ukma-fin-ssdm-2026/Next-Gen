"""Conversation Service: розмови між користувачами (ADR-005, FR-021, FR-022).

Сервіс не залежить від FastAPI: роутер лише перетворює винятки на HTTP-коди.

- `ListingUnauthorizedError` — 401: немає автентифікованого користувача;
- `ConversationForbiddenError` — 403: розмова із собою або акаунт заблоковано;
- `ListingNotFoundError` — 404: оголошення немає, воно не `ACTIVE` або чуже;
- `ConversationNotFoundError` — 404: розмови немає або користувач не її
  учасник (IDOR);
- `InvalidMessageError` — 422: текст поза 1–1000 символів або з керівними;
- `InvalidChatCursorError` — 422: пошкоджений курсор або `after` з `before`;
- `ChatRateLimitError` — 429: перевищено ліміт, `retry_after_seconds` для
  заголовка `Retry-After`.

Усі зміни виконуються в одній сесії запиту, тому розмова й перше
повідомлення фіксуються разом або не фіксуються взагалі. Вміст повідомлень
не пишеться ні в журнал дій, ні в тексти винятків.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from src.domain.activity import ActivityType
from src.domain.conversations import (
    ChatSettings,
    Conversation,
    Message,
    as_utc,
    decode_cursor,
    encode_cursor,
    normalize_message_body,
    normalize_pair,
)
from src.domain.exceptions import (
    ChatRateLimitError,
    ConversationForbiddenError,
    ConversationNotFoundError,
    InvalidChatCursorError,
    InvalidMessageError,
    ListingNotFoundError,
    ListingUnauthorizedError,
)
from src.domain.listings import Listing, utc_now
from src.domain.users import CurrentUser
from src.repositories.conversations import ConversationRepository
from src.repositories.listings import ListingRepository
from src.repositories.users import UserRepository
from src.services.activity import ActivityLogService

MESSAGES_PAGE_DEFAULT = 50
REPLY_PREVIEW_LENGTH = 140
MESSAGES_PAGE_MAX = 100
CONVERSATIONS_PAGE_DEFAULT = 20
CONVERSATIONS_PAGE_MAX = 50

MESSAGE_RATE_WINDOW = timedelta(minutes=1)
CONVERSATION_START_WINDOW = timedelta(days=1)

DELETED_USER_NAME = "Користувач"


@dataclass(frozen=True)
class ListingCard:
    """Картка оголошення в повідомленні.

    Для недоступного (не `ACTIVE`) оголошення `available` = False, а назва,
    ціна й фото порожні: клієнт показує лише «Оголошення знято». Контакт
    продавця картка не містить ніколи.
    """

    listing_id: UUID
    available: bool
    title: str | None = None
    price: float | None = None
    image_url: str | None = None


@dataclass(frozen=True)
class ReplyPreview:
    """Цитата повідомлення, на яке відповідають: скорочений текст без вкладень."""

    message_id: UUID
    sender_id: UUID
    is_own: bool
    body: str


@dataclass(frozen=True)
class MessageView:
    """Повідомлення для учасника розмови."""

    message_id: UUID
    conversation_id: UUID
    sender_id: UUID
    body: str
    created_at: datetime
    is_own: bool
    listing: ListingCard | None
    reply_to: ReplyPreview | None = None


@dataclass(frozen=True)
class Participant:
    """Співрозмовник: лише публічне ім'я й аватарка, без email і контакту."""

    user_id: UUID
    display_name: str
    avatar_url: str | None


@dataclass(frozen=True)
class ConversationSummary:
    """Рядок списку розмов."""

    conversation_id: UUID
    other: Participant
    last_message: MessageView | None
    last_message_at: datetime
    unread_count: int


@dataclass(frozen=True)
class ConversationPage:
    """Сторінка списку розмов; `next_cursor` — для наступної (старішої)."""

    items: list[ConversationSummary]
    next_cursor: str | None


@dataclass(frozen=True)
class PeerRead:
    """Позиція останнього повідомлення, яке прочитав співрозмовник."""

    created_at: datetime
    message_id: UUID


@dataclass(frozen=True)
class MessagePage:
    """Сторінка повідомлень за зростанням `(created_at, message_id)`.

    `before_cursor` — для старіших повідомлень (None, якщо старіших немає або
    запит був з `after`); `after_cursor` — для опитування нових (позиція
    останнього повідомлення або переданий `after`); `has_more` — у напрямку
    запиту лишилися ще повідомлення понад `limit`.
    """

    items: list[MessageView]
    before_cursor: str | None
    after_cursor: str | None
    has_more: bool
    peer_read: PeerRead | None = None


@dataclass(frozen=True)
class StartResult:
    """Результат старту з оголошення; `created` — розмову створено зараз."""

    conversation_id: UUID
    message: MessageView
    created: bool


class ConversationService:
    """Бізнес-правила чату незалежно від HTTP-фреймворку."""

    def __init__(
        self,
        conversations: ConversationRepository,
        listings: ListingRepository,
        users: UserRepository,
        activity: ActivityLogService,
        settings: ChatSettings | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._conversations = conversations
        self._listings = listings
        self._users = users
        self._activity = activity
        self._settings = settings or ChatSettings()
        self._clock = clock

    # -- зміни ----------------------------------------------------------------

    def start_from_listing(
        self, actor: CurrentUser | None, listing_id: UUID, body: str
    ) -> StartResult:
        """Знаходить або створює розмову з продавцем і надсилає повідомлення.

        Перше повідомлення обов'язкове й несе картку оголошення. Нова розмова
        і її перше повідомлення мають однаковий `created_at`.
        """
        user_id = self._require_active_actor(actor)
        listing = self._listings.get(listing_id)
        if listing is None or not listing.is_public():
            raise ListingNotFoundError("Оголошення не знайдено")
        low, high = normalize_pair(user_id, listing.user_id)
        clean_body = normalize_message_body(body)
        with self._conversations.sender_write_lock(user_id):
            now = self._clock()
            self._check_message_rate(user_id, now)
            conversation = self._conversations.get_by_pair(low, high)
            created = False
            if conversation is None:
                self._check_conversation_starts(user_id, now)
                conversation, created = self._conversations.get_or_create(
                    Conversation(user_low_id=low, user_high_id=high, created_at=now)
                )
            message = self._append(
                conversation.conversation_id,
                user_id,
                clean_body,
                listing.id,
                # Перше повідомлення нової розмови має її created_at: так
                # count_conversations_started_since визначає, хто її почав.
                first_at=now if created else None,
            )
        if created:
            self._activity.record(
                actor,
                ActivityType.CONVERSATION_STARTED,
                listing.id,
                f"Розмова {conversation.conversation_id}",
            )
        return StartResult(
            conversation_id=conversation.conversation_id,
            message=self._message_view(message, user_id),
            created=created,
        )

    def send_message(
        self,
        actor: CurrentUser | None,
        conversation_id: UUID,
        body: str,
        listing_id: UUID | None = None,
        reply_to_id: UUID | None = None,
    ) -> MessageView:
        """Надсилає повідомлення учасником розмови, за потреби з карткою й цитатою."""
        user_id = self._require_active_actor(actor)
        conversation = self._require_participant(conversation_id, user_id)
        clean_body = normalize_message_body(body)
        if listing_id is not None:
            self._require_attachable_listing(listing_id, conversation)
        if reply_to_id is not None and (
            self._conversations.get_message(conversation_id, reply_to_id) is None
        ):
            raise InvalidMessageError("Повідомлення для відповіді не знайдено")
        with self._conversations.sender_write_lock(user_id):
            self._check_message_rate(user_id, self._clock())
            message = self._append(
                conversation.conversation_id,
                user_id,
                clean_body,
                listing_id,
                reply_to_id=reply_to_id,
            )
        return self._message_view(message, user_id)

    def mark_read(
        self,
        actor: CurrentUser | None,
        conversation_id: UUID,
        through: str | None = None,
    ) -> None:
        """Пересуває позначку до показаного повідомлення або до останнього.

        Курсор не дає повідомленню, що надійшло між читанням сторінки та цим
        викликом, стати прочитаним ще до того, як клієнт його отримає.
        """
        user_id = self._require_actor(actor)
        self._require_participant(conversation_id, user_id)
        if through is None:
            last = self._conversations.last_message(conversation_id)
        else:
            key = decode_cursor(through)
            last = self._conversations.get_message(conversation_id, key[1])
            if last is None or last.key != key:
                raise InvalidChatCursorError("Некоректний курсор прочитання")
        if last is not None:
            self._conversations.mark_read(conversation_id, user_id, last.key)

    def _append(
        self,
        conversation_id: UUID,
        sender_id: UUID,
        body: str,
        listing_id: UUID | None,
        first_at: datetime | None = None,
        reply_to_id: UUID | None = None,
    ) -> Message:
        """Додає повідомлення під блокуванням розмови зі строго зростаючим часом.

        Записи в розмову йдуть по черзі до commit, а `created_at` нового
        повідомлення більший за `last_message_at`, тож повідомлення не може
        з'явитися позаду курсора `after`, який клієнт уже отримав.
        """
        conversation = self._conversations.lock_conversation(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError("Розмову не знайдено")
        created_at = first_at or _later_than(
            self._clock(), as_utc(conversation.last_message_at)
        )
        return self._conversations.add_message(
            Message(
                conversation_id=conversation_id,
                sender_id=sender_id,
                body=body,
                listing_id=listing_id,
                created_at=created_at,
                reply_to_id=reply_to_id,
            )
        )

    # -- читання --------------------------------------------------------------

    def list_conversations(
        self,
        actor: CurrentUser | None,
        limit: int = CONVERSATIONS_PAGE_DEFAULT,
        cursor: str | None = None,
    ) -> ConversationPage:
        """Розмови користувача від найсвіжішої активності."""
        user_id = self._require_actor(actor)
        _check_limit(limit, CONVERSATIONS_PAGE_MAX)
        before = decode_cursor(cursor) if cursor is not None else None
        rows = self._conversations.list_for_user(user_id, limit + 1, before)
        page = rows[:limit]
        next_cursor = None
        if len(rows) > limit:
            last = page[-1]
            next_cursor = encode_cursor((last.last_message_at, last.conversation_id))
        return ConversationPage(
            items=[self._summary(item, user_id) for item in page],
            next_cursor=next_cursor,
        )

    def list_messages(
        self,
        actor: CurrentUser | None,
        conversation_id: UUID,
        after: str | None = None,
        before: str | None = None,
        limit: int = MESSAGES_PAGE_DEFAULT,
    ) -> MessagePage:
        """Повідомлення розмови для учасника; курсори взаємовиключні."""
        user_id = self._require_actor(actor)
        if after is not None and before is not None:
            raise InvalidChatCursorError("Курсори after і before взаємовиключні")
        _check_limit(limit, MESSAGES_PAGE_MAX)
        after_key = decode_cursor(after) if after is not None else None
        before_key = decode_cursor(before) if before is not None else None
        conversation = self._require_participant(conversation_id, user_id)
        rows = self._conversations.list_messages(
            conversation_id, limit + 1, after=after_key, before=before_key
        )
        has_more = len(rows) > limit
        if after_key is not None:
            page = rows[:limit]
            before_cursor = None
        else:
            page = rows[-limit:]
            before_cursor = encode_cursor(page[0].key) if has_more else None
        after_cursor = encode_cursor(page[-1].key) if page else after
        peer_marker = conversation.read_marker(conversation.other_participant(user_id))
        return MessagePage(
            items=[self._message_view(item, user_id) for item in page],
            before_cursor=before_cursor,
            after_cursor=after_cursor,
            has_more=has_more,
            peer_read=PeerRead(*peer_marker) if peer_marker else None,
        )

    def unread_count(self, actor: CurrentUser | None) -> int:
        """Сума непрочитаних у всіх розмовах користувача (значок у меню)."""
        return self._conversations.total_unread(self._require_actor(actor))

    # -- правила --------------------------------------------------------------

    def _require_actor(self, actor: CurrentUser | None) -> UUID:
        if actor is None:
            raise ListingUnauthorizedError("Потрібна ідентифікація користувача")
        return actor.user_id

    def _require_active_actor(self, actor: CurrentUser | None) -> UUID:
        user_id = self._require_actor(actor)
        user = self._users.get_by_id(user_id)
        if user is None or user.is_blocked:
            raise ConversationForbiddenError("Акаунт заблоковано")
        return user_id

    def _require_participant(
        self, conversation_id: UUID, user_id: UUID
    ) -> Conversation:
        conversation = self._conversations.get(conversation_id)
        if conversation is None or not conversation.has_participant(user_id):
            raise ConversationNotFoundError("Розмову не знайдено")
        return conversation

    def _require_attachable_listing(
        self, listing_id: UUID, conversation: Conversation
    ) -> None:
        """Прикріпити можна лише ACTIVE-оголошення одного з учасників."""
        listing = self._listings.get(listing_id)
        if (
            listing is None
            or not listing.is_public()
            or not conversation.has_participant(listing.user_id)
        ):
            raise ListingNotFoundError("Оголошення не знайдено")

    def _check_message_rate(self, user_id: UUID, now: datetime) -> None:
        sent = self._conversations.count_messages_since(
            user_id, now - MESSAGE_RATE_WINDOW
        )
        if sent >= self._settings.message_rate_per_minute:
            raise ChatRateLimitError(
                "Забагато повідомлень, спробуйте за хвилину",
                retry_after_seconds=_seconds(MESSAGE_RATE_WINDOW),
            )

    def _check_conversation_starts(self, user_id: UUID, now: datetime) -> None:
        started = self._conversations.count_conversations_started_since(
            user_id, now - CONVERSATION_START_WINDOW
        )
        if started >= self._settings.conversation_starts_per_day:
            raise ChatRateLimitError(
                "Забагато нових розмов за добу, спробуйте пізніше",
                retry_after_seconds=_seconds(CONVERSATION_START_WINDOW),
            )

    # -- представлення --------------------------------------------------------

    def _message_view(self, message: Message, viewer_id: UUID) -> MessageView:
        return MessageView(
            message_id=message.message_id,
            conversation_id=message.conversation_id,
            sender_id=message.sender_id,
            body=message.body,
            created_at=message.key[0],
            is_own=message.sender_id == viewer_id,
            listing=self._listing_card(message.listing_id),
            reply_to=self._reply_preview(message, viewer_id),
        )

    def _reply_preview(self, message: Message, viewer_id: UUID) -> ReplyPreview | None:
        if message.reply_to_id is None:
            return None
        target = self._conversations.get_message(
            message.conversation_id, message.reply_to_id
        )
        if target is None:
            return None
        body = target.body
        if len(body) > REPLY_PREVIEW_LENGTH:
            body = body[: REPLY_PREVIEW_LENGTH - 1].rstrip() + "…"
        return ReplyPreview(
            message_id=target.message_id,
            sender_id=target.sender_id,
            is_own=target.sender_id == viewer_id,
            body=body,
        )

    def _listing_card(self, listing_id: UUID | None) -> ListingCard | None:
        if listing_id is None:
            return None
        listing = self._listings.get(listing_id)
        if listing is None or not listing.is_public():
            return ListingCard(listing_id=listing_id, available=False)
        return ListingCard(
            listing_id=listing.id,
            available=True,
            title=listing.title,
            price=listing.price,
            image_url=_cover_url(listing),
        )

    def _summary(
        self, conversation: Conversation, viewer_id: UUID
    ) -> ConversationSummary:
        other_id = conversation.other_participant(viewer_id)
        other = self._users.get_by_id(other_id)
        last = self._conversations.last_message(conversation.conversation_id)
        return ConversationSummary(
            conversation_id=conversation.conversation_id,
            other=Participant(
                user_id=other_id,
                display_name=other.display_name if other else DELETED_USER_NAME,
                avatar_url=other.avatar_url if other else None,
            ),
            last_message=self._message_view(last, viewer_id) if last else None,
            last_message_at=as_utc(conversation.last_message_at),
            unread_count=self._conversations.unread_count(
                conversation.conversation_id, viewer_id
            ),
        )


def _check_limit(limit: int, maximum: int) -> None:
    if not 1 <= limit <= maximum:
        raise ValueError(f"limit має бути від 1 до {maximum}")


def _later_than(now: datetime, previous: datetime) -> datetime:
    """`now` або найменший час, строго більший за `previous` (годинник міг
    відстати або два записи отримали однакову мітку)."""
    return now if now > previous else previous + timedelta(microseconds=1)


def _seconds(window: timedelta) -> int:
    return int(window.total_seconds())


def _cover_url(listing: Listing) -> str | None:
    """Мініатюра першого за порядком фото оголошення."""
    if not listing.images:
        return None
    cover = min(listing.images, key=lambda image: image.display_order)
    return cover.thumbnail_url or cover.image_url
