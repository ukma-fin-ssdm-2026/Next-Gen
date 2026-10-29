"""Category Suggestion Service: подання та модерація пропозицій (FR-015 / US-010)."""

from dataclasses import replace
from datetime import timedelta
from threading import RLock
from uuid import UUID

from src.domain.category_suggestions import (
    MAX_PENDING_SUGGESTIONS_PER_USER,
    CategorySuggestion,
    CategorySuggestionStatus,
    build_category_slug,
    normalize_suggestion_name,
)
from src.domain.exceptions import (
    CategorySuggestionConflictError,
    CategorySuggestionNotFoundError,
    CategorySuggestionQuotaError,
    DuplicateCategoryError,
    DuplicateCategorySuggestionError,
    ListingForbiddenError,
    ListingUnauthorizedError,
    ModerationForbiddenError,
)
from src.domain.listings import OTHER_CATEGORY_ID, Listing, ListingStatus, utc_now
from src.domain.moderation import (
    ModerationAction,
    ModerationActionType,
    normalize_moderation_reason,
)
from src.domain.users import CurrentUser, User, UserRole
from src.repositories.categories import CategoryRepository
from src.repositories.category_suggestions import CategorySuggestionRepository
from src.repositories.listings import ListingRepository, get_listing_mutation_lock
from src.repositories.moderation import ModerationActionRepository
from src.services.categories import CategoryService


