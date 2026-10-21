import re

ALLOWED_DOMAIN = "ukma.edu.ua"
TELEGRAM_MIN_USERNAME_LEN = 5
TELEGRAM_MAX_USERNAME_LEN = 32


def _normalize(value: str) -> str:
    return value.strip().lower()


def is_ukma_email(email: str) -> bool:
    """Повертає True, якщо адреса належить домену @ukma.edu.ua."""
    local, _, domain = _normalize(email).rpartition("@")
    return bool(local) and "@" not in local and domain == ALLOWED_DOMAIN


def is_valid_telegram_handle(handle: str) -> bool:
    """Мінімальна валідація префіксу @ та довжини юзернейму."""
    normalized = handle.strip()
    return bool(re.match(r"^@[a-zA-Z0-9_]{5,32}$", normalized))



