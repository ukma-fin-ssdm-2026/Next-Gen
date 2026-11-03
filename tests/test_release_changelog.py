"""Тести автоматизованого релізу (Лаб 8, бонус «Автоматизований реліз»).

release-please створює запис у CHANGELOG.md у власному форматі
`## [1.0.1](посилання) (2026-11-05)`; скрипт `scripts/release_changelog.py`
приводить його до Keep a Changelog `## [1.0.1] - 2026-11-05` і переносить
ручні пункти з `[Unreleased]` у новий реліз.
"""

import yaml

from scripts.generate_openapi import RELEASE_MARKER, render_openapi_yaml
from scripts.release_changelog import normalize_changelog
from src import __version__

REPO = "https://github.com/org/repo"

PREAMBLE = "# Changelog\n\nОпис формату.\n"

RELEASE_PLEASE_OUTPUT = (
    PREAMBLE + "\n## [1.0.1](https://github.com/org/repo/compare/v1.0.0...v1.0.1)"
    " (2026-11-05)\n\n\n"
    "### Refactoring\n\n"
    "* extract method in listing filters ([abc1234](https://github.com/org/repo/"
    "commit/abc1234))\n\n"
    "## [Unreleased]\n\n"
    "### Refactoring\n\n"
    "- Ручний пункт про версію.\n\n"
    "## [1.0.0] - 2026-11-01\n\n"
    "### Added\n\n"
    "- Перший реліз.\n\n"
    "[Unreleased]: https://github.com/org/repo/compare/v1.0.0...HEAD\n"
    "[1.0.0]: https://github.com/org/repo/releases/tag/v1.0.0\n"
)


def test_release_heading_becomes_keep_a_changelog() -> None:
    """[TP-037] Заголовок release-please перетворюється на `## [X.Y.Z] - дата`."""
    result = normalize_changelog(RELEASE_PLEASE_OUTPUT, REPO)
    assert "## [1.0.1] - 2026-11-05\n" in result
    assert "](https://github.com/org/repo/compare/v1.0.0...v1.0.1) (" not in result


def test_unreleased_items_move_into_new_release() -> None:
    """[TP-037] Пункти з [Unreleased] переходять у новий реліз, секція порожніє."""
    result = normalize_changelog(RELEASE_PLEASE_OUTPUT, REPO)
    unreleased = result.split("## [Unreleased]")[1].split("## [1.0.1]")[0]
    release = result.split("## [1.0.1] - 2026-11-05")[1].split("## [1.0.0]")[0]

    assert "Ручний пункт" not in unreleased
    assert "- Ручний пункт про версію." in release
    assert "- extract method in listing filters" in release
    assert release.count("### Refactoring") == 1


def test_sections_are_ordered_unreleased_then_newest() -> None:
    """[TP-037] Порядок: преамбула, [Unreleased], новіші релізи, старіші."""
    result = normalize_changelog(RELEASE_PLEASE_OUTPUT, REPO)
    assert result.startswith(PREAMBLE)
    positions = [
        result.index("## [Unreleased]"),
        result.index("## [1.0.1]"),
        result.index("## [1.0.0]"),
    ]
    assert positions == sorted(positions)


def test_link_references_are_rebuilt() -> None:
    """[TP-037] Посилання внизу відповідають усім релізам і новому тегу."""
    result = normalize_changelog(RELEASE_PLEASE_OUTPUT, REPO)
    assert result.endswith(
        "[Unreleased]: https://github.com/org/repo/compare/v1.0.1...HEAD\n"
        "[1.0.1]: https://github.com/org/repo/compare/v1.0.0...v1.0.1\n"
        "[1.0.0]: https://github.com/org/repo/releases/tag/v1.0.0\n"
    )


def test_normalization_is_idempotent_and_keeps_manual_changelog() -> None:
    """[TP-037] Повторний запуск і файл без запису release-please не змінюються."""
    once = normalize_changelog(RELEASE_PLEASE_OUTPUT, REPO)
    assert normalize_changelog(once, REPO) == once
    manual = PREAMBLE + "\n## [1.0.0] - 2026-11-01\n\n### Added\n\n- Перший реліз.\n"
    assert normalize_changelog(manual, REPO) == manual


def test_openapi_version_line_carries_release_marker() -> None:
    """[TP-037]
    Рядок info.version в OpenAPI має маркер release-please і ту саму версію.
    """
    text = render_openapi_yaml()
    version_lines = [line for line in text.splitlines() if RELEASE_MARKER in line]
    assert version_lines == [f"  version: {__version__} # {RELEASE_MARKER}"]
    assert yaml.safe_load(text)["info"]["version"] == __version__
