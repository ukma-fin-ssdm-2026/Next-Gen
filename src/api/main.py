"""Точка входу FastAPI: маршрутизація та службові ендпоінти."""

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from src import __version__
from src.api.deps import get_database_readiness_probe, get_image_storage
from src.api.routers import (
    activity,
    auth,
    categories,
    category_suggestions,
    complaints,
    contacts,
    favorites,
    feedback,
    listings,
    moderation,
    users,
)
from src.repositories.image_storage import STORAGE_KEY_PATTERN, ImageStorage

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Baraholka NaUKMA API",
    description=(
        "REST API для маркетплейсу студентських оголошень Києво-Могилянської академії "
        "(Baraholka NaUKMA). Розроблено за підходом Code-First."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(listings.router, prefix="/api/v1")
app.include_router(contacts.router, prefix="/api/v1")
app.include_router(favorites.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(category_suggestions.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(moderation.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(complaints.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(activity.router, prefix="/api/v1")


def _custom_openapi() -> dict:
    """Прибирає автоматичний 422 з операцій, які не мають що валідувати.

    Якщо операція приймає лише cookie сесії (без тіла, path, query чи header),
    FastAPI все одно додає `422 HTTPValidationError`, хоча ендпоїнт його не
    повертає. Явно задекларовані 422 (власна схема помилки) не чіпаються.
    """
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict) or "requestBody" in operation:
                continue
            params = operation.get("parameters", [])
            response_422 = operation.get("responses", {}).get("422", {})
            auto = "HTTPValidationError" in str(response_422)
            if auto and all(item.get("in") == "cookie" for item in params):
                operation["responses"].pop("422")
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi  # type: ignore[method-assign]


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
RESERVED_FRONTEND_PREFIXES = (
    "api/",
    "docs",
    "redoc",
    "openapi.json",
    "health",
    "uploads/",
)


class HealthResponse(BaseModel):
    status: str = Field(..., description="Статус доступності сервісу", examples=["ok"])
    app: str = Field(
        ...,
        description="Назва застосунку",
        examples=["Baraholka NaUKMA API"],
    )
    version: str = Field(..., description="Поточна версія API", examples=[__version__])
    timestamp: datetime = Field(..., description="Час серверної перевірки")


class ReadinessResponse(BaseModel):
    status: str = Field(..., description="Готовність API обслуговувати запити")
    database: str = Field(..., description="Стан активного сховища даних")
    timestamp: datetime = Field(..., description="Час серверної перевірки")


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Перевірка працездатності API (Health Check)",
    description=(
        "Системний ендпоінт для моніторингу працездатності сервісу, перевірки "
        "доступності та конвеєрів CI/CD."
    ),
    tags=["System"],
    status_code=status.HTTP_200_OK,
)
def health_check() -> dict:
    """Повертає службовий статус процесу API."""
    return {
        "status": "ok",
        "app": "Baraholka NaUKMA API",
        "version": __version__,
        "timestamp": datetime.now(timezone.utc),
    }


@app.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ReadinessResponse,
            "description": "PostgreSQL тимчасово недоступний",
        }
    },
    summary="Перевірка готовності API та сховища даних",
    description=(
        "Readiness probe перевіряє активне сховище даних. На відміну від "
        "liveness endpoint `/health`, він повертає 503, якщо PostgreSQL "
        "недоступний."
    ),
    tags=["System"],
)
def readiness_check(
    probe: Callable[[], str] = Depends(get_database_readiness_probe),
) -> dict | JSONResponse:
    """Повертає 200 лише коли API та активне сховище готові до роботи."""
    timestamp = datetime.now(timezone.utc)
    try:
        database_status = probe()
    except (SQLAlchemyError, OSError):
        logger.warning("Database readiness probe failed", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unavailable",
                "database": "unavailable",
                "timestamp": timestamp.isoformat(),
            },
        )
    return {
        "status": "ready",
        "database": database_status,
        "timestamp": timestamp,
    }


@app.get(
    "/uploads/{storage_key}",
    include_in_schema=False,
    summary="Отримати завантажене зображення або thumbnail",
)
def get_uploaded_image(
    storage_key: str,
    storage: ImageStorage = Depends(get_image_storage),
) -> Response:
    """Віддає збережене зображення оголошення або thumbnail у форматі WebP (FR-002)."""
    if not STORAGE_KEY_PATTERN.fullmatch(storage_key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        content = storage.read_image(storage_key)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return Response(
        content=content,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=86400, immutable"},
    )


def resolve_frontend_file(frontend_path: str, frontend_root: Path) -> Path:
    """Повертає файл React build-у для шляху або index.html для SPA-маршруту.

    404 для зарезервованих префіксів backend, для шляхів поза build-ом і для
    невідомих file-like шляхів (з розширенням): вони не маскуються під
    успішний React-маршрут (TM-03).
    """
    if frontend_path.startswith(RESERVED_FRONTEND_PREFIXES):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    root = frontend_root.resolve()
    requested_file = (root / frontend_path).resolve()
    if (
        frontend_path
        and requested_file.is_relative_to(root)
        and requested_file.is_file()
    ):
        return requested_file
    if PurePosixPath(frontend_path).suffix:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return root / "index.html"


if FRONTEND_DIST.is_dir():
    assets_directory = FRONTEND_DIST / "assets"
    if assets_directory.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=assets_directory),
            name="frontend-assets",
        )

    @app.get("/{frontend_path:path}", include_in_schema=False)
    def serve_frontend(frontend_path: str) -> FileResponse:
        """Віддає React build і підтримує пряме відкриття SPA-маршрутів."""
        return FileResponse(resolve_frontend_file(frontend_path, FRONTEND_DIST))
