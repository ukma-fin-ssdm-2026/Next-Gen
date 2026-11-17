"""Контракт сховища розмов і in-memory адаптер (ADR-005).

Однаковий контракт реалізують `InMemoryConversationRepository` (розробка без
БД і модульні тести) та `PostgresConversationRepository`. Усі вибірки
повідомлень впорядковані лише за `(created_at, message_id)`.
"""

from contextlib import AbstractContextManager
from datetime import datetime
from threading import RLock
from typing import Protocol
from uuid import UUID

from src.domain.conversations import Conversation, Message, MessageKey, as_utc


class ConversationRepository(Protocol):
    """Контракт сховища розмов для `ConversationService`."""

    def get(self, conversation_id: UUID) -> Conversation | None:
        """Розмова за ідентифікатором або None."""

    def get_by_pair(self, user_low_id: UUID, user_high_id: UUID) -> Conversation | None:
        """Розмова нормалізованої пари учасників або None."""

    def sender_write_lock(self, sender_id: UUID) -> AbstractContextManager[None]:
        """Серіалізує записи одного відправника (ліміти без гонок).

        Підрахунок для лімітів і вставка повідомлення виконуються під цим
        блокуванням, тож паралельні запити одного користувача не проходять
        ліміт обидва. У PostgreSQL блокування тримається до кінця транзакції.
        """

    def lock_conversation(self, conversation_id: UUID) -> Conversation | None:
        """Блокує розмову для запису й повертає її актуальний стан.

        Записи в одну розмову йдуть по черзі до кінця транзакції, тому новий
        `created_at` можна взяти строго більшим за `last_message_at`.
        """

    def get_or_create(self, conversation: Conversation) -> tuple[Conversation, bool]:
        """Повертає розмову пари, створюючи передану, якщо її ще немає.

        Друге значення — True, якщо розмову створено саме цим викликом.
        Паралельні виклики для однієї пари не створюють дубліката.
        """

    def add_message(self, message: Message) -> Message:
        """Додає повідомлення й пересуває `last_message_at` розмови вперед."""

    def last_message(self, conversation_id: UUID) -> Message | None:
        """Найновіше повідомлення розмови за `(created_at, message_id)`."""

    def get_message(self, conversation_id: UUID, message_id: UUID) -> Message | None:
        """Повідомлення за id, лише якщо воно належить цій розмові."""

    def list_for_user(
        self, user_id: UUID, limit: int, before: MessageKey | None = None
    ) -> list[Conversation]:
        """Розмови учасника від найсвіжішої активності.

        Порядок — `(last_message_at, conversation_id)` за спаданням; `before`
        повертає лише розмови, що йдуть після вказаної позиції.
        """

    def list_messages(
        self,
        conversation_id: UUID,
        limit: int,
        after: MessageKey | None = None,
        before: MessageKey | None = None,
    ) -> list[Message]:
        """Повідомлення за зростанням `(created_at, message_id)`.

        `after` — перші `limit` новіших за позицію; `before` — останні `limit`
        старіших за позицію; без курсора — останні `limit` повідомлень.
        """

    def mark_read(self, conversation_id: UUID, user_id: UUID, key: MessageKey) -> bool:
        """Пересуває позначку прочитаного учасника лише вперед."""

    def unread_count(self, conversation_id: UUID, user_id: UUID) -> int:
        """Повідомлення співрозмовника, новіші за позначку прочитаного."""

    def total_unread(self, user_id: UUID) -> int:
        """Сума непрочитаних у всіх розмовах користувача."""

    def count_messages_since(self, sender_id: UUID, since: datetime) -> int:
        """Скільки повідомлень користувач надіслав починаючи з `since`."""

    def count_conversations_started_since(self, user_id: UUID, since: datetime) -> int:
        """Скільки нових розмов користувач почав починаючи з `since`.

        Розмову «почав» відправник першого повідомлення: воно створюється
        атомарно з розмовою й має той самий `created_at`.
        """

    def delete_messages_older_than(self, cutoff: datetime, batch_size: int) -> int:
        """Видаляє не більше `batch_size` повідомлень, старіших за `cutoff`."""

    def delete_empty_conversations(self) -> int:
        """Видаляє розмови без жодного повідомлення. Повертає кількість."""


