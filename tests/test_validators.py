import pytest

from src.domain.validators import is_ukma_email, is_valid_telegram_handle


@pytest.mark.parametrize(
    "email",
    [
        "student@ukma.edu.ua",
        "  Student@UKMA.edu.ua ",
    ],
)
def test_accepts_ukma_email(email):
    """[FR-001] [SEC-001] Валідація корпоративної пошти НаУКМА."""
    assert is_ukma_email(email) is True


@pytest.mark.parametrize(
    "email",
    [
        "student@gmail.com",
        "@ukma.edu.ua",
        "a@b@ukma.edu.ua",
    ],
)
def test_rejects_invalid_email(email):
    """[FR-001] [SEC-001] Відхилення сторонніх чи невалідних поштових адрес."""
    assert is_ukma_email(email) is False


@pytest.mark.parametrize(
    "handle",
    [
        "@student",
        "@valid_user",
        "  @student_ukma  ",
    ],
)
def test_accepts_valid_telegram_handle_format(handle):
    """[FR-002] [SEC-002] Валідація коректного формату Telegram-контакту."""
    assert is_valid_telegram_handle(handle) is True


@pytest.mark.parametrize(
    "handle",
    [
        "student",  # пропущено @
        "@a",  # занадто короткий (< 5 символів після @)
        "@" + "a" * 33,  # занадто довгий (> 32 символи)
    ],
)
def test_rejects_telegram_handle_missing_prefix_or_invalid_length(handle):
    """[FR-002] [SEC-002] Відхилення Telegram-контакту з невалідною довжиною."""
    assert is_valid_telegram_handle(handle) is False


@pytest.mark.parametrize(
    "handle",
    [
        "@user.name",  # крапка недопустима в юзернеймі TG
        "@user-name",  # дефіс недопустимий
        "@user name",  # пробіл всередині
        "@студент",  # кирилиця заборонена
        "@user!name",  # спецсимволи заборонені
    ],
)
def test_rejects_telegram_handle_invalid_characters(handle):
    """[FR-002] [SEC-002] Відхилення заборонених символів у Telegram-контакті."""
    assert is_valid_telegram_handle(handle) is False
