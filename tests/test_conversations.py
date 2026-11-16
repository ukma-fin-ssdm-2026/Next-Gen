"""Модульні тести ядра чату без HTTP (ADR-005).

- домен: нормалізація пари й тексту, курсор, позначка прочитаного, налаштування;
- контракт сховища розмов (`ConversationRepositoryContract`), який перевіряється
  на in-memory адаптері тут і на PostgreSQL-адаптері в
  `tests/test_postgres_repositories.py`;
- `ConversationService`: правила доступу, картка оголошення, курсори,
  прочитання й ліміти.
"""

import base64
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.conversations import (
    DEFAULT_CHAT_CONVERSATION_STARTS_PER_DAY,
    DEFAULT_CHAT_MESSAGE_RATE_PER_MINUTE,
    DEFAULT_CHAT_RETENTION_DAYS,
    MESSAGE_BODY_MAX_LENGTH,
    ChatSettings,
    Conversation,
    Message,
    as_utc,
    decode_cursor,
    encode_cursor,
    normalize_message_body,
    normalize_pair,
)
from src.domain.activity import ActivityType
from src.domain.exceptions import (
    ChatRateLimitError,
    ConversationForbiddenError,
    ConversationNotFoundError,
    InvalidChatCursorError,
    InvalidMessageError,
    ListingNotFoundError,
    ListingUnauthorizedError,
)
from src.domain.listings import (
    SEED_CATEGORY_ID,
    Listing,
    ListingImage,
    ListingStatus,
)
from src.domain.users import CurrentUser, User, UserRole
from src.repositories.conversations import InMemoryConversationRepository
from src.repositories.listings import InMemoryListingRepository
from src.repositories.moderation import InMemoryModerationActionRepository
from src.repositories.support import InMemoryActivityRepository
from src.repositories.users import InMemoryUserRepository
from src.services.activity import ActivityLogService
from src.services.conversations import (
    MESSAGES_PAGE_MAX,
    ConversationService,
    ListingCard,
    Participant,
)

T0 = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)

# Невидимі символи задаємо кодами, щоб їх не було у вихідному коді.
ZERO_WIDTH_JOINER = chr(0x200D)
RIGHT_TO_LEFT_OVERRIDE = chr(0x202E)
FAMILY_EMOJI = "Сім'я 👨" + ZERO_WIDTH_JOINER + "👩" + ZERO_WIDTH_JOINER + "👧"

# Два UUID з відомим порядком: LOW < HIGH.
LOW_ID = UUID("00000000-0000-4000-8000-000000000001")
HIGH_ID = UUID("ffffffff-ffff-4fff-bfff-ffffffffffff")


# ---------------------------------------------------------------------------
# Домен
# ---------------------------------------------------------------------------


def test_pair_is_normalized_regardless_of_order() -> None:
    """[TP-050]
    Пара A,B і B,A дає ту саму впорядковану пару, тож розмова одна на двох.
    """
    assert normalize_pair(HIGH_ID, LOW_ID) == (LOW_ID, HIGH_ID)
    assert normalize_pair(LOW_ID, HIGH_ID) == (LOW_ID, HIGH_ID)


def test_conversation_with_self_is_forbidden() -> None:
    """[TP-050]
    Розмова із самим собою заборонена ще на рівні домену.
    """
    with pytest.raises(ConversationForbiddenError):
        normalize_pair(LOW_ID, LOW_ID)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Привіт!  ", "Привіт!"),
        ("x", "x"),
        ("я" * MESSAGE_BODY_MAX_LENGTH, "я" * MESSAGE_BODY_MAX_LENGTH),
        ("<script>alert(1)</script>", "<script>alert(1)</script>"),
        ("'; DROP TABLE messages; --", "'; DROP TABLE messages; --"),
        (FAMILY_EMOJI, FAMILY_EMOJI),
    ],
    ids=["trim", "min", "max", "xss-as-text", "sql-as-text", "emoji-zwj"],
)
def test_message_body_accepts_valid_text(raw: str, expected: str) -> None:
    """[TP-050]
    Текст обрізається; межі 1 і 1000 символів допустимі; XSS і SQL-подібний
    ввід зберігаються як звичайний текст; емодзі зі з'єднувачем ZWJ дозволені.
    """
    assert normalize_message_body(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "я" * (MESSAGE_BODY_MAX_LENGTH + 1),
        "таб\tтут",
        "нуль\x00байт",
        "del\x7f",
        "підміна " + RIGHT_TO_LEFT_OVERRIDE + "тексту",
        None,
    ],
    ids=["empty", "spaces", "too-long", "tab", "nul", "del", "bidi", "none"],
)
def test_message_body_rejects_invalid_text(raw) -> None:
    """[TP-050]
    Порожній, задовгий текст, керівні символи (Cc) і символи підміни напрямку
    тексту відхиляються.
    """
    with pytest.raises(InvalidMessageError):
        normalize_message_body(raw)


def test_message_body_keeps_line_breaks() -> None:
    """[TP-050] Перенос рядка дозволений: CRLF зводиться до LF, 3+ переноси до двох."""
    assert normalize_message_body("  рядок\r\nщe рядок  ") == "рядок\nщe рядок"
    assert normalize_message_body("а\n\n\n\n\nб") == "а\n\nб"


def test_message_entity_normalizes_body_and_rejects_invalid() -> None:
    """[TP-050]
    Сутність Message сама нормалізує текст, тож сховище не отримає невалідний.
    """
    message = Message(conversation_id=uuid4(), sender_id=LOW_ID, body="  ok  ")
    assert message.body == "ok"
    with pytest.raises(InvalidMessageError):
        Message(conversation_id=uuid4(), sender_id=LOW_ID, body=" ")


def test_cursor_round_trip_keeps_time_and_id() -> None:
    """[TP-050]
    Курсор кодує пару (created_at, message_id) і розкодовується без втрат.
    """
    key = (T0 + timedelta(microseconds=123), uuid4())
    token = encode_cursor(key)
    assert "|" not in token and "=" not in token
    assert decode_cursor(token) == key