class InMemoryConversationRepository:
    """Розмови в пам'яті процесу (без DATABASE_URL і для модульних тестів)."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._conversations: dict[UUID, Conversation] = {}
        self._by_pair: dict[tuple[UUID, UUID], UUID] = {}
        self._messages: dict[UUID, list[Message]] = {}

    def get(self, conversation_id: UUID) -> Conversation | None:
        return self._conversations.get(conversation_id)

    def sender_write_lock(self, sender_id: UUID) -> AbstractContextManager[None]:
        # Одне блокування на все сховище: записи в пам'яті просто йдуть по черзі.
        return self._lock

    def lock_conversation(self, conversation_id: UUID) -> Conversation | None:
        return self.get(conversation_id)

    def get_by_pair(self, user_low_id: UUID, user_high_id: UUID) -> Conversation | None:
        conversation_id = self._by_pair.get((user_low_id, user_high_id))
        return self._conversations.get(conversation_id) if conversation_id else None

    def get_or_create(self, conversation: Conversation) -> tuple[Conversation, bool]:
        with self._lock:
            existing = self.get_by_pair(
                conversation.user_low_id, conversation.user_high_id
            )
            if existing is not None:
                return existing, False
            self._conversations[conversation.conversation_id] = conversation
            self._by_pair[conversation.participants] = conversation.conversation_id
            self._messages[conversation.conversation_id] = []
            return conversation, True

    def add_message(self, message: Message) -> Message:
        with self._lock:
            conversation = self._conversations.get(message.conversation_id)
            if conversation is None:
                raise KeyError(f"Розмову {message.conversation_id} не знайдено")
            items = self._messages[message.conversation_id]
            items.append(message)
            items.sort(key=lambda item: item.key)
            if as_utc(message.created_at) > as_utc(conversation.last_message_at):
                conversation.last_message_at = message.created_at
            return message

    def last_message(self, conversation_id: UUID) -> Message | None:
        items = self._messages.get(conversation_id) or []
        return items[-1] if items else None

    def get_message(self, conversation_id: UUID, message_id: UUID) -> Message | None:
        for item in self._messages.get(conversation_id) or []:
            if item.message_id == message_id:
                return item
        return None

    def list_for_user(
        self, user_id: UUID, limit: int, before: MessageKey | None = None
    ) -> list[Conversation]:
        items = [c for c in self._conversations.values() if c.has_participant(user_id)]
        items.sort(key=_activity_key, reverse=True)
        if before is not None:
            items = [c for c in items if _activity_key(c) < before]
        return items[:limit]

    def list_messages(
        self,
        conversation_id: UUID,
        limit: int,
        after: MessageKey | None = None,
        before: MessageKey | None = None,
    ) -> list[Message]:
        if after is not None and before is not None:
            raise ValueError("after і before взаємовиключні")
        items = list(self._messages.get(conversation_id) or [])
        if after is not None:
            return [m for m in items if m.key > after][:limit]
        if before is not None:
            items = [m for m in items if m.key < before]
        return items[-limit:] if limit else []

    def mark_read(self, conversation_id: UUID, user_id: UUID, key: MessageKey) -> bool:
        with self._lock:
            conversation = self._conversations.get(conversation_id)
            if conversation is None:
                return False
            return conversation.set_read_marker(user_id, key)

    def unread_count(self, conversation_id: UUID, user_id: UUID) -> int:
        conversation = self._conversations.get(conversation_id)
        if conversation is None or not conversation.has_participant(user_id):
            return 0
        marker = conversation.read_marker(user_id)
        return sum(
            1
            for message in self._messages.get(conversation_id) or []
            if message.sender_id != user_id and (marker is None or message.key > marker)
        )

    def total_unread(self, user_id: UUID) -> int:
        return sum(
            self.unread_count(c.conversation_id, user_id)
            for c in self._conversations.values()
            if c.has_participant(user_id)
        )

    def count_messages_since(self, sender_id: UUID, since: datetime) -> int:
        since = as_utc(since)
        return sum(
            1
            for items in self._messages.values()
            for message in items
            if message.sender_id == sender_id and as_utc(message.created_at) >= since
        )

    def count_conversations_started_since(self, user_id: UUID, since: datetime) -> int:
        since = as_utc(since)
        started = 0
        for conversation in self._conversations.values():
            created_at = as_utc(conversation.created_at)
            if created_at < since:
                continue
            if any(
                m.sender_id == user_id and as_utc(m.created_at) == created_at
                for m in self._messages.get(conversation.conversation_id) or []
            ):
                started += 1
        return started

    def delete_messages_older_than(self, cutoff: datetime, batch_size: int) -> int:
        cutoff = as_utc(cutoff)
        with self._lock:
            deleted = 0
            for conversation_id, items in self._messages.items():
                keep = []
                for message in items:
                    if deleted < batch_size and as_utc(message.created_at) < cutoff:
                        deleted += 1
                    else:
                        keep.append(message)
                self._messages[conversation_id] = keep
            return deleted

    def delete_empty_conversations(self) -> int:
        with self._lock:
            empty = [cid for cid, items in self._messages.items() if not items]
            for conversation_id in empty:
                conversation = self._conversations.pop(conversation_id)
                self._by_pair.pop(conversation.participants, None)
                del self._messages[conversation_id]
            return len(empty)


def _activity_key(conversation: Conversation) -> MessageKey:
    return as_utc(conversation.last_message_at), conversation.conversation_id
