#!/usr/bin/env python3
"""Автоматизація релізу за стандартом Conventional Commits (Lab 08, Bonus 3).

Аналізує історію git-комітів після останнього тегу:
- feat: -> minor bump
- fix:, refactor: -> patch bump (refactor явно підвищує patch)
- BREAKING CHANGE -> major bump

Оновлює pyproject.toml, дописує CHANGELOG.md (Keep a Changelog) та повертає нову версію.
"""

import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = ROOT_DIR / "pyproject.toml"
CHANGELOG_PATH = ROOT_DIR / "CHANGELOG.md"


def get_current_version() -> str:
    content = PYPROJECT_PATH.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        raise ValueError("Не знайдено поле version у pyproject.toml")
    return match.group(1)


def get_commits_since_last_tag() -> list[str]:
    try:
        tag_proc = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        last_tag = tag_proc.stdout.strip() if tag_proc.returncode == 0 else ""
    except Exception:
        last_tag = ""

    rev_range = f"{last_tag}..HEAD" if last_tag else "HEAD"
    log_proc = subprocess.run(
        ["git", "log", rev_range, "--pretty=format:%s"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in log_proc.stdout.splitlines() if line.strip()]


def determine_bump_type(commits: list[str]) -> str:
    """Визначає тип зміни версії: 'major', 'minor', 'patch' або 'none'."""
    bump = "none"
    for msg in commits:
        if "BREAKING CHANGE" in msg or re.match(r"^[a-z]+(\([^\)]+\))?!:", msg):
            return "major"
        if msg.startswith("feat:") or msg.startswith("feat("):
            if bump != "major":
                bump = "minor"
        elif (
            msg.startswith("fix:")
            or msg.startswith("fix(")
            or msg.startswith("refactor:")
            or msg.startswith("refactor(")
        ):
            if bump not in ("major", "minor"):
                bump = "patch"
    return bump


def bump_version(current: str, bump_type: str) -> str:
    parts = [int(p) for p in current.split(".")]
    while len(parts) < 3:
        parts.append(0)
    major, minor, patch = parts[0], parts[1], parts[2]

    if bump_type == "major":
        return f"{major + 1}.0.0"
    if bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    if bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return current


def update_pyproject_version(new_version: str) -> None:
    content = PYPROJECT_PATH.read_text(encoding="utf-8")
    updated = re.sub(
        r'^version\s*=\s*"[^"]+"',
        f'version = "{new_version}"',
        content,
        flags=re.MULTILINE,
    )
    PYPROJECT_PATH.write_text(updated, encoding="utf-8")


def update_changelog(new_version: str, commits: list[str]) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    features: list[str] = []
    fixes: list[str] = []
    refactors: list[str] = []
    others: list[str] = []

    for c in commits:
        if c.startswith("feat"):
            features.append(c)
        elif c.startswith("fix"):
            fixes.append(c)
        elif c.startswith("refactor"):
            refactors.append(c)
        else:
            others.append(c)

    sections = [f"## [{new_version}] - {today}"]
    if features:
        sections.append("\n### Added")
        for f in features:
            sections.append(f"- {f}")
    if refactors:
        sections.append("\n### Refactored")
        for r in refactors:
            sections.append(f"- {r}")
    if fixes:
        sections.append("\n### Fixed")
        for fix in fixes:
            sections.append(f"- {fix}")

    entry = "\n".join(sections) + "\n\n"

    header = (
        "# Changelog\n\n"
        "Усі помітні зміни в проєкті документуються в цьому файлі.\n"
        "Формат базується на "
        "[Keep a Changelog](https://keepachangelog.com/en/1.1.0/),\n"
        "і проєкт дотримується "
        "[Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n\n"
    )

    if CHANGELOG_PATH.exists():
        existing = CHANGELOG_PATH.read_text(encoding="utf-8")
        if "# Changelog" in existing:
            rest = existing[len(header) :] if existing.startswith(header) else existing
            updated_changelog = f"{header}{entry}{rest}"
        else:
            updated_changelog = f"{header}{entry}{existing}"
    else:
        updated_changelog = f"{header}{entry}"

    CHANGELOG_PATH.write_text(updated_changelog, encoding="utf-8")


def main() -> None:
    current = get_current_version()
    commits = get_commits_since_last_tag()
    bump_type = determine_bump_type(commits)

    print(f"Поточна версія: {current}")
    print(f"Знайдено комітів: {len(commits)}")
    print(f"Тип підвищення: {bump_type} (refactor: -> patch)")

    if bump_type == "none" and len(sys.argv) > 1 and sys.argv[1] == "--force-patch":
        bump_type = "patch"

    if bump_type == "none":
        print("Не знайдено змін для релізу.")
        return

    new_version = bump_version(current, bump_type)
    print(f"Нова версія: {new_version}")

    update_pyproject_version(new_version)
    update_changelog(new_version, commits)
    print(f"Оновлено pyproject.toml та CHANGELOG.md для v{new_version}")


if __name__ == "__main__":
    main()
