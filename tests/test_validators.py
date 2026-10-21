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
    assert is_valid_telegram_handle(handle) is False