def _token(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


@pytest.mark.parametrize(
    "token",
    [
        "",
        "не-base64!",
        "A" * 200,
        _token("без-роздільника"),
        _token("2026-11-16T12:00:00|not-a-uuid"),
        _token(f"вчора|{uuid4()}"),
        _token(f"2026-11-16T12:00:00|{uuid4()}"),
        _token(f"2026-11-16T12:00:00+00:00|{uuid4()}|зайве"),
        None,
    ],
    ids=[
        "empty",
        "not-base64",
        "too-long",
        "no-separator",
        "bad-uuid",
        "bad-time",
        "naive-time",
        "extra-part",
        "none",
    ],
)
def test_invalid_cursor_is_rejected(token) -> None:
    """[TP-050]
    Пошкоджений або підроблений курсор дає InvalidChatCursorError, а не 500.
    """
    with pytest.raises(InvalidChatCursorError):
        decode_cursor(token)


def test_conversation_requires_ordered_pair_and_knows_participants() -> None:
    """[TP-050]
    Розмова приймає лише впорядковану пару, знає співрозмовника й учасників.
    """
    conversation = Conversation(user_low_id=LOW_ID, user_high_id=HIGH_ID, created_at=T0)
    assert conversation.last_message_at == T0
    assert conversation.other_participant(LOW_ID) == HIGH_ID
    assert conversation.other_participant(HIGH_ID) == LOW_ID
    assert not conversation.has_participant(uuid4())
    with pytest.raises(ValueError):
        conversation.other_participant(uuid4())
    with pytest.raises(ValueError):
        Conversation(user_low_id=HIGH_ID, user_high_id=LOW_ID)


def test_read_marker_only_moves_forward() -> None:
    """[TP-050]
    Позначка прочитаного пересувається лише вперед і окремо для кожного учасника.
    """
    conversation = Conversation(user_low_id=LOW_ID, user_high_id=HIGH_ID)
    older = (T0, UUID(int=1))
    newer = (T0, UUID(int=2))
    assert conversation.read_marker(LOW_ID) is None
    assert conversation.set_read_marker(LOW_ID, newer)
    assert not conversation.set_read_marker(LOW_ID, older)
    assert conversation.read_marker(LOW_ID) == newer
    assert conversation.read_marker(HIGH_ID) is None
    with pytest.raises(ValueError):
        conversation.read_marker(uuid4())


def test_chat_settings_defaults_and_env(monkeypatch) -> None:
    """[TP-050]
    Ліміти за замовчуванням — 30/хв, 10/добу, 365 днів; змінні середовища
    перекривають їх, а некоректне значення зупиняє старт.
    """
    for name in (
        "CHAT_MESSAGE_RATE_PER_MINUTE",
        "CHAT_CONVERSATION_STARTS_PER_DAY",
        "CHAT_RETENTION_DAYS",
    ):
        monkeypatch.delenv(name, raising=False)
    assert ChatSettings.from_env() == ChatSettings(
        DEFAULT_CHAT_MESSAGE_RATE_PER_MINUTE,
        DEFAULT_CHAT_CONVERSATION_STARTS_PER_DAY,
        DEFAULT_CHAT_RETENTION_DAYS,
    )
    monkeypatch.setenv("CHAT_MESSAGE_RATE_PER_MINUTE", "5")
    assert ChatSettings.from_env().message_rate_per_minute == 5
    for raw in ("0", "-1", "abc"):
        monkeypatch.setenv("CHAT_RETENTION_DAYS", raw)
        with pytest.raises(RuntimeError, match="CHAT_RETENTION_DAYS"):
            ChatSettings.from_env()


def _oid(n: int) -> UUID:
    """UUID із відомим порядком і літерою в hex.

    SQLite зберігає UUID як 32 hex-символи; рядок лише з цифр отримав би
    числовий тип, тому префікс «a» тримає значення текстом і зберігає порядок.
    """
    return UUID(f"a{n:031x}")


# ---------------------------------------------------------------------------
# Контракт сховища розмов
# ---------------------------------------------------------------------------


class ConversationRepositoryContract:
    """Спільні сценарії для будь-якої реалізації ConversationRepository.

    Підклас має надати фікстури `repo` і `new_user` (створює користувача й
    повертає його UUID) та `new_listing` (оголошення продавця, повертає UUID).
    """

    def _start(self, repo, first: UUID, second: UUID, at: datetime = T0):
        low, high = normalize_pair(first, second)
        conversation, created = repo.get_or_create(
            Conversation(user_low_id=low, user_high_id=high, created_at=at)
        )
        if created:
            repo.add_message(
                Message(
                    conversation_id=conversation.conversation_id,
                    sender_id=first,
                    body="Перше повідомлення",
                    created_at=at,
                )
            )
        return conversation, created

    def _send(self, repo, conversation, sender, at, body="текст", message_id=None):
        message = Message(
            conversation_id=conversation.conversation_id,
            sender_id=sender,
            body=body,
            created_at=at,
            message_id=message_id or uuid4(),
        )
        return repo.add_message(message)

    def test_get_or_create_returns_one_conversation_per_pair(self, repo, new_user):
        """[TP-051]
        Друга спроба для пари в зворотному порядку повертає ту саму розмову.
        """
        a, b = new_user(), new_user()
        first, created = self._start(repo, a, b)
        second, created_again = self._start(repo, b, a)
        assert created and not created_again
        assert second.conversation_id == first.conversation_id
        low, high = normalize_pair(a, b)
        assert repo.get_by_pair(low, high).conversation_id == first.conversation_id
        assert repo.get(first.conversation_id).participants == (low, high)
        assert repo.get(uuid4()) is None

    def test_add_message_moves_last_activity_forward_only(self, repo, new_user):
        """[TP-051]
        last_message_at рухається вперед і не відкочується старішим повідомленням.
        """
        a, b = new_user(), new_user()
        conversation, _ = self._start(repo, a, b)
        self._send(repo, conversation, b, T0 + timedelta(minutes=5))
        self._send(repo, conversation, a, T0 + timedelta(minutes=1))
        stored = repo.get(conversation.conversation_id)
        assert stored.last_message_at.astimezone(timezone.utc) == T0 + timedelta(
            minutes=5
        )
        assert repo.last_message(conversation.conversation_id).created_at.astimezone(
            timezone.utc
        ) == T0 + timedelta(minutes=5)

    def test_messages_with_same_timestamp_are_not_lost(self, repo, new_user):
        """[TP-051]
        Повідомлення з однаковим created_at впорядковані за id, курсори after і
        before на межі не гублять і не дублюють жодного з них.
        """
        a, b = new_user(), new_user()
        conversation, _ = self._start(repo, a, b)
        same = T0 + timedelta(minutes=1)
        ids = [_oid(i) for i in (3, 1, 2)]
        for message_id in ids:
            self._send(repo, conversation, b, same, message_id=message_id)
        items = repo.list_messages(conversation.conversation_id, limit=10)
        assert [m.message_id for m in items[1:]] == sorted(ids)
        middle = items[2].key
        after = repo.list_messages(conversation.conversation_id, limit=10, after=middle)
        before = repo.list_messages(
            conversation.conversation_id, limit=10, before=middle
        )
        assert [m.message_id for m in after] == [_oid(3)]
        assert [m.message_id for m in before] == [items[0].message_id, _oid(1)]

    def test_list_messages_pages_with_limit(self, repo, new_user):
        """[TP-051]
        Без курсора — останні limit повідомлень за зростанням; after бере перші
        новіші, before — останні старіші.
        """
        a, b = new_user(), new_user()
        conversation, _ = self._start(repo, a, b)
        for minute in range(1, 6):
            self._send(repo, conversation, a, T0 + timedelta(minutes=minute))
        cid = conversation.conversation_id
        all_items = repo.list_messages(cid, limit=100)
        assert len(all_items) == 6
        latest = repo.list_messages(cid, limit=2)
        assert [m.key for m in latest] == [m.key for m in all_items[-2:]]
        after = repo.list_messages(cid, limit=2, after=all_items[1].key)
        assert [m.key for m in after] == [m.key for m in all_items[2:4]]
        before = repo.list_messages(cid, limit=2, before=all_items[4].key)
        assert [m.key for m in before] == [m.key for m in all_items[2:4]]

    def test_list_for_user_orders_by_activity_and_pages(self, repo, new_user):
        """[TP-051]
        Розмови учасника йдуть від найсвіжішої активності; чужі не потрапляють.
        """
        me, x, y, stranger = new_user(), new_user(), new_user(), new_user()
        older, _ = self._start(repo, me, x, T0)
        newer, _ = self._start(repo, y, me, T0 + timedelta(minutes=1))
        self._start(repo, x, stranger, T0 + timedelta(minutes=2))
        items = repo.list_for_user(me, limit=10)
        assert [c.conversation_id for c in items] == [
            newer.conversation_id,
            older.conversation_id,
        ]
        cursor = (
            items[0].last_message_at.astimezone(timezone.utc),
            items[0].conversation_id,
        )
        page = repo.list_for_user(me, limit=10, before=cursor)
        assert [c.conversation_id for c in page] == [older.conversation_id]

    def test_unread_count_respects_exact_read_marker(self, repo, new_user):
        """[TP-051]
        Позначка прочитаного не робить прочитаним новіше повідомлення з тим самим
        created_at; власні повідомлення не рахуються непрочитаними.
        """
        a, b = new_user(), new_user()
        conversation, _ = self._start(repo, a, b)
        cid = conversation.conversation_id
        same = T0 + timedelta(minutes=1)
        first = self._send(repo, conversation, a, same, message_id=_oid(10))
        self._send(repo, conversation, a, same, message_id=_oid(20))
        assert repo.unread_count(cid, a) == 0
        assert repo.unread_count(cid, b) == 3
        assert repo.mark_read(cid, b, first.key)
        assert repo.unread_count(cid, b) == 1
        assert not repo.mark_read(cid, b, (T0, _oid(0)))
        assert repo.unread_count(cid, b) == 1
        assert repo.unread_count(cid, new_user()) == 0

    def test_mark_read_tracks_each_participant_separately(self, repo, new_user):
        """[TP-051]
        Позначка прочитаного зберігається окремо для учасника low і high;
        для неіснуючої розмови вона не ставиться, а два курсори разом — помилка.
        """
        a, b = new_user(), new_user()
        conversation, _ = self._start(repo, a, b)
        cid = conversation.conversation_id
        reply = self._send(repo, conversation, b, T0 + timedelta(minutes=1))
        low, high = conversation.participants
        assert repo.mark_read(cid, low, reply.key)
        assert repo.mark_read(cid, high, reply.key)
        stored = repo.get(cid)
        assert stored.read_marker(low) == reply.key
        assert stored.read_marker(high) == reply.key
        assert repo.unread_count(cid, a) == 0 and repo.unread_count(cid, b) == 0
        assert not repo.mark_read(uuid4(), a, reply.key)
        with pytest.raises(ValueError):
            repo.list_messages(cid, limit=1, after=reply.key, before=reply.key)

    def test_total_unread_sums_all_conversations(self, repo, new_user):
        """[TP-051]
        Загальний лічильник непрочитаних — сума по всіх розмовах користувача.
        """
        me, x, y = new_user(), new_user(), new_user()
        self._start(repo, x, me)
        second, _ = self._start(repo, y, me, T0 + timedelta(minutes=1))
        self._send(repo, second, y, T0 + timedelta(minutes=2))
        assert repo.total_unread(me) == 3
        assert repo.total_unread(x) == 0

    def test_rate_counters_use_since_boundary(self, repo, new_user):
        """[TP-051]
        Лічильники для лімітів: повідомлення від since включно; розмову почав
        відправник першого повідомлення.
        """
        a, b, c = new_user(), new_user(), new_user()
        conversation, _ = self._start(repo, a, b, T0)
        self._start(repo, c, a, T0 + timedelta(minutes=1))
        self._send(repo, conversation, a, T0 + timedelta(minutes=2))
        assert repo.count_messages_since(a, T0) == 2
        assert repo.count_messages_since(a, T0 + timedelta(minutes=2)) == 1
        assert repo.count_messages_since(a, T0 + timedelta(minutes=3)) == 0
        assert repo.count_conversations_started_since(a, T0) == 1
        assert repo.count_conversations_started_since(c, T0) == 1
        assert repo.count_conversations_started_since(b, T0) == 0
        assert repo.count_conversations_started_since(a, T0 + timedelta(seconds=1)) == 0

    def test_cleanup_deletes_old_messages_in_batches_then_empty_conversations(
        self, repo, new_user
    ):
        """[TP-051]
        Очищення видаляє лише старі повідомлення пакетами, потім порожні розмови;
        повторний запуск нічого не змінює.
        """
        a, b, c = new_user(), new_user(), new_user()
        old, _ = self._start(repo, a, b, T0)
        self._send(repo, old, b, T0 + timedelta(minutes=1))
        mixed, _ = self._start(repo, a, c, T0)
        fresh = self._send(repo, mixed, c, T0 + timedelta(days=400))
        cutoff = T0 + timedelta(days=1)
        assert repo.delete_messages_older_than(cutoff, batch_size=2) == 2
        assert repo.delete_messages_older_than(cutoff, batch_size=2) == 1
        assert repo.delete_messages_older_than(cutoff, batch_size=2) == 0
        assert repo.delete_empty_conversations() == 1
        assert repo.delete_empty_conversations() == 0
        assert repo.get(old.conversation_id) is None
        low, high = normalize_pair(a, b)
        assert repo.get_by_pair(low, high) is None
        remaining = repo.list_messages(mixed.conversation_id, limit=10)
        assert [m.message_id for m in remaining] == [fresh.message_id]

    def test_write_locks_return_current_conversation_state(self, repo, new_user):
        """[TP-051]
        Блокування відправника працює як контекстний менеджер, а блокування
        розмови повертає її актуальний `last_message_at` (або None).
        """
        a, b = new_user(), new_user()
        conversation, _ = self._start(repo, a, b)
        with repo.sender_write_lock(a):
            self._send(repo, conversation, a, T0 + timedelta(seconds=7))
            locked = repo.lock_conversation(conversation.conversation_id)
        assert as_utc(locked.last_message_at) == T0 + timedelta(seconds=7)
        assert repo.lock_conversation(uuid4()) is None


class TestInMemoryConversationRepository(ConversationRepositoryContract):
    """[TP-051] Контракт сховища розмов на in-memory адаптері."""

    @pytest.fixture
    def repo(self):
        return InMemoryConversationRepository()

    @pytest.fixture
    def new_user(self):
        return uuid4

    def test_in_memory_rejects_message_for_unknown_conversation(self, repo):
        """[TP-051]
        Повідомлення до неіснуючої розмови не додається; limit=0 дає порожній список.
        """
        with pytest.raises(KeyError):
            repo.add_message(
                Message(conversation_id=uuid4(), sender_id=LOW_ID, body="x")
            )
        assert repo.list_messages(uuid4(), limit=0) == []


# ---------------------------------------------------------------------------
# ConversationService
# ---------------------------------------------------------------------------


class _Clock:
    """Керований годинник: тести рухають час без sleep."""

    def __init__(self, now: datetime = T0) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta) -> None:
        self.now += timedelta(**delta)


