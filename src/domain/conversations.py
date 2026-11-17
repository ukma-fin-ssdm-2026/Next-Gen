"""Розмови й повідомлення між двома користувачами (ADR-005, FR-021, FR-022).

Модуль не залежить від FastAPI і SQLAlchemy: тут лише сутності, нормалізація
пари учасників і тексту, непрозорий курсор та налаштування лімітів.
Порядок повідомлень визначає лише пара `(created_at, message_id)`.
"""

from __future__ import annotations

import base64
import binascii
import re
import os
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.domain.exceptions import (
    ConversationForbiddenError,
    InvalidChatCursorError,
    InvalidMessageError,
)
from src.domain.listings import utc_now

MESSAGE_BODY_MIN_LENGTH = 1
MESSAGE_BODY_MAX_LENGTH = 1000

DEFAULT_CHAT_MESSAGE_RATE_PER_MINUTE = 30
DEFAULT_CHAT_CONVERSATION_STARTS_PER_DAY = 10
DEFAULT_CHAT_RETENTION_DAYS = 365

# Невидимі символи керування напрямком тексту (Unicode Cf): ALM, LRM, RLM,
# LRE–RLO і LRI–PDI. Дозволяють візуально підмінити текст повідомлення, тому
# відхиляються разом із Cc. Задані кодами, щоб їх не було у вихідному коді.
BIDI_CONTROL_CHARACTERS = frozenset(
    chr(code)
    for code in (0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A))
)

# Курсор — base64url від "ISO-час|UUID"; довший рядок свідомо не розбираємо.
CURSOR_MAX_LENGTH = 128

MessageKey = tuple[datetime, UUID]
"""Стабільна позиція повідомлення: `(created_at, message_id)`."""


def normalize_pair(first: UUID, second: UUID) -> tuple[UUID, UUID]:
    """Повертає пару учасників у порядку `(менший, більший)`.

    Пара `A,B` і `B,A` дає однаковий результат, тому на двох користувачів
    існує рівно одна розмова. Розмова із самим собою заборонена.
    """
    if first == second:
        raise ConversationForbiddenError("Не можна почати розмову із самим собою")
    return (first, second) if first < second else (second, first)


def normalize_message_body(body: str) -> str:
    """Обрізає пробіли й перевіряє текст: 1–1000 символів, без керівних.

    Дозволено лише перенос рядка: `\\r\\n` і `\\r` зводяться до `\\n`, а три й
    більше переносів поспіль скорочуються до двох (порожній рядок).
    """
    if not isinstance(body, str):
        raise InvalidMessageError("Текст повідомлення має бути рядком")
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    if any(
        (unicodedata.category(ch) == "Cc" and ch != "\n")
        or ch in BIDI_CONTROL_CHARACTERS
        for ch in body
    ):
        raise InvalidMessageError("Повідомлення не може містити керівні символи")
    cleaned = re.sub(r"\n{3,}", "\n\n", body.strip())
    if not MESSAGE_BODY_MIN_LENGTH <= len(cleaned) <= MESSAGE_BODY_MAX_LENGTH:
        raise InvalidMessageError(
            f"Повідомлення має містити від {MESSAGE_BODY_MIN_LENGTH} "
            f"до {MESSAGE_BODY_MAX_LENGTH} символів"
        )
    return cleaned


