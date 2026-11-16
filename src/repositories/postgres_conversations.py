"""PostgreSQL-адаптер сховища розмов (ADR-002, ADR-005).

Реалізує контракт `ConversationRepository`. Розмова створюється через
`INSERT ... ON CONFLICT DO NOTHING` за унікальною парою, тому паралельні
запити не створюють дубліката й не обривають транзакцію помилкою. Курсори
порівнюються як пари рядків `(created_at, message_id)`, що працює однаково в
PostgreSQL і SQLite (модульні тести).

Записи серіалізуються блокуваннями рядків `FOR NO KEY UPDATE` до кінця
транзакції: рядок відправника в `users` (ліміти) і рядок розмови (порядок
повідомлень). Цей режим не конфліктує з `FOR KEY SHARE`, який беруть
перевірки зовнішніх ключів, тому вставки з посиланням на ці рядки не чекають.
Порядок завжди «користувач, потім розмова», що виключає взаємоблокування.
SQLite (модульні тести) `FOR UPDATE` не підтримує й ігнорує.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, delete, exists, func, literal, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from src.db.converters import (
    conversation_row_to_domain,
    message_domain_to_row,
    message_row_to_domain,
)
from src.db.models import ConversationRow, MessageRow, UserRow
from src.domain.conversations import Conversation, Message, MessageKey

_MESSAGE_ORDER = tuple_(MessageRow.created_at, MessageRow.message_id)


def _message_key(key: MessageKey):
    """Позиція як типізована пара параметрів (у SQLite UUID і час — рядки)."""
    created_at, message_id = key
    return tuple_(
        literal(created_at, MessageRow.created_at.type),
        literal(message_id, MessageRow.message_id.type),
    )


def _activity_key(key: MessageKey):
    last_message_at, conversation_id = key
    return tuple_(
        literal(last_message_at, ConversationRow.last_message_at.type),
        literal(conversation_id, ConversationRow.conversation_id.type),
    )


_ACTIVITY_ORDER = tuple_(
    ConversationRow.last_message_at, ConversationRow.conversation_id
)


class PostgresConversationRepository:
    """Реалізує ConversationRepository у PostgreSQL."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # -- розмови --------------------------------------------------------------

    def get(self, conversation_id: UUID) -> Conversation | None:
        row = self._session.get(ConversationRow, conversation_id)
        return conversation_row_to_domain(row) if row else None

    @contextmanager
    def sender_write_lock(self, sender_id: UUID) -> Iterator[None]:
        # Блокування рядка знімає лише commit/rollback сесії запиту, а не вихід
        # із блоку: так лічильник лімітів і вставка видні наступному запиту разом.
        self._session.execute(
            select(UserRow.user_id)
            .where(UserRow.user_id == sender_id)
            .with_for_update(key_share=True)
        )
        yield

    def lock_conversation(self, conversation_id: UUID) -> Conversation | None:
        stmt = (
            select(ConversationRow)
            .where(ConversationRow.conversation_id == conversation_id)
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
        row = self._session.scalars(stmt).first()
        return conversation_row_to_domain(row) if row else None

    def get_by_pair(self, user_low_id: UUID, user_high_id: UUID) -> Conversation | None:
        row = self._row_by_pair(user_low_id, user_high_id)
        return conversation_row_to_domain(row) if row else None

    def get_or_create(self, conversation: Conversation) -> tuple[Conversation, bool]:
        insert = (
            postgresql_insert
            if self._session.get_bind().dialect.name == "postgresql"
            else sqlite_insert
        )
        table = ConversationRow.__table__
        statement = (
            insert(table)
            .values(
                conversation_id=conversation.conversation_id,
                user_low_id=conversation.user_low_id,
                user_high_id=conversation.user_high_id,
                created_at=conversation.created_at,
                last_message_at=conversation.last_message_at,
            )
            .on_conflict_do_nothing(index_elements=["user_low_id", "user_high_id"])
            .returning(table.c.conversation_id)
        )
        # RETURNING повертає рядок лише тоді, коли вставка справді відбулась.
        created = self._session.execute(statement).first() is not None
        row = self._row_by_pair(conversation.user_low_id, conversation.user_high_id)
        return conversation_row_to_domain(row), created

    def list_for_user(
        self, user_id: UUID, limit: int, before: MessageKey | None = None
    ) -> list[Conversation]:
        stmt = select(ConversationRow).where(
            or_(
                ConversationRow.user_low_id == user_id,
                ConversationRow.user_high_id == user_id,
            )
        )
        if before is not None:
            stmt = stmt.where(_ACTIVITY_ORDER < _activity_key(before))
        stmt = stmt.order_by(
            ConversationRow.last_message_at.desc(),
            ConversationRow.conversation_id.desc(),
        ).limit(limit)
        return [conversation_row_to_domain(r) for r in self._session.scalars(stmt)]

    def mark_read(self, conversation_id: UUID, user_id: UUID, key: MessageKey) -> bool:
        row = self._session.get(ConversationRow, conversation_id, with_for_update=True)
        if row is None:
            return False
        conversation = conversation_row_to_domain(row)
        if not conversation.set_read_marker(user_id, key):
            return False
        at, message_id = key
        if user_id == row.user_low_id:
            row.low_last_read_at, row.low_last_read_message_id = at, message_id
        else:
            row.high_last_read_at, row.high_last_read_message_id = at, message_id
        self._session.flush()
        return True

    # -- повідомлення ---------------------------------------------------------

    def add_message(self, message: Message) -> Message:
        row = message_domain_to_row(message)
        self._session.add(row)
        self._session.flush()
        self._session.execute(
            update(ConversationRow)
            .where(
                ConversationRow.conversation_id == message.conversation_id,
                ConversationRow.last_message_at < message.created_at,
            )
            .values(last_message_at=message.created_at)
            .execution_options(synchronize_session="fetch")
        )
        return message_row_to_domain(row)

    def last_message(self, conversation_id: UUID) -> Message | None:
        stmt = (
            select(MessageRow)
            .where(MessageRow.conversation_id == conversation_id)
            .order_by(MessageRow.created_at.desc(), MessageRow.message_id.desc())
            .limit(1)
        )
        row = self._session.scalars(stmt).first()
        return message_row_to_domain(row) if row else None

    def list_messages(
        self,
        conversation_id: UUID,
        limit: int,
        after: MessageKey | None = None,
        before: MessageKey | None = None,
    ) -> list[Message]:
        if after is not None and before is not None:
            raise ValueError("after і before взаємовиключні")
        stmt = select(MessageRow).where(MessageRow.conversation_id == conversation_id)
        if after is not None:
            stmt = stmt.where(_MESSAGE_ORDER > _message_key(after)).order_by(
                MessageRow.created_at, MessageRow.message_id
            )
            rows = list(self._session.scalars(stmt.limit(limit)))
        else:
            if before is not None:
                stmt = stmt.where(_MESSAGE_ORDER < _message_key(before))
            stmt = stmt.order_by(
                MessageRow.created_at.desc(), MessageRow.message_id.desc()
            )
            rows = list(self._session.scalars(stmt.limit(limit)))[::-1]
        return [message_row_to_domain(r) for r in rows]

    # -- непрочитані ----------------------------------------------------------

    def unread_count(self, conversation_id: UUID, user_id: UUID) -> int:
        row = self._session.get(ConversationRow, conversation_id)
        if row is None or user_id not in (row.user_low_id, row.user_high_id):
            return 0
        marker = conversation_row_to_domain(row).read_marker(user_id)
        stmt = select(func.count()).where(
            MessageRow.conversation_id == conversation_id,
            MessageRow.sender_id != user_id,
        )
        if marker is not None:
            stmt = stmt.where(_MESSAGE_ORDER > _message_key(marker))
        return self._session.scalar(stmt) or 0

    def total_unread(self, user_id: UUID) -> int:
        return self._unread_on_side(user_id, low=True) + self._unread_on_side(
            user_id, low=False
        )

    def _unread_on_side(self, user_id: UUID, *, low: bool) -> int:
        """Непрочитані в розмовах, де користувач стоїть на боці low або high."""
        if low:
            side, read_at, read_id = (
                ConversationRow.user_low_id,
                ConversationRow.low_last_read_at,
                ConversationRow.low_last_read_message_id,
            )
        else:
            side, read_at, read_id = (
                ConversationRow.user_high_id,
                ConversationRow.high_last_read_at,
                ConversationRow.high_last_read_message_id,
            )
        stmt = (
            select(func.count())
            .select_from(MessageRow)
            .join(
                ConversationRow,
                MessageRow.conversation_id == ConversationRow.conversation_id,
            )
            .where(
                side == user_id,
                MessageRow.sender_id != user_id,
                or_(
                    read_at.is_(None),
                    read_id.is_(None),
                    _MESSAGE_ORDER > tuple_(read_at, read_id),
                ),
            )
        )
        return self._session.scalar(stmt) or 0

    # -- ліміти ---------------------------------------------------------------

    def count_messages_since(self, sender_id: UUID, since: datetime) -> int:
        stmt = select(func.count()).where(
            MessageRow.sender_id == sender_id, MessageRow.created_at >= since
        )
        return self._session.scalar(stmt) or 0

    def count_conversations_started_since(self, user_id: UUID, since: datetime) -> int:
        stmt = (
            select(func.count(func.distinct(ConversationRow.conversation_id)))
            .select_from(MessageRow)
            .join(
                ConversationRow,
                MessageRow.conversation_id == ConversationRow.conversation_id,
            )
            .where(
                MessageRow.sender_id == user_id,
                ConversationRow.created_at >= since,
                MessageRow.created_at == ConversationRow.created_at,
            )
        )
        return self._session.scalar(stmt) or 0

    # -- зберігання -----------------------------------------------------------

    def delete_messages_older_than(self, cutoff: datetime, batch_size: int) -> int:
        batch = (
            select(MessageRow.message_id)
            .where(MessageRow.created_at < cutoff)
            .order_by(MessageRow.created_at, MessageRow.message_id)
            .limit(batch_size)
        )
        result = self._session.execute(
            delete(MessageRow)
            .where(MessageRow.message_id.in_(batch.scalar_subquery()))
            .execution_options(synchronize_session="fetch")
        )
        return result.rowcount or 0

    def delete_empty_conversations(self) -> int:
        has_messages = exists().where(
            and_(MessageRow.conversation_id == ConversationRow.conversation_id)
        )
        result = self._session.execute(
            delete(ConversationRow)
            .where(~has_messages)
            .execution_options(synchronize_session="fetch")
        )
        return result.rowcount or 0

    def _row_by_pair(
        self, user_low_id: UUID, user_high_id: UUID
    ) -> ConversationRow | None:
        stmt = select(ConversationRow).where(
            ConversationRow.user_low_id == user_low_id,
            ConversationRow.user_high_id == user_high_id,
        )
        return self._session.scalars(stmt).first()