class _Chat:
    """Сервіс чату на in-memory сховищах з користувачами й оголошеннями."""

    def __init__(self, settings: ChatSettings | None = None) -> None:
        self.clock = _Clock()
        self.users = InMemoryUserRepository()
        self.listings = InMemoryListingRepository([])
        self.repo = InMemoryConversationRepository()
        self.events = InMemoryActivityRepository()
        self.service = ConversationService(
            self.repo,
            self.listings,
            self.users,
            ActivityLogService(
                self.events, self.users, InMemoryModerationActionRepository()
            ),
            settings,
            clock=self.clock,
        )

    def user(self, name: str, *, blocked: bool = False) -> CurrentUser:
        user = User(
            tenant_id=uuid4(),
            entra_object_id=uuid4(),
            email=f"{uuid4().hex}@ukma.edu.ua",
            display_name=name,
            avatar_url=f"/uploads/{name}.webp",
            is_blocked=blocked,
        )
        self.users.save(user)
        return CurrentUser(
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            entra_object_id=user.entra_object_id,
            email=user.email,
            display_name=user.display_name,
            role=UserRole.USER,
        )

    def listing(self, seller: CurrentUser, title: str = "Калькулятор") -> Listing:
        return self.listings.add(
            Listing(
                title=title,
                description="Робочий",
                price=250.0,
                category_id=SEED_CATEGORY_ID,
                contact="@seller_telegram",
                user_id=seller.user_id,
                images=[
                    ListingImage(image_url="/uploads/2.webp", display_order=1),
                    ListingImage(
                        image_url="/uploads/1.webp",
                        thumbnail_url="/uploads/1_thumb.webp",
                        display_order=0,
                    ),
                ],
            )
        )

    def withdraw(self, listing: Listing) -> None:
        listing.status = ListingStatus.WITHDRAWN
        self.listings.save(listing)

    def started_events(self) -> list:
        return [
            event
            for event in self.events.list_events(False)
            if event.action_type == ActivityType.CONVERSATION_STARTED
        ]


