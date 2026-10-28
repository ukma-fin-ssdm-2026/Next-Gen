"""Точка входу FastAPI: маршрутизація та службові ендпоінти."""

from datetime import datetime, timezone

from fastapi import FastAPI, status
from pydantic import BaseModel, Field

from src.api.routers import auth, favorites, listings

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
app.include_router(favorites.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")


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