def as_utc(value: datetime) -> datetime:
    """Приводить час до UTC; час без поясу вважається UTC (SQLite його губить)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def encode_cursor(key: MessageKey) -> str:
    """Кодує позицію `(created_at, id)` у непрозорий рядок для клієнта."""
    created_at, item_id = key
    raw = f"{as_utc(created_at).isoformat()}|{item_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(token: str) -> MessageKey:
    """Розбирає курсор; будь-яке пошкодження дає InvalidChatCursorError."""
    if not isinstance(token, str) or not 0 < len(token) <= CURSOR_MAX_LENGTH:
        raise InvalidChatCursorError("Невалідний курсор")
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        created_part, id_part = raw.split("|")
        created_at = datetime.fromisoformat(created_part)
        item_id = UUID(id_part)
    except (ValueError, UnicodeError, binascii.Error) as exc:
        raise InvalidChatCursorError("Невалідний курсор") from exc
    if created_at.tzinfo is None:
        raise InvalidChatCursorError("Невалідний курсор")
    return as_utc(created_at), item_id


def _read_positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(f"{name} має бути цілим числом, отримано {raw!r}") from None
    if value <= 0:
        raise RuntimeError(f"{name} має бути більшим за 0, отримано {value}")
    return value


@dataclass(frozen=True)
class ChatSettings:
    """Ліміти й строк зберігання чату (ADR-005, розділ 2.5)."""

    message_rate_per_minute: int = DEFAULT_CHAT_MESSAGE_RATE_PER_MINUTE
    conversation_starts_per_day: int = DEFAULT_CHAT_CONVERSATION_STARTS_PER_DAY
    retention_days: int = DEFAULT_CHAT_RETENTION_DAYS

    @classmethod
    def from_env(cls) -> ChatSettings:
        """Читає `CHAT_*` зі змінних середовища; некоректне значення — помилка."""
        return cls(
            message_rate_per_minute=_read_positive_int(
                "CHAT_MESSAGE_RATE_PER_MINUTE", DEFAULT_CHAT_MESSAGE_RATE_PER_MINUTE
            ),
            conversation_starts_per_day=_read_positive_int(
                "CHAT_CONVERSATION_STARTS_PER_DAY",
                DEFAULT_CHAT_CONVERSATION_STARTS_PER_DAY,
            ),
            retention_days=_read_positive_int(
                "CHAT_RETENTION_DAYS", DEFAULT_CHAT_RETENTION_DAYS
            ),
        )


@dataclass
class Conversation:
    """Розмова між двома користувачами; пара зберігається впорядкованою.

    Для кожного учасника окремо зберігається позначка прочитаного: час і
    ідентифікатор останнього прочитаного повідомлення (стабільна пара).
    """

    user_low_id: UUID
    user_high_id: UUID
    conversation_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    last_message_at: datetime | None = None
    low_last_read_at: datetime | None = None
    low_last_read_message_id: UUID | None = None
    high_last_read_at: datetime | None = None
    high_last_read_message_id: UUID | None = None

    def __post_init__(self) -> None:
        if not self.user_low_id < self.user_high_id:
            raise ValueError("Пара учасників має бути впорядкована: low < high")
        if self.last_message_at is None:
            self.last_message_at = self.created_at

    @property
    def participants(self) -> tuple[UUID, UUID]:
        return self.user_low_id, self.user_high_id

    def has_participant(self, user_id: UUID) -> bool:
        return user_id in self.participants

    def other_participant(self, user_id: UUID) -> UUID:
        """Співрозмовник указаного учасника."""
        if user_id == self.user_low_id:
            return self.user_high_id
        if user_id == self.user_high_id:
            return self.user_low_id
        raise ValueError("Користувач не є учасником розмови")

    def read_marker(self, user_id: UUID) -> MessageKey | None:
        """Позиція останнього прочитаного учасником повідомлення або None."""
        if user_id == self.user_low_id:
            at, message_id = self.low_last_read_at, self.low_last_read_message_id
        elif user_id == self.user_high_id:
            at, message_id = self.high_last_read_at, self.high_last_read_message_id
        else:
            raise ValueError("Користувач не є учасником розмови")
        if at is None or message_id is None:
            return None
        return as_utc(at), message_id

    def set_read_marker(self, user_id: UUID, key: MessageKey) -> bool:
        """Пересуває позначку лише вперед. True, якщо позначка змінилась."""
        current = self.read_marker(user_id)
        if current is not None and key <= current:
            return False
        at, message_id = key
        if user_id == self.user_low_id:
            self.low_last_read_at, self.low_last_read_message_id = at, message_id
        else:
            self.high_last_read_at, self.high_last_read_message_id = at, message_id
        return True


@dataclass(frozen=True)
class Message:
    """Незмінне повідомлення розмови; текст уже нормалізований."""

    conversation_id: UUID
    sender_id: UUID
    body: str
    listing_id: UUID | None = None
    message_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    reply_to_id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "body", normalize_message_body(self.body))

    @property
    def key(self) -> MessageKey:
        return as_utc(self.created_at), self.message_id
