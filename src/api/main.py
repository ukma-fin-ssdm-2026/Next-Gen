"""Точка входу FastAPI: маршрутизація та службові ендпоінти."""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.api.deps import get_image_storage
from src.api.routers import (
    auth,
    categories,
    category_suggestions,
    contacts,
    favorites,
    listings,
    moderation,
    users,
)
from src.repositories.image_storage import STORAGE_KEY_PATTERN, ImageStorage

app = FastAPI(
    title="Baraholka NaUKMA API",
    description=(
        "REST API для маркетплейсу студентських оголошень Києво-Могилянської академії "
        "(Baraholka NaUKMA). Розроблено за підходом Code-First."
    ),
    version="1.0.0",
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
    version: str = Field(..., description="Поточна версія API", examples=["1.0.0"])
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
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc),
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
        if frontend_path.startswith(RESERVED_FRONTEND_PREFIXES):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        frontend_root = FRONTEND_DIST.resolve()
        requested_file = (frontend_root / frontend_path).resolve()
        if (
            frontend_path
            and requested_file.is_file()
            and requested_file.is_relative_to(frontend_root)
        ):
            return FileResponse(requested_file)
        return FileResponse(frontend_root / "index.html")
