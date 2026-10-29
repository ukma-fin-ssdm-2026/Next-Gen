"""Точка входу FastAPI: маршрутизація та службові ендпоінти."""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.api.routers import (
    auth,
    categories,
    contacts,
    favorites,
    listings,
    moderation,
)

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
app.include_router(auth.router, prefix="/api/v1")
app.include_router(moderation.router, prefix="/api/v1")

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
RESERVED_FRONTEND_PREFIXES = (
    "api/",
    "docs",
    "redoc",
    "openapi.json",
    "health",
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
