"""Валідація пошти та контактних даних студента (FR-001, FR-010, SEC-002)."""

import re

ALLOWED_DOMAIN = "ukma.edu.ua"
TELEGRAM_MIN_USERNAME_LEN = 5
TELEGRAM_MAX_USERNAME_LEN = 32
TELEGRAM_HANDLE_PATTERN = re.compile(
    rf"^@[a-zA-Z0-9_]{{{TELEGRAM_MIN_USERNAME_LEN},{TELEGRAM_MAX_USERNAME_LEN}}}$"
)


def _normalize(value: str) -> str:
    return value.strip().lower()


def is_ukma_email(email: str) -> bool:
    """Повертає True, якщо адреса належить домену @ukma.edu.ua."""
    local, _, domain = _normalize(email).rpartition("@")
    return bool(local) and "@" not in local and domain == ALLOWED_DOMAIN


def is_valid_telegram_handle(handle: str) -> bool:
    """Перевіряє, чи є контакт валідним юзернеймом Telegram (@username).

    Вимоги:
    - обов'язковий префікс '@';
    - довжина імені користувача від 5 до 32 символів;
    - дозволені символи: латиниця (a-z, A-Z), цифри (0-9) та символ підкреслення (_).
    """
    normalized = handle.strip()
    return bool(TELEGRAM_HANDLE_PATTERN.match(normalized))