@pytest.fixture
def chat() -> _Chat:
    return _Chat()


def test_start_from_listing_creates_conversation_with_first_message(chat) -> None:
    """[TP-053]
    Покупець пише продавцю: одна розмова, перше повідомлення з карткою
    оголошення, той самий created_at і подія без тексту повідомлення.
    """
    seller, buyer = chat.user("Продавець"), chat.user("Покупець")
    listing = chat.listing(seller)

    result = chat.service.start_from_listing(buyer, listing.id, "  Ще продаєте?  ")

    assert result.created is True
    conversation = chat.repo.get(result.conversation_id)
    assert set(conversation.participants) == {seller.user_id, buyer.user_id}
    assert conversation.created_at == result.message.created_at == T0
    assert result.message.body == "Ще продаєте?"
    assert result.message.is_own is True
    assert result.message.listing == ListingCard(
        listing_id=listing.id,
        available=True,
        title="Калькулятор",
        price=250.0,
        image_url="/uploads/1_thumb.webp",
    )
    [event] = chat.started_events()
    assert event.actor_id == buyer.user_id
    assert event.listing_id == listing.id
    assert "Ще продаєте" not in event.details
    assert str(result.conversation_id) in event.details


def test_second_start_reuses_conversation_for_pair(chat) -> None:
    """[TP-053]
    Повторний старт (і з іншого оголошення того ж продавця) не створює
    другої розмови й другої події CONVERSATION_STARTED.
    """
    seller, buyer = chat.user("Продавець"), chat.user("Покупець")
    first = chat.service.start_from_listing(buyer, chat.listing(seller).id, "Привіт")
    chat.clock.advance(seconds=5)
    other_listing = chat.listing(seller, "Підручник")

    second = chat.service.start_from_listing(buyer, other_listing.id, "А це?")

    assert second.created is False
    assert second.conversation_id == first.conversation_id
    assert second.message.listing.title == "Підручник"
    assert len(chat.started_events()) == 1
    page = chat.service.list_messages(seller, first.conversation_id)
    assert [m.body for m in page.items] == ["Привіт", "А це?"]


