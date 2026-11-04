"""Характеризаційні тести доменної сутності Feedback (Лаб 8, Бонус 2).

Фіксують поточну поведінку модуля src/domain/feedback.py, який до Лаб 8
не мав окремих доменних тестів, включно з нетривіальними особливостями
(неявний strip пробілів, точні граничні значення та текст винятків).
"""

from uuid import uuid4
import pytest

from src.domain.exceptions import InvalidFeedbackError
from src.domain.feedback import (
    FEEDBACK_MESSAGE_MAX_LENGTH,
    FEEDBACK_MESSAGE_MIN_LENGTH,
    FEEDBACK_SUBJECT_MAX_LENGTH,
    FEEDBACK_SUBJECT_MIN_LENGTH,
    Feedback,
    FeedbackStatus,
)


def test_feedback_creation_with_valid_data():
    """Фіксація базового створення об'єкта та значень за замовчуванням."""
    uid = uuid4()
    fb = Feedback(
        user_id=uid,
        subject="Питання щодо книги",
        message="Доброго дня, чи актуальне оголошення?",
    )
    assert fb.user_id == uid
    assert fb.subject == "Питання щодо книги"
    assert fb.message == "Доброго дня, чи актуальне оголошення?"
    assert fb.status == FeedbackStatus.NEW
    assert fb.id is not None
    assert fb.created_at is not None
    assert fb.resolved_by is None
    assert fb.resolved_at is None


def test_feedback_strips_whitespace_characters():
    """Фіксація поточної поведінки: неявний strip() для subject та message."""
    uid = uuid4()
    fb = Feedback(
        user_id=uid,
        subject="   Тема з пробілами   ",
        message="   Текст звернення з пробілами довжиною понад 10   ",
    )
    assert fb.subject == "Тема з пробілами"
    assert fb.message == "Текст звернення з пробілами довжиною понад 10"


def test_feedback_boundary_subject_lengths():
    """Фіксація точних меж довжини теми: 3..120 символів."""
    uid = uuid4()
    # Мінімальна валідна довжина (3 символи)
    fb_min = Feedback(user_id=uid, subject="123", message="Валідне повідомлення")
    assert len(fb_min.subject) == 3

    # Максимальна валідна довжина (120 символів)
    max_subject = "a" * 120
    fb_max = Feedback(user_id=uid, subject=max_subject, message="Валідне повідомлення")
    assert len(fb_max.subject) == 120

    # Замала тема після strip (< 3)
    with pytest.raises(InvalidFeedbackError) as exc_info:
        Feedback(user_id=uid, subject=" 12 ", message="Валідне повідомлення")
    msg = (
        f"Тема має містити від {FEEDBACK_SUBJECT_MIN_LENGTH} "
        f"до {FEEDBACK_SUBJECT_MAX_LENGTH} символів"
    )
    assert msg in str(exc_info.value)

    # Завелика тема (> 120)
    with pytest.raises(InvalidFeedbackError) as exc_info:
        Feedback(user_id=uid, subject="a" * 121, message="Валідне повідомлення")
    assert msg in str(exc_info.value)


def test_feedback_boundary_message_lengths():
    """Фіксація точних меж довжини повідомлення: 10..2000 символів."""
    uid = uuid4()
    # Мінімальна валідна довжина (10 символів)
    fb_min = Feedback(user_id=uid, subject="Валідна тема", message="1234567890")
    assert len(fb_min.message) == 10

    # Максимальна валідна довжина (2000 символів)
    max_message = "m" * 2000
    fb_max = Feedback(user_id=uid, subject="Валідна тема", message=max_message)
    assert len(fb_max.message) == 2000

    # Замале повідомлення (< 10 символів)
    with pytest.raises(InvalidFeedbackError) as exc_info:
        Feedback(user_id=uid, subject="Валідна тема", message="Коротко")
    msg = (
        f"Повідомлення має містити від {FEEDBACK_MESSAGE_MIN_LENGTH} "
        f"до {FEEDBACK_MESSAGE_MAX_LENGTH} символів"
    )
    assert msg in str(exc_info.value)

    # Завелике повідомлення (> 2000 символів)
    with pytest.raises(InvalidFeedbackError) as exc_info:
        Feedback(user_id=uid, subject="Валідна тема", message="m" * 2001)
    assert msg in str(exc_info.value)
