"""Moderation Service: адміністративне зняття оголошення (FR-011)."""

from dataclasses import replace
from datetime import timedelta
from uuid import UUID

from src.domain.exceptions import (
    ListingNotFoundError,
    ListingUnauthorizedError,
    ModerationForbiddenError,
)
from src.domain.favorites import Favorite
from src.domain.listings import Listing, ListingStatus, utc_now
from src.domain.moderation import (
    ModerationAction,
    ModerationActionType,
    normalize_moderation_reason,
)
from src.domain.users import CurrentUser, UserRole
from src.repositories.favorites import FavoriteRepository
from src.repositories.listings import ListingRepository, get_listing_mutation_lock
from src.repositories.moderation import ModerationActionRepository


class ModerationService:
    """Бізнес-правила модерації незалежно від HTTP-фреймворку."""

    def __init__(
        self,
        listings: ListingRepository,
        favorites: FavoriteRepository,
        actions: ModerationActionRepository,
    ) -> None:
        self._listings = listings
        self._favorites = favorites
        self._actions = actions
        # Серіалізує перевірку статусу і зміну стану: два одночасні запити
        # не можуть обидва побачити ACTIVE і створити два записи аудиту.
        # З PostgreSQL це замінюється транзакцією з SELECT ... FOR UPDATE.
        self._lock = get_listing_mutation_lock(listings)

    def withdraw_listing(
        self, moderator: CurrentUser | None, listing_id: UUID, reason: str
    ) -> ModerationAction:
        """Знімає активне оголошення з причиною і фіксує дію в журналі.

        Зміна статусу, очищення обраного та запис аудиту виконуються як одна
        операція: якщо будь-який крок падає, попередній стан відновлюється.
        Оголошення фізично не видаляється (FR-011).
        """
        if moderator is None:
            raise ListingUnauthorizedError("Потрібна ідентифікація користувача")
        if moderator.role != UserRole.ADMIN:
            raise ModerationForbiddenError("Дія дозволена лише адміністраторам")
        action = ModerationAction(
            moderator_id=moderator.user_id,
            listing_id=listing_id,
            action_type=ModerationActionType.WITHDRAW_LISTING,
            reason=normalize_moderation_reason(reason),
        )

        with self._lock:
            return self._withdraw_locked(action, listing_id)

    def _withdraw_locked(
        self, action: ModerationAction, listing_id: UUID
    ) -> ModerationAction:
        """Перевірка статусу і всі зміни стану під одним замком."""
        original = self._listings.get(listing_id)
        if original is None or not original.is_public():
            raise ListingNotFoundError("Оголошення не знайдено або вже зняте")

        withdrawn = replace(
            original,
            status=ListingStatus.WITHDRAWN,
            updated_at=max(utc_now(), original.updated_at + timedelta(microseconds=1)),
        )
        saved_favorites = self._favorites.list_by_listing(listing_id)
        try:
            self._listings.save(withdrawn)
            self._favorites.delete_by_listing(listing_id)
            self._actions.add(action)
        except Exception:
            self._rollback(original, saved_favorites)
            raise
        return action

    def _rollback(self, original: Listing, saved_favorites: list[Favorite]) -> None:
        """Повертає оголошення і записи обраного до стану перед операцією."""
        self._listings.save(original)
        for favorite in saved_favorites:
            if self._favorites.get(favorite.user_id, favorite.listing_id) is None:
                self._favorites.add(favorite)