def test_start_rejects_own_blocked_and_unavailable_listing(chat) -> None:
    """[TP-053]
    Власник не пише сам собі (403), заблокований не пише (403), зняте чи
    неіснуюче оголошення — 404; жодна спроба нічого не створює.
    """
    seller, buyer = chat.user("Продавець"), chat.user("Покупець")
    blocked = chat.user("Заблокований", blocked=True)
    listing = chat.listing(seller)
    withdrawn = chat.listing(seller, "Знято")
    chat.withdraw(withdrawn)

    with pytest.raises(ConversationForbiddenError):
        chat.service.start_from_listing(seller, listing.id, "Сам собі")
    with pytest.raises(ConversationForbiddenError):
        chat.service.start_from_listing(blocked, listing.id, "Привіт")
    with pytest.raises(ListingNotFoundError):
        chat.service.start_from_listing(buyer, withdrawn.id, "Привіт")
    with pytest.raises(ListingNotFoundError):
        chat.service.start_from_listing(buyer, uuid4(), "Привіт")
    assert chat.service.list_conversations(buyer).items == []
    assert chat.started_events() == []


@pytest.mark.parametrize("body", ["", "   ", "x" * (MESSAGE_BODY_MAX_LENGTH + 1)])
def test_start_with_invalid_body_creates_nothing(chat, body) -> None:
    """[TP-053]
    Порожній або задовгий текст — InvalidMessageError (422) до створення розмови.
    """
    seller, buyer = chat.user("Продавець"), chat.user("Покупець")
    listing = chat.listing(seller)

    with pytest.raises(InvalidMessageError):
        chat.service.start_from_listing(buyer, listing.id, body)

    assert chat.service.list_conversations(buyer).items == []
    assert chat.service.list_conversations(seller).items == []


def test_anonymous_actor_is_unauthorized_everywhere(chat) -> None:
    """[TP-053]
    Без користувача кожна операція — ListingUnauthorizedError (401).
    """
    seller = chat.user("Продавець")
    listing_id, conversation_id = chat.listing(seller).id, uuid4()
    calls = [
        lambda: chat.service.start_from_listing(None, listing_id, "x"),
        lambda: chat.service.send_message(None, conversation_id, "x"),
        lambda: chat.service.list_conversations(None),
        lambda: chat.service.list_messages(None, conversation_id),
        lambda: chat.service.mark_read(None, conversation_id),
        lambda: chat.service.unread_count(None),
    ]
    for call in calls:
        with pytest.raises(ListingUnauthorizedError):
            call()


def test_non_participant_gets_not_found(chat) -> None:
    """[TP-053]
    Чужа й неіснуюча розмова однаково дають ConversationNotFoundError (404,
    IDOR): не можна читати, писати чи позначати прочитаним.
    """
    seller, buyer, stranger = (
        chat.user("Продавець"),
        chat.user("Покупець"),
        chat.user("Сторонній"),
    )
    started = chat.service.start_from_listing(buyer, chat.listing(seller).id, "Hi")

    for conversation_id in (started.conversation_id, uuid4()):
        with pytest.raises(ConversationNotFoundError):
            chat.service.list_messages(stranger, conversation_id)
        with pytest.raises(ConversationNotFoundError):
            chat.service.send_message(stranger, conversation_id, "Я тут")
        with pytest.raises(ConversationNotFoundError):
            chat.service.mark_read(stranger, conversation_id)
    assert chat.repo.unread_count(started.conversation_id, seller.user_id) == 1


def test_blocked_participant_cannot_send(chat) -> None:
    """[TP-053]
    Учасника, якого заблокували після старту, сервіс не пускає писати (403).
    """
    seller, buyer = chat.user("Продавець"), chat.user("Покупець")
    started = chat.service.start_from_listing(buyer, chat.listing(seller).id, "Hi")
    user = chat.users.get_by_id(buyer.user_id)
    user.is_blocked = True
    chat.users.save(user)

    with pytest.raises(ConversationForbiddenError):
        chat.service.send_message(buyer, started.conversation_id, "Ще раз")


