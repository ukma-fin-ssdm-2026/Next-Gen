"""Доменні помилки Listing Service. Роутер перетворює їх на HTTP-коди."""

from uuid import UUID


class ListingError(Exception):
    """Базова помилка операцій з оголошеннями."""


class ListingNotFoundError(ListingError):
    """Оголошення з указаним ідентифікатором не існує."""


class ListingUnauthorizedError(ListingError):
    """Немає ідентифікатора поточного користувача."""


class ListingForbiddenError(ListingError):
    """Поточний користувач не є власником оголошення."""


class InvalidPriceRangeError(ListingError):
    """Мінімальна ціна фільтрації перевищує максимальну ціну."""


class InvalidListingImageError(ListingError):
    """Некоректні дані або кількість зображень оголошення."""


class ImageUploadRateLimitError(InvalidListingImageError):
    """Перевищено ліміт запитів на завантаження зображень (TM-08)."""


class FavoriteNotFoundError(ListingError):
    """Оголошення немає в обраному поточного користувача."""


class CategoryError(ListingError):
    """Базова помилка операцій з категоріями."""


class CategoryNotFoundError(CategoryError):
    """Категорію з указаним ідентифікатором або slug не знайдено."""


class DuplicateCategoryError(CategoryError):
    """Категорія з таким slug вже існує."""


class InvalidCategoryError(CategoryError):
    """Некоректні дані категорії."""


class CategorySuggestionError(CategoryError):
    """Базова помилка операцій з пропозиціями категорій (FR-015)."""


class CategorySuggestionNotFoundError(CategorySuggestionError):
    """Пропозицію категорії не знайдено."""


class InvalidCategorySuggestionError(CategorySuggestionError):
    """Некоректна назва пропозиції категорії (довжина або керівні символи)."""


class DuplicateCategorySuggestionError(CategorySuggestionError):
    """Пропозиція дублює наявну категорію або іншу активну пропозицію."""

    def __init__(
        self,
        message: str,
        *,
        existing_category_id: UUID | None = None,
        existing_category_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.existing_category_id = existing_category_id
        self.existing_category_name = existing_category_name


class CategorySuggestionConflictError(CategorySuggestionError):
    """Пропозицію категорії вже розглянуто (повторне схвалення або відхилення)."""


class CategorySuggestionQuotaError(CategorySuggestionError):
    """Перевищено ліміт активних (PENDING) пропозицій категорій на користувача."""


class ModerationForbiddenError(ListingError):
    """Поточний користувач не має ролі ADMIN для дії модерації."""


class InvalidModerationReasonError(ListingError):
    """Причина модерації порожня або виходить за межі довжини."""


class ProfileError(Exception):
    """Базова помилка операцій з профілем користувача."""


class InvalidProfileError(ProfileError):
    """Некоректні дані профілю (ім'я, контакт, аватарка)."""


class ProfileNotFoundError(ProfileError):
    """Профіль користувача не знайдено."""


class UserNotFoundError(ListingError):
    """Користувача для адміністративної дії не знайдено."""


class InvalidUserModerationError(ListingError):
    """Дію над користувачем не можна виконати (самоблокування, адміністратор, стан)."""


class ComplaintError(Exception):
    """Базова помилка скарг на оголошення (FR-016)."""


class InvalidComplaintError(ComplaintError):
    """Некоректні дані скарги."""


class ComplaintNotFoundError(ComplaintError):
    """Скаргу не знайдено."""


class DuplicateComplaintError(ComplaintError):
    """Користувач уже скаржився на це оголошення."""


class ComplaintConflictError(ComplaintError):
    """Скаргу вже розглянуто."""


class FeedbackError(Exception):
    """Базова помилка звернень до адміністрації (FR-017)."""


class InvalidFeedbackError(FeedbackError):
    """Некоректні дані звернення."""


class FeedbackNotFoundError(FeedbackError):
    """Звернення не знайдено."""


class FeedbackConflictError(FeedbackError):
    """Звернення вже опрацьовано."""
