"""Валідація університетської пошти (FR-001, SEC-001)."""

ALLOWED_DOMAIN = "ukma.edu.ua"


def _normalize(email: str) -> str:
    return email.strip().lower()


def is_ukma_email(email: str) -> bool:
    """Повертає True, якщо адреса належить домену @ukma.edu.ua."""
    local, _, domain = _normalize(email).rpartition("@")
    return bool(local) and "@" not in local and domain == ALLOWED_DOMAIN


def is_valid_telegram_handle(handle: str) -> bool:
    """Мінімальна валідація префіксу @ та довжини юзернейму."""
    if not handle.startswith("@"):
        return False
    username = handle[1:]
    return 5 <= len(username) <= 32