def test_attached_listing_must_be_active_and_belong_to_participant(chat) -> None:
    """[TP-053]
    До повідомлення можна прикріпити лише ACTIVE-оголошення учасника; чуже,
    зняте чи неіснуюче — однаковий ListingNotFoundError (404).
    """
    seller, buyer, stranger = (
        chat.user("Продавець"),
        chat.user("Покупець"),
        chat.user("Сторонній"),
    )
    started = chat.service.start_from_listing(buyer, chat.listing(seller).id, "Hi")
    conversation_id = started.conversation_id
    foreign = chat.listing(stranger, "Чуже")
    withdrawn = chat.listing(seller, "Знято")
    chat.withdraw(withdrawn)

    for listing_id in (foreign.id, withdrawn.id, uuid4()):
        with pytest.raises(ListingNotFoundError):
            chat.service.send_message(buyer, conversation_id, "Глянь", listing_id)

    own = chat.listing(buyer, "Обміняю на")
    message = chat.service.send_message(buyer, conversation_id, "Обмін?", own.id)
    assert message.listing.title == "Обміняю на"
    assert len(chat.service.list_messages(buyer, conversation_id).items) == 2


def test_reply_quotes_message_of_same_conversation(chat) -> None:
    """[TP-053] Відповідь цитує повідомлення своєї розмови; чужі й вигадані id — 422."""
    seller, buyer, stranger = (
        chat.user("Продавець"),
        chat.user("Покупець"),
        chat.user("Сторонній"),
    )
    started = chat.service.start_from_listing(buyer, chat.listing(seller).id, "Привіт")
    other = chat.service.start_from_listing(
        stranger, chat.listing(seller, "Інше").id, "Секрет"
    )
    first_id = started.message.message_id

    chat.clock.advance(seconds=1)
    reply = chat.service.send_message(
        seller, started.conversation_id, "Так", reply_to_id=first_id
    )
    assert reply.reply_to.message_id == first_id
    assert reply.reply_to.body == "Привіт"
    assert reply.reply_to.is_own is False

    for bad in (other.message.message_id, uuid4()):
        with pytest.raises(InvalidMessageError):
            chat.service.send_message(
                seller, started.conversation_id, "Ні", reply_to_id=bad
            )

    items = chat.service.list_messages(buyer, started.conversation_id).items
    assert items[0].reply_to is None
    assert items[1].reply_to.is_own is True


def test_reply_preview_is_truncated(chat) -> None:
    """[TP-053] Довга цитата скорочується до 140 символів з «…»."""
    seller, buyer = chat.user("Продавець"), chat.user("Покупець")
    started = chat.service.start_from_listing(buyer, chat.listing(seller).id, "я" * 500)
    chat.clock.advance(seconds=1)
    reply = chat.service.send_message(
        seller, started.conversation_id, "ok", reply_to_id=started.message.message_id
    )
    assert len(reply.reply_to.body) == 140
    assert reply.reply_to.body.endswith("…")


def test_card_of_withdrawn_or_deleted_listing_shows_only_state(chat) -> None:
    """[TP-053]
    Після зняття чи видалення оголошення картка має лише available=False:
    без назви, ціни, фото й контакту; історія та розмова працюють далі.
    """
    seller, buyer = chat.user("Продавець"), chat.user("Покупець")
    listing = chat.listing(seller)
    gone = chat.listing(seller, "Видалене")
    started = chat.service.start_from_listing(buyer, listing.id, "Hi")
    chat.clock.advance(seconds=1)
    chat.service.send_message(buyer, started.conversation_id, "І це", gone.id)

    chat.withdraw(listing)
    chat.listings.delete(gone.id)
    chat.clock.advance(seconds=1)
    chat.service.send_message(seller, started.conversation_id, "Вже продав")

    first, second, third = chat.service.list_messages(
        seller, started.conversation_id
    ).items
    assert first.listing == ListingCard(listing_id=listing.id, available=False)
    assert second.listing == ListingCard(listing_id=gone.id, available=False)
    assert third.listing is None
    assert "contact" not in ListingCard.__dataclass_fields__


def test_markup_and_sql_like_text_is_kept_as_plain_text(chat) -> None:
    """[TP-053]
    XSS- і SQL-подібний текст зберігається без змін як звичайний текст.
    """
    seller, buyer = chat.user("Продавець"), chat.user("Покупець")
    body = "<script>alert(1)</script> '; DROP TABLE messages; --"

    started = chat.service.start_from_listing(buyer, chat.listing(seller).id, body)

    [message] = chat.service.list_messages(seller, started.conversation_id).items
    assert message.body == body
    assert message.is_own is False


def test_list_conversations_shows_public_profile_unread_and_pages(chat) -> None:
    """[TP-053]
    Список розмов: від найсвіжішої, співрозмовник лише з іменем і аватаркою
    (без email), останнє повідомлення, непрочитані й курсор наступної сторінки.
    """
    buyer = chat.user("Покупець")
    sellers = [chat.user(f"Продавець{i}") for i in range(3)]
    for seller in sellers:
        chat.service.start_from_listing(buyer, chat.listing(seller).id, "Привіт")
        chat.clock.advance(seconds=1)
    reply = chat.service.list_conversations(sellers[0]).items[0]
    chat.service.send_message(sellers[0], reply.conversation_id, "Так, продаю")

    first = chat.service.list_conversations(buyer, limit=2)
    second = chat.service.list_conversations(buyer, limit=2, cursor=first.next_cursor)

    names = [item.other.display_name for item in first.items + second.items]
    assert names == ["Продавець0", "Продавець2", "Продавець1"]
    assert second.next_cursor is None
    top = first.items[0]
    assert top.other == Participant(
        user_id=sellers[0].user_id,
        display_name="Продавець0",
        avatar_url="/uploads/Продавець0.webp",
    )
    assert "email" not in Participant.__dataclass_fields__
    assert top.last_message.body == "Так, продаю"
    assert top.last_message_at == chat.clock.now
    assert [item.unread_count for item in first.items + second.items] == [1, 0, 0]
    assert chat.service.unread_count(buyer) == 1
    assert chat.service.unread_count(sellers[1]) == 1
    with pytest.raises(InvalidChatCursorError):
        chat.service.list_conversations(buyer, cursor="не-курсор")


