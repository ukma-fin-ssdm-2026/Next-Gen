"""Модульні тести ядра чату без HTTP (ADR-005).

- домен: нормалізація пари й тексту, курсор, позначка прочитаного, налаштування;
- контракт сховища розмов (`ConversationRepositoryContract`), який перевіряється
  на in-memory адаптері тут і на PostgreSQL-адаптері в
  `tests/test_postgres_repositories.py`.
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
    decode_cursor,
    encode_cursor,
    normalize_message_body,
    normalize_pair,
)
from src.domain.exceptions import (
    ConversationForbiddenError,
    InvalidChatCursorError,
    InvalidMessageError,
)
from src.repositories.conversations import InMemoryConversationRepository

T0 = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)

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
        ("Сім'я 👨‍👩‍👧", "Сім'я 👨‍👩‍👧"),
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
        "рядок\nще рядок",
        "таб\tтут",
        "нуль\x00байт",
        "del\x7f",
        "підміна ‮тексту",
        None,
    ],
    ids=["empty", "spaces", "too-long", "newline", "tab", "nul", "del", "bidi", "none"],
)
def test_message_body_rejects_invalid_text(raw) -> None:
    """[TP-050]
    Порожній, задовгий текст, керівні символи (Cc) і символи підміни напрямку
    тексту відхиляються.
    """
    with pytest.raises(InvalidMessageError):
        normalize_message_body(raw)


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
        ids = [UUID(int=i) for i in (3, 1, 2)]
        for message_id in ids:
            self._send(repo, conversation, b, same, message_id=message_id)
        items = repo.list_messages(conversation.conversation_id, limit=10)
        assert [m.message_id for m in items[1:]] == sorted(ids)
        middle = items[2].key
        after = repo.list_messages(conversation.conversation_id, limit=10, after=middle)
        before = repo.list_messages(
            conversation.conversation_id, limit=10, before=middle
        )
        assert [m.message_id for m in after] == [UUID(int=3)]
        assert [m.message_id for m in before] == [items[0].message_id, UUID(int=1)]

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
        first = self._send(repo, conversation, a, same, message_id=UUID(int=10))
        self._send(repo, conversation, a, same, message_id=UUID(int=20))
        assert repo.unread_count(cid, a) == 0
        assert repo.unread_count(cid, b) == 3
        assert repo.mark_read(cid, b, first.key)
        assert repo.unread_count(cid, b) == 1
        assert not repo.mark_read(cid, b, (T0, UUID(int=0)))
        assert repo.unread_count(cid, b) == 1
        assert repo.unread_count(cid, new_user()) == 0

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


class TestInMemoryConversationRepository(ConversationRepositoryContract):
    """[TP-051] Контракт сховища розмов на in-memory адаптері."""

    @pytest.fixture
    def repo(self):
        return InMemoryConversationRepository()

    @pytest.fixture
    def new_user(self):
        return uuid4

    def test_in_memory_rejects_both_cursors_and_unknown_conversation(self, repo):
        """[TP-051]
        after і before разом — помилка; повідомлення до неіснуючої розмови не
        додається.
        """
        with pytest.raises(ValueError):
            repo.list_messages(
                uuid4(), limit=1, after=(T0, uuid4()), before=(T0, uuid4())
            )
        with pytest.raises(KeyError):
            repo.add_message(
                Message(conversation_id=uuid4(), sender_id=LOW_ID, body="x")
            )
        assert repo.list_messages(uuid4(), limit=0) == []
        assert not repo.mark_read(uuid4(), LOW_ID, (T0, uuid4()))
