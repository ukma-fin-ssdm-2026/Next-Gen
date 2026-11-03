"""Приводить запис release-please у CHANGELOG.md до формату Keep a Changelog.

release-please додає новий реліз як ``## [1.0.1](посилання) (2026-11-05)`` і
вставляє його перед ``## [Unreleased]``. Скрипт:

1. перетворює такий заголовок на ``## [1.0.1] - 2026-11-05``;
2. переносить ручні пункти з ``## [Unreleased]`` у новий реліз (за категоріями
   ``### ...``) і лишає порожню секцію ``[Unreleased]`` угорі;
3. перебудовує посилання на порівняння версій унизу файлу.

Файл без запису release-please не змінюється, повторний запуск — теж.

    python -m scripts.release_changelog CHANGELOG.md \\
        --repo-url https://github.com/ukma-fin-ssdm-2026/Next-Gen
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

RELEASE_PLEASE_HEADING = re.compile(
    r"^## \[(?P<version>\d+\.\d+\.\d+)\]\([^)]*\) \((?P<date>\d{4}-\d{2}-\d{2})\)\s*$"
)
VERSION_HEADING = re.compile(r"^## \[(?P<version>\d+\.\d+\.\d+)\] - \d{4}-\d{2}-\d{2}$")
LINK_REFERENCE = re.compile(r"^\[[^\]]+\]: \S+$")
UNRELEASED = "## [Unreleased]"


def _split_sections(body: str) -> tuple[str, list[list[str]]]:
    """Ділить текст на преамбулу і секції `## ...` (заголовок + рядки)."""
    preamble: list[str] = []
    sections: list[list[str]] = []
    for line in body.split("\n"):
        if line.startswith("## "):
            sections.append([line])
        elif sections:
            sections[-1].append(line)
        else:
            preamble.append(line)
    return "\n".join(preamble).rstrip("\n"), sections


def _categories(lines: list[str]) -> dict[str, list[str]]:
    """Збирає пункти секції за категоріями `### ...`, зберігаючи порядок."""
    result: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        if line.startswith("### "):
            current = line
            result.setdefault(current, [])
        elif current is not None and line.strip():
            bullet = "- " + line[2:] if line.startswith("* ") else line
            result[current].append(bullet)
    return result


def _render(heading: str, categories: dict[str, list[str]]) -> list[str]:
    lines = [heading, ""]
    for category, items in categories.items():
        if items:
            lines += [category, "", *items, ""]
    return lines


def normalize_changelog(text: str, repo_url: str) -> str:
    """Повертає нормалізований CHANGELOG; без запису release-please — без змін."""
    if not any(RELEASE_PLEASE_HEADING.match(line) for line in text.split("\n")):
        return text

    content = "\n".join(
        line for line in text.rstrip("\n").split("\n") if not LINK_REFERENCE.match(line)
    )
    preamble, sections = _split_sections(content)

    unreleased_items: dict[str, list[str]] = {}
    releases: list[list[str]] = []
    for section in sections:
        heading = section[0].strip()
        if heading == UNRELEASED:
            unreleased_items = _categories(section[1:])
            continue
        match = RELEASE_PLEASE_HEADING.match(heading)
        if match:
            new_heading = f"## [{match['version']}] - {match['date']}"
            releases.append(["new", new_heading, *section[1:]])
        else:
            releases.append(["old", *section])

    output = [preamble, "", UNRELEASED, ""]
    versions: list[str] = []
    merged = False
    for kind, heading, *lines in releases:
        version_match = VERSION_HEADING.match(heading)
        if version_match:
            versions.append(version_match["version"])
        if kind == "new" and not merged:
            categories = _categories(lines)
            for category, items in unreleased_items.items():
                categories.setdefault(category, []).extend(items)
            output += _render(heading, categories)
            merged = True
        else:
            output += [heading, *[line for line in lines]]
            while output and not output[-1].strip():
                output.pop()
            output.append("")

    if versions:
        output.append(f"[Unreleased]: {repo_url}/compare/v{versions[0]}...HEAD")
        for newer, older in zip(versions, versions[1:]):
            output.append(f"[{newer}]: {repo_url}/compare/v{older}...v{newer}")
        output.append(f"[{versions[-1]}]: {repo_url}/releases/tag/v{versions[-1]}")
    return "\n".join(output).rstrip("\n") + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path, help="Шлях до CHANGELOG.md")
    parser.add_argument("--repo-url", required=True, help="URL репозиторію GitHub")
    args = parser.parse_args()

    original = args.path.read_text(encoding="utf-8")
    normalized = normalize_changelog(original, args.repo_url.rstrip("/"))
    if normalized == original:
        print("CHANGELOG.md уже у форматі Keep a Changelog")
        return
    args.path.write_text(normalized, encoding="utf-8")
    print("CHANGELOG.md нормалізовано до формату Keep a Changelog")


if __name__ == "__main__":
    main()
