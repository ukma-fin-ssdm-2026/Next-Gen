"""Tests for the controlled production-data seeding utility."""

from io import BytesIO
import sys
from types import SimpleNamespace

from PIL import Image
import pytest

from scripts.seed_listings import make_test_image, parse_args, select_category


class StubCategoryRepository:
    def __init__(self, categories):
        self.categories = categories

    def get_by_slug(self, slug):
        return next(
            (category for category in self.categories if category.slug == slug),
            None,
        )

    def list_active(self):
        return [category for category in self.categories if category.is_active]


def test_make_test_image_returns_valid_jpeg() -> None:
    """[TP-001] [FR-002] Seed utility produces a valid listing image."""
    image = Image.open(BytesIO(make_test_image(1)))

    assert image.format == "JPEG"
    assert image.size == (900, 600)


def test_select_category_uses_first_active_category() -> None:
    """[TP-001] [FR-002] Seed listings use only an active category."""
    inactive = SimpleNamespace(slug="inactive", is_active=False)
    active = SimpleNamespace(slug="books", is_active=True)
    repository = StubCategoryRepository([inactive, active])

    assert select_category(repository, None) is active
    assert select_category(repository, "books") is active


def test_cleanup_requires_explicit_confirmation(monkeypatch) -> None:
    """[TP-001] [FR-002] Destructive seed cleanup requires confirmation."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["seed_listings.py", "--owner-email", "student@ukma.edu.ua", "--cleanup"],
    )

    with pytest.raises(SystemExit) as exc_info:
        parse_args()

    assert exc_info.value.code == 2
