"""Узгодженість номера версії релізу (Лаб 8, SemVer, MAINT-001).

Номер версії має бути однаковим у конфігурації бекенду, фронтенду, OpenAPI
та відповіді /health, а CHANGELOG.md — містити секцію для поточної версії.
"""

import json
import re
import tomllib
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from src import __version__
from src.api.main import app

ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def test_version_is_semver() -> None:
    """[TP-036] Єдине джерело версії `src.__version__` має формат MAJOR.MINOR.PATCH."""
    assert SEMVER.fullmatch(__version__), __version__


def test_project_configs_share_one_version() -> None:
    """[TP-036]
    pyproject.toml, frontend/package.json і package-lock.json мають ту саму версію.
    """
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "frontend" / "package.json").read_text("utf-8"))
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text("utf-8"))

    assert pyproject["project"]["version"] == __version__
    assert package["version"] == __version__
    assert lock["version"] == __version__
    assert lock["packages"][""]["version"] == __version__


def test_api_reports_package_version() -> None:
    """[TP-036] FastAPI, згенерований OpenAPI і /health повертають ту саму версію."""
    spec = yaml.safe_load(
        (ROOT / "docs" / "api" / "openapi-generated.yaml").read_text("utf-8")
    )
    assert app.version == __version__
    assert spec["info"]["version"] == __version__
    with TestClient(app) as client:
        assert client.get("/health").json()["version"] == __version__


def test_changelog_has_section_for_current_version() -> None:
    """[TP-036] CHANGELOG.md має секцію `## [версія] - РРРР-ММ-ДД`."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    pattern = rf"^## \[{re.escape(__version__)}\] - \d{{4}}-\d{{2}}-\d{{2}}$"
    assert re.search(pattern, changelog, flags=re.MULTILINE)
