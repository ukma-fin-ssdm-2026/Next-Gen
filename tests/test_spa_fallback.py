"""Регресійні тести SPA fallback (FR-002, TM-03).

Невідомі file-like шляхи (з розширенням) мають давати 404, а не маскуватися
під успішний React-маршрут; маршрути React без розширення віддають index.html.
"""

from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api.main import FRONTEND_DIST, app, resolve_frontend_file


@pytest.fixture
def frontend_root(tmp_path: Path) -> Path:
    root = tmp_path / "dist"
    root.mkdir()
    (root / "index.html").write_text("<!doctype html><div id=root></div>")
    (root / "favicon.svg").write_text("<svg/>")
    (tmp_path / "secret.txt").write_text("top secret")
    return root


@pytest.mark.parametrize(
    "path",
    [
        "",
        "listings",
        "listings/3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "admin/logs/admins",
    ],
)
def test_react_routes_fall_back_to_index(frontend_root: Path, path: str) -> None:
    """[TP-023] [FR-002] Маршрути React без розширення віддають index.html."""
    assert resolve_frontend_file(path, frontend_root) == frontend_root / "index.html"


def test_existing_build_file_is_served(frontend_root: Path) -> None:
    """[TP-023] [FR-002] Наявний файл build-у віддається як є."""
    assert resolve_frontend_file("favicon.svg", frontend_root) == (
        frontend_root / "favicon.svg"
    )


@pytest.mark.parametrize(
    "path",
    ["secret.txt", "../secret.txt", "assets/nonexistent.js", "missing/image.webp"],
)
def test_unknown_file_like_paths_are_404(frontend_root: Path, path: str) -> None:
    """[TP-023] [FR-002]
    Невідомий file-like шлях або вихід за межі build-у дає 404, а не index.html.
    """
    with pytest.raises(HTTPException) as error:
        resolve_frontend_file(path, frontend_root)
    assert error.value.status_code == 404


@pytest.mark.parametrize(
    "path", ["api/v1/unknown", "uploads/x", "docs", "redoc", "openapi.json", "health"]
)
def test_reserved_prefixes_are_404(frontend_root: Path, path: str) -> None:
    """[TP-023] [FR-002] Зарезервовані префікси backend не віддають React."""
    with pytest.raises(HTTPException) as error:
        resolve_frontend_file(path, frontend_root)
    assert error.value.status_code == 404


@pytest.mark.skipif(
    not FRONTEND_DIST.is_dir(), reason="Потрібен зібраний frontend/dist"
)
def test_http_spa_fallback_with_built_frontend() -> None:
    """[TP-023] [FR-002]
    Через HTTP із зібраним frontend: React-маршрути 200, file-like шляхи 404.
    """
    with TestClient(app) as client:
        for path in ("/listings", "/admin/logs/admins"):
            response = client.get(path)
            assert response.status_code == 200, path
            assert "text/html" in response.headers["content-type"]
        for path in (
            "/uploads/nonexistent.webp",
            "/uploads/../../secret.txt",
            "/secret.txt",
            "/assets/nonexistent.js",
        ):
            assert client.get(path).status_code == 404, path
