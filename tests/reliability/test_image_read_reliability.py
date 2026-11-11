"""Тести надійності віддачі фото `GET /uploads/{storage_key}` (Лаб 9, REL-02).

Несправність: `except Exception` перетворював будь-який збій читання (немає
прав, помилка диска, навіть баг у коді) на 404 без запису в лог. Тепер:
- відсутній файл або некоректний ключ лишаються штатним 404;
- збій сховища (`OSError`) дає швидку відмову 503 з `Retry-After`,
  `Cache-Control: no-store` і записом у лог;
- непередбачений виняток більше не маскується під 404 (стандартний 500).
"""

import errno
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_image_storage
from src.api.main import IMAGE_STORAGE_RETRY_AFTER_SECONDS, app
from src.repositories.image_storage import InMemoryImageStorage, LocalImageStorage

KEY = "0123456789abcdef0123456789abcdef.webp"
WEBP = b"RIFF\x1a\x00\x00\x00WEBPVP8 fake"


@pytest.fixture
def storage(tmp_path: Path):
    local = LocalImageStorage(tmp_path)
    (tmp_path / KEY).write_bytes(WEBP)
    app.dependency_overrides[get_image_storage] = lambda: local
    yield local
    app.dependency_overrides.pop(get_image_storage, None)


@pytest.mark.parametrize(
    "fault",
    [
        PermissionError(errno.EACCES, "Permission denied", "/var/lib/uploads/x"),
        OSError(errno.EIO, "Input/output error", "/var/lib/uploads/x"),
    ],
    ids=["permission-denied", "disk-io-error"],
)
def test_storage_failure_returns_503_and_is_logged(
    storage, monkeypatch, caplog, fault
) -> None:
    """[TP-038] [FR-002]
    Ін'єкція збою: читання файлу з тома падає з OSError. Відповідь — 503 з
    Retry-After і no-store (не 404 і не кешується), без шляхів на диску. У лозі є
    збій зі шляхом файлу з винятку, але немає значення з URL (захист від log
    injection).
    """

    def failing_read(self):
        raise fault

    monkeypatch.setattr(Path, "read_bytes", failing_read)

    with caplog.at_level(logging.ERROR, logger="src.api.main"):
        response = TestClient(app).get(f"/uploads/{KEY}")

    assert response.status_code == 503
    assert response.headers["Retry-After"] == str(IMAGE_STORAGE_RETRY_AFTER_SECONDS)
    assert response.headers["Cache-Control"] == "no-store"
    assert "/var/lib/uploads" not in response.text
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert errors and errors[0].exc_info is not None
    assert "/var/lib/uploads/x" in caplog.text
    assert all(KEY not in record.getMessage() for record in caplog.records)


def test_missing_file_and_invalid_key_stay_404(storage, tmp_path: Path) -> None:
    """[TP-038] [FR-002]
    Граничні випадки: невідомий ключ, некоректний ключ і файл, видалений між
    перевіркою та читанням, — це штатний 404, а не збій сховища.
    """
    client = TestClient(app)
    assert client.get("/uploads/" + "f" * 32 + ".webp").status_code == 404
    assert client.get("/uploads/not-a-key.webp").status_code == 404

    original_is_file = Path.is_file

    def vanished(self):
        # Перевірка бачить файл, але до читання його вже видалили.
        exists = original_is_file(self)
        if self.name == KEY:
            self.unlink()
        return exists

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(Path, "is_file", vanished)
        assert client.get(f"/uploads/{KEY}").status_code == 404


def test_existing_image_is_served_with_immutable_cache(storage) -> None:
    """[TP-038] [FR-002]
    Штатний шлях не змінився: наявне фото віддається 200 image/webp з довгим кешем.
    """
    response = TestClient(app).get(f"/uploads/{KEY}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["Cache-Control"] == "public, max-age=86400, immutable"
    assert response.content == WEBP


def test_unexpected_error_is_not_masked_as_404(storage, monkeypatch) -> None:
    """[TP-038] [FR-002]
    Помилка в коді (не OSError) більше не ховається під 404: клієнт бачить 500,
    а виняток доходить до серверного логування.
    """

    def buggy_read(self, key):
        raise RuntimeError("bug in storage adapter")

    monkeypatch.setattr(LocalImageStorage, "_read_blob", buggy_read)

    response = TestClient(app, raise_server_exceptions=False).get(f"/uploads/{KEY}")

    assert response.status_code == 500


def test_in_memory_blob_removed_concurrently_is_404(monkeypatch) -> None:
    """[TP-038] [FR-002]
    In-memory сховище: блоб зник між перевіркою та читанням — це 404, а не 500
    через KeyError.
    """
    memory = InMemoryImageStorage()
    monkeypatch.setattr(InMemoryImageStorage, "_blob_exists", lambda self, key: True)
    app.dependency_overrides[get_image_storage] = lambda: memory
    try:
        assert TestClient(app).get(f"/uploads/{KEY}").status_code == 404
    finally:
        app.dependency_overrides.pop(get_image_storage, None)