def test_list_messages_pages_back_and_polls_forward(chat) -> None:
    """[TP-053]
    Без курсора — останні `limit`; `before` гортає старіші до кінця; `after`
    повертає лише нові, а без нових залишає той самий курсор опитування.
    """
    seller, buyer = chat.user("Продавець"), chat.user("Покупець")
    started = chat.service.start_from_listing(buyer, chat.listing(seller).id, "m0")
    conversation_id = started.conversation_id
    for i in range(1, 5):
        chat.clock.advance(seconds=1)
        chat.service.send_message(seller if i % 2 else buyer, conversation_id, f"m{i}")

    latest = chat.service.list_messages(buyer, conversation_id, limit=2)
    older = chat.service.list_messages(
        buyer, conversation_id, before=latest.before_cursor, limit=2
    )
    oldest = chat.service.list_messages(
        buyer, conversation_id, before=older.before_cursor, limit=2
    )
    assert [m.body for m in latest.items] == ["m3", "m4"]
    assert [m.body for m in older.items] == ["m1", "m2"]
    assert [m.body for m in oldest.items] == ["m0"]
    assert latest.has_more and older.has_more and not oldest.has_more
    assert oldest.before_cursor is None

    idle = chat.service.list_messages(buyer, conversation_id, after=latest.after_cursor)
    assert idle.items == [] and idle.after_cursor == latest.after_cursor
    chat.clock.advance(seconds=1)
    chat.service.send_message(seller, conversation_id, "m5")
    fresh = chat.service.list_messages(buyer, conversation_id, after=idle.after_cursor)
    assert [m.body for m in fresh.items] == ["m5"]
    assert fresh.before_cursor is None and not fresh.has_more


def test_list_messages_rejects_both_or_broken_cursors(chat) -> None:
    """[TP-053]
    after і before разом або пошкоджений курсор — InvalidChatCursorError (422);
    limit поза межами відхиляється ще до запиту до сховища.
    """
    seller, buyer = chat.user("Продавець"), chat.user("Покупець")
    started = chat.service.start_from_listing(buyer, chat.listing(seller).id, "Hi")
    cursor = chat.service.list_messages(buyer, started.conversation_id).after_cursor

    with pytest.raises(InvalidChatCursorError):
        chat.service.list_messages(
            buyer, started.conversation_id, after=cursor, before=cursor
        )
    with pytest.raises(InvalidChatCursorError):
        chat.service.list_messages(buyer, started.conversation_id, before="%%%")
    for limit in (0, MESSAGES_PAGE_MAX + 1):
        with pytest.raises(ValueError):
            chat.service.list_messages(buyer, started.conversation_id, limit=limit)


def test_mark_read_clears_only_own_unread(chat) -> None:
    """[TP-053]
    Прочитання обнуляє непрочитані лише читача; співрозмовник свої не втрачає,
    а порожній результат для нових розмов не ламає лічильник.
    """
    seller, buyer = chat.user("Продавець"), chat.user("Покупець")
    started = chat.service.start_from_listing(buyer, chat.listing(seller).id, "Hi")
    chat.service.send_message(seller, started.conversation_id, "Вітаю")
    chat.service.send_message(buyer, started.conversation_id, "Коли можна забрати?")

    chat.service.mark_read(seller, started.conversation_id)
    chat.service.mark_read(seller, started.conversation_id)

    assert chat.service.unread_count(seller) == 0
    assert chat.service.unread_count(buyer) == 1
    chat.service.mark_read(buyer, started.conversation_id)
    assert chat.service.unread_count(buyer) == 0


# ---------------------------------------------------------------------------
# Ліміти (ADR-005, розділ 2.5)
# ---------------------------------------------------------------------------


def test_message_rate_limit_blocks_until_minute_passes() -> None:
    """[TP-054]
    Ліміт повідомлень за рухому хвилину: N-те проходить, N+1 — 429 з
    Retry-After 60 с; рівно через 60 с перше ще в вікні, трохи пізніше — ні.
    """
    chat = _Chat(ChatSettings(message_rate_per_minute=3))
    seller, buyer = chat.user("Продавець"), chat.user("Покупець")
    started = chat.service.start_from_listing(buyer, chat.listing(seller).id, "1")
    chat.service.send_message(buyer, started.conversation_id, "2")
    chat.service.send_message(buyer, started.conversation_id, "3")

    with pytest.raises(ChatRateLimitError) as error:
        chat.service.send_message(buyer, started.conversation_id, "4")
    assert error.value.retry_after_seconds == 60
    chat.service.send_message(seller, started.conversation_id, "Ліміт окремий")

    chat.clock.advance(seconds=60)
    with pytest.raises(ChatRateLimitError):
        chat.service.send_message(buyer, started.conversation_id, "4")
    chat.clock.advance(microseconds=1)
    chat.service.send_message(buyer, started.conversation_id, "4")
    assert len(chat.service.list_messages(buyer, started.conversation_id).items) == 5


def test_message_rate_limit_applies_to_start_from_listing() -> None:
    """[TP-054]
    Повторний старт з оголошення теж рахується як повідомлення.
    """
    chat = _Chat(ChatSettings(message_rate_per_minute=1))
    seller, buyer = chat.user("Продавець"), chat.user("Покупець")
    listing = chat.listing(seller)
    chat.service.start_from_listing(buyer, listing.id, "Hi")

    with pytest.raises(ChatRateLimitError):
        chat.service.start_from_listing(buyer, listing.id, "Hi again")