class CategorySuggestionService:
    """Бізнес-правила пропозицій категорій та їх модерації."""

    def __init__(
        self,
        suggestions: CategorySuggestionRepository,
        categories: CategoryRepository,
        category_service: CategoryService,
        listings: ListingRepository,
        actions: ModerationActionRepository,
    ) -> None:
        self._suggestions = suggestions
        self._categories = categories
        self._category_service = category_service
        self._listings = listings
        self._actions = actions
        self._lock = RLock()
        self._listing_lock = get_listing_mutation_lock(listings)

    @property
    def lock(self) -> RLock:
        """Спільний RLock для координації створення пропозиції та оголошення."""
        return self._lock

    def validate_submission(
        self, actor: CurrentUser | User | UUID | None, name: str
    ) -> tuple[UUID, str]:
        """Перевіряє можливість подання пропозиції без її публікації."""
        proposer_id = self._resolve_proposer_id(actor)
        clean_name = normalize_suggestion_name(name)
        with self._lock:
            self._validate_submission_locked(proposer_id, clean_name)
        return proposer_id, clean_name

    def submit(
        self, actor: CurrentUser | User | UUID | None, name: str
    ) -> CategorySuggestion:
        """Створює нову пропозицію категорії від автентифікованого продавця (FR-015)."""
        proposer_id = self._resolve_proposer_id(actor)
        clean_name = normalize_suggestion_name(name)
        with self._lock:
            self._validate_submission_locked(proposer_id, clean_name)
            suggestion = CategorySuggestion(
                name=clean_name,
                proposer_id=proposer_id,
            )
            return self._suggestions.add(suggestion)

    def _validate_submission_locked(self, proposer_id: UUID, clean_name: str) -> None:
        self._check_duplicate_category(clean_name)
        existing_pending = self._suggestions.find_pending_by_name(clean_name)
        if existing_pending is not None:
            raise DuplicateCategorySuggestionError(
                f"Пропозиція категорії '{existing_pending.name}' "
                "вже перебуває на розгляді"
            )
        pending_by_user = self._suggestions.list_by_proposer(
            proposer_id, status=CategorySuggestionStatus.PENDING
        )
        if len(pending_by_user) >= MAX_PENDING_SUGGESTIONS_PER_USER:
            raise CategorySuggestionQuotaError(
                f"Перевищено ліміт активних пропозицій "
                f"({MAX_PENDING_SUGGESTIONS_PER_USER} у статусі PENDING)"
            )

    def list_by_status(
        self,
        moderator: CurrentUser | User | None,
        status: CategorySuggestionStatus = CategorySuggestionStatus.PENDING,
    ) -> list[tuple[CategorySuggestion, int]]:
        """Повертає чергу пропозицій із кількістю активних оголошень (ADMIN)."""
        self._require_admin(moderator)
        with self._lock, self._listing_lock:
            items = self._suggestions.list_by_status(status)
            items.sort(key=lambda item: item.created_at)
            all_listings = self._listings.list_all()
            counts: dict[UUID, int] = {}
            for listing in all_listings:
                if (
                    listing.suggested_category_id is not None
                    and listing.status == ListingStatus.ACTIVE
                ):
                    counts[listing.suggested_category_id] = (
                        counts.get(listing.suggested_category_id, 0) + 1
                    )
            return [(item, counts.get(item.suggestion_id, 0)) for item in items]

    def list_pending(
        self, moderator: CurrentUser | User | None
    ) -> list[tuple[CategorySuggestion, int]]:
        """Скорочення для черги PENDING-пропозицій."""
        return self.list_by_status(moderator, status=CategorySuggestionStatus.PENDING)

    def approve(
        self,
        moderator: CurrentUser | User | None,
        suggestion_id: UUID,
        name: str | None = None,
    ) -> CategorySuggestion:
        """Схвалює пропозицію: створює категорію, переносить оголошення і пише аудит."""
        admin = self._require_admin(moderator)
        with self._lock:
            original = self._require_pending(suggestion_id)
            final_name = (
                normalize_suggestion_name(name) if name is not None else original.name
            )
            self._check_duplicate_category(final_name)
            slug = build_category_slug(final_name)
            slug_collision = self._categories.get_by_slug(slug)
            if slug_collision is not None:
                raise DuplicateCategorySuggestionError(
                    f"Категорія '{slug_collision.name}' "
                    f"вже існує (id={slug_collision.id})",
                    existing_category_id=slug_collision.id,
                    existing_category_name=slug_collision.name,
                )

            affected_originals: list[Listing] = []
            created_category_id: UUID | None = None
            try:
                created_category = self._category_service.create(
                    name=final_name, slug=slug
                )
                created_category_id = created_category.id
                with self._listing_lock:
                    for candidate in list(self._listings.list_all()):
                        if candidate.suggested_category_id != suggestion_id:
                            continue
                        current = self._listings.get(candidate.id)
                        if (
                            current is None
                            or current.suggested_category_id != suggestion_id
                            or current.status != ListingStatus.ACTIVE
                            or current.category_id != OTHER_CATEGORY_ID
                        ):
                            continue
                        affected_originals.append(replace(current))
                        moved = replace(
                            current,
                            category_id=created_category.id,
                            updated_at=max(
                                utc_now(),
                                current.updated_at + timedelta(microseconds=1),
                            ),
                        )
                        self._listings.save(moved)
                approved = replace(
                    original,
                    name=final_name,
                    status=CategorySuggestionStatus.APPROVED,
                    category_id=created_category.id,
                    reviewed_by=admin.user_id,
                    reviewed_at=utc_now(),
                )
                self._suggestions.save(approved)
                self._actions.add(
                    ModerationAction(
                        moderator_id=admin.user_id,
                        suggestion_id=suggestion_id,
                        action_type=ModerationActionType.APPROVE_CATEGORY,
                        reason=f"Схвалено категорію: {final_name}",
                    )
                )
                return approved
            except DuplicateCategoryError as exc:
                self._rollback_changes(
                    original, affected_originals, created_category_id
                )
                raise DuplicateCategorySuggestionError(str(exc)) from exc
            except Exception:
                self._rollback_changes(
                    original, affected_originals, created_category_id
                )
                raise

    def reject(
        self,
        moderator: CurrentUser | User | None,
        suggestion_id: UUID,
        reason: str,
    ) -> CategorySuggestion:
        """Відхиляє пропозицію: залишає оголошення в «Інше» і пише аудит."""
        admin = self._require_admin(moderator)
        clean_reason = normalize_moderation_reason(reason)
        with self._lock:
            original = self._require_pending(suggestion_id)
            linked_originals: list[Listing] = []
            try:
                with self._listing_lock:
                    for candidate in list(self._listings.list_all()):
                        if candidate.suggested_category_id != suggestion_id:
                            continue
                        current = self._listings.get(candidate.id)
                        if (
                            current is None
                            or current.suggested_category_id != suggestion_id
                        ):
                            continue
                        linked_originals.append(replace(current))
                        cleared = replace(
                            current,
                            suggested_category_id=None,
                            updated_at=max(
                                utc_now(),
                                current.updated_at + timedelta(microseconds=1),
                            ),
                        )
                        self._listings.save(cleared)
                rejected = replace(
                    original,
                    status=CategorySuggestionStatus.REJECTED,
                    reason=clean_reason,
                    reviewed_by=admin.user_id,
                    reviewed_at=utc_now(),
                )
                self._suggestions.save(rejected)
                self._actions.add(
                    ModerationAction(
                        moderator_id=admin.user_id,
                        suggestion_id=suggestion_id,
                        action_type=ModerationActionType.REJECT_CATEGORY,
                        reason=clean_reason,
                    )
                )
                return rejected
            except Exception:
                self._rollback_changes(original, linked_originals, None)
                raise

    def get(self, suggestion_id: UUID) -> CategorySuggestion | None:
        """Повертає пропозицію за ID."""
        return self._suggestions.get(suggestion_id)

    def delete(self, suggestion_id: UUID) -> bool:
        """Видаляє пропозицію при відкаті створення оголошення."""
        return self._suggestions.delete(suggestion_id)

    def count_active_listings(self, suggestion_id: UUID) -> int:
        """Підраховує активні оголошення, прив'язані до пропозиції."""
        return sum(
            1
            for item in self._listings.list_all()
            if item.suggested_category_id == suggestion_id
            and item.status == ListingStatus.ACTIVE
        )

    def _require_pending(self, suggestion_id: UUID) -> CategorySuggestion:
        suggestion = self._suggestions.get(suggestion_id)
        if suggestion is None:
            raise CategorySuggestionNotFoundError(
                f"Пропозицію категорії {suggestion_id} не знайдено"
            )
        if suggestion.status != CategorySuggestionStatus.PENDING:
            raise CategorySuggestionConflictError(
                "Пропозиція категорії вже розглянута "
                f"(status={suggestion.status.value})"
            )
        return suggestion

    def _check_duplicate_category(self, name: str) -> None:
        existing_cat = self._categories.get_by_name(name)
        if existing_cat is not None:
            raise DuplicateCategorySuggestionError(
                f"Категорія '{existing_cat.name}' вже існує (id={existing_cat.id})",
                existing_category_id=existing_cat.id,
                existing_category_name=existing_cat.name,
            )

    def _rollback_changes(
        self,
        original_suggestion: CategorySuggestion,
        listing_snapshots: list[Listing],
        created_category_id: UUID | None,
    ) -> None:
        with self._listing_lock:
            for snap in listing_snapshots:
                current = self._listings.get(snap.id)
                if current is not None:
                    restored = replace(
                        current,
                        category_id=snap.category_id,
                        suggested_category_id=snap.suggested_category_id,
                        updated_at=snap.updated_at,
                    )
                    self._listings.save(restored)
                else:
                    self._listings.save(snap)
        if created_category_id is not None:
            self._categories.delete(created_category_id)
        self._suggestions.save(original_suggestion)

    @staticmethod
    def _resolve_proposer_id(actor: CurrentUser | User | UUID | None) -> UUID:
        if actor is None:
            raise ListingUnauthorizedError("Потрібна ідентифікація користувача")
        if isinstance(actor, (CurrentUser, User)):
            if getattr(actor, "is_blocked", False):
                raise ListingForbiddenError(
                    "Заблокований користувач не може пропонувати категорії"
                )
            return actor.user_id
        return actor

    @staticmethod
    def _require_admin(moderator: CurrentUser | User | None) -> CurrentUser | User:
        if moderator is None:
            raise ListingUnauthorizedError("Потрібна ідентифікація користувача")
        if getattr(moderator, "is_blocked", False) or moderator.role != UserRole.ADMIN:
            raise ModerationForbiddenError("Дія дозволена лише адміністраторам")
        return moderator
