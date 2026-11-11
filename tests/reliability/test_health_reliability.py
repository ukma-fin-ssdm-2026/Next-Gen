"""Тести readiness-перевірки залежності PostgreSQL для Лабораторної 9."""

import logging
from collections.abc import Callable

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.exc import OperationalError

from src.api.deps import get_database_readiness_probe
from src.api.main import app


def _client_with_probe(probe: Callable[[], str]) -> TestClient:
    app.dependency_overrides[get_database_readiness_probe] = lambda: probe
    return TestClient(app)


def test_readiness_reports_ready_when_database_responds() -> None:
    """[REL-001] REL-08: успішний probe підтверджує готовність залежності."""
    client = _client_with_probe(lambda: "ok")
    try:
        response = client.get("/health/ready")
    finally:
        app.dependency_overrides.pop(get_database_readiness_probe, None)

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["database"] == "ok"


def test_readiness_fault_injection_returns_safe_503(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """[REL-001] REL-08: збій PostgreSQL дає безпечну 503 без витоку деталей."""

    def failed_probe() -> str:
        raise OperationalError(
            "SELECT secret FROM internal_table",
            {},
            OSError("database password leaked in diagnostic"),
        )

    client = _client_with_probe(failed_probe)
    with caplog.at_level(logging.WARNING, logger="src.api.main"):
        try:
            response = client.get("/health/ready")
        finally:
            app.dependency_overrides.pop(get_database_readiness_probe, None)

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert response.json()["database"] == "unavailable"
    assert "secret" not in response.text
    assert "password" not in response.text
    assert "Database readiness probe failed" in caplog.text


def test_liveness_remains_available_during_database_failure() -> None:
    """[REL-001] REL-08: падіння залежності не означає падіння процесу API."""

    def failed_probe() -> str:
        raise OperationalError("SELECT 1", {}, OSError("database unavailable"))

    client = _client_with_probe(failed_probe)
    try:
        readiness = client.get("/health/ready")
        liveness = client.get("/health")
    finally:
        app.dependency_overrides.pop(get_database_readiness_probe, None)

    assert readiness.status_code == 503
    assert liveness.status_code == 200
    assert liveness.json()["status"] == "ok"
