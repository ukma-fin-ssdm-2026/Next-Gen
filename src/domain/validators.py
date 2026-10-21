"""Валідація університетської пошти (FR-001, SEC-001)."""

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
    if not normalized.startswith("@"):
        return False
    username = normalized[1:]
    return TELEGRAM_MIN_USERNAME_LEN <= len(username) <= TELEGRAM_MAX_USERNAME_LEN