def test_conversation_start_limit_counts_only_new_conversations() -> None:
    """[TP-054]
    Ліміт нових розмов за рухомі 24 год: зайвий старт — 429 з Retry-After
    доби й без створеної розмови; існуюча розмова лімітом не обмежена;
    через 24 год і 1 мкс старт знову можливий.
    """
    chat = _Chat(ChatSettings(conversation_starts_per_day=2))
    buyer = chat.user("Покупець")
    sellers = [chat.user(f"Продавець{i}") for i in range(3)]
    listings = [chat.listing(seller) for seller in sellers]
    chat.service.start_from_listing(buyer, listings[0].id, "Hi")
    chat.service.start_from_listing(buyer, listings[1].id, "Hi")

    with pytest.raises(ChatRateLimitError) as error:
        chat.service.start_from_listing(buyer, listings[2].id, "Hi")
    assert error.value.retry_after_seconds == 24 * 60 * 60
    assert chat.service.list_conversations(sellers[2]).items == []
    again = chat.service.start_from_listing(buyer, listings[0].id, "Ще раз")
    assert again.created is False

    chat.clock.advance(days=1, microseconds=1)
    assert chat.service.start_from_listing(buyer, listings[2].id, "Hi").created
    assert len(chat.started_events()) == 3


def test_message_times_strictly_increase_so_polling_never_skips(chat) -> None:
    """[TP-053]
    Однакова мітка годинника чи годинник, що відстав, не ставлять нове
    повідомлення позаду вже виданого курсора `after`: час строго зростає.
    """
    seller, buyer = chat.user("Продавець"), chat.user("Покупець")
    started = chat.service.start_from_listing(buyer, chat.listing(seller).id, "m0")
    conversation_id = started.conversation_id
    cursor = chat.service.list_messages(seller, conversation_id).after_cursor
    seen = []
    for i, step in enumerate((0, -5, 0), start=1):
        chat.clock.advance(seconds=step)
        chat.service.send_message(buyer, conversation_id, f"m{i}")
        page = chat.service.list_messages(seller, conversation_id, after=cursor)
        seen += [m.body for m in page.items]
        cursor = page.after_cursor

    times = [
        m.created_at for m in chat.service.list_messages(seller, conversation_id).items
    ]
    assert seen == ["m1", "m2", "m3"]
    assert times == sorted(set(times))
    assert times[0] == T0


def test_send_to_conversation_removed_before_lock_is_not_found(chat) -> None:
    """[TP-053]
    Якщо розмову видалило очищення між перевіркою доступу й блокуванням,
    повідомлення не додається, а відповідь — ConversationNotFoundError (404).
    """
    seller, buyer = chat.user("Продавець"), chat.user("Покупець")
    started = chat.service.start_from_listing(buyer, chat.listing(seller).id, "Hi")
    chat.repo.lock_conversation = lambda conversation_id: None

    with pytest.raises(ConversationNotFoundError):
        chat.service.send_message(seller, started.conversation_id, "Відповідь")
    assert chat.repo.unread_count(started.conversation_id, buyer.user_id) == 0


def test_parallel_sends_cannot_bypass_rate_limit() -> None:
    """[TP-054]
    Паралельні запити одного користувача рахуються по черзі: за ліміту 1
    проходить рівно одне повідомлення, решта — ChatRateLimitError.
    """
    import threading
    import time

    chat = _Chat(ChatSettings(message_rate_per_minute=2))
    seller, buyer = chat.user("Продавець"), chat.user("Покупець")
    started = chat.service.start_from_listing(buyer, chat.listing(seller).id, "1")
    count = chat.repo.count_messages_since

    def slow_count(sender_id, since):
        # Розширюємо вікно між підрахунком і вставкою, щоб гонка була певною.
        result = count(sender_id, since)
        time.sleep(0.02)
        return result

    chat.repo.count_messages_since = slow_count
    barrier = threading.Barrier(8)
    outcomes: list[str] = []

    def send() -> None:
        barrier.wait()
        try:
            chat.service.send_message(buyer, started.conversation_id, "паралельно")
            outcomes.append("ok")
        except ChatRateLimitError:
            outcomes.append("429")

    threads = [threading.Thread(target=send) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert sorted(outcomes) == ["429"] * 7 + ["ok"]


def test_default_limits_match_adr() -> None:
    """[TP-054]
    За замовчуванням сервіс пропускає 30 повідомлень за хвилину, 31-ше — 429.
    """
    chat = _Chat()
    seller, buyer = chat.user("Продавець"), chat.user("Покупець")
    started = chat.service.start_from_listing(buyer, chat.listing(seller).id, "1")
    for i in range(2, DEFAULT_CHAT_MESSAGE_RATE_PER_MINUTE + 1):
        chat.service.send_message(buyer, started.conversation_id, str(i))

    with pytest.raises(ChatRateLimitError):
        chat.service.send_message(buyer, started.conversation_id, "зайве")


def test_conversation_service_factory_and_startup_validation(monkeypatch) -> None:
    """[TP-054]
    Фабрика без DATABASE_URL дає сервіс на in-memory сховищі; некоректне
    CHAT_* зупиняє старт застосунку ще до прийому запитів.
    """
    from fastapi.testclient import TestClient

    from src.api import deps
    from src.api.main import app

    service = deps.get_conversation_service(None)
    assert isinstance(service, ConversationService)
    assert deps.get_conversation_repository(None) is (
        deps.get_conversation_repository(None)
    )

    monkeypatch.setenv("CHAT_MESSAGE_RATE_PER_MINUTE", "0")
    with pytest.raises(RuntimeError, match="CHAT_MESSAGE_RATE_PER_MINUTE"):
        with TestClient(app):
            pass
