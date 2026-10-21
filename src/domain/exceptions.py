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
