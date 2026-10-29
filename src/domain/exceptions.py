"""Доменні помилки Listing Service. Роутер перетворює їх на HTTP-коди."""


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


class ModerationForbiddenError(ListingError):
    """Поточний користувач не має ролі ADMIN для дії модерації."""


class InvalidModerationReasonError(ListingError):
    """Причина модерації порожня або виходить за межі довжини."""
