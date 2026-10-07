from datetime import datetime
from fastapi import FastAPI, status
from pydantic import BaseModel, Field

# ==============================================================================
# ПРИМІТКА ДЛЯ BACKEND LEAD (Данііл / @megatr4n):
# Цей файл є базовою точкою входу FastAPI для налаштування автогенерації
# специфікації OpenAPI (scripts/generate_openapi.py) та сторінки Swagger UI.
# 
# Тут реалізовано лише системний Health Check ендпоінт для перевірки працездатності.
# Ви можете вільно редагувати цей файл, додавати middleware або підключати
# свої бізнес-роутери через:
# app.include_router(your_router, prefix="/api/v1")
# ==============================================================================

from src.api.routers import listings

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

# Версіонування API (API Versioning)
app.include_router(listings.router, prefix="/api/v1")

class HealthResponse(BaseModel):
    status: str = Field(..., description="Статус доступності сервісу", example="ok")
    app: str = Field(..., description="Назва застосунку", example="Baraholka NaUKMA API")
    version: str = Field(..., description="Поточна версія API", example="1.0.0")
    timestamp: datetime = Field(..., description="Час серверної перевірки")


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Перевірка працездатності API (Health Check)",
    description="Системний ендпоінт для моніторингу працездатності сервісу, перевірки доступності та конвеєрів CI/CD.",
    tags=["System"],
    status_code=status.HTTP_200_OK,
)
def health_check():
    return {
        "status": "ok",
        "app": "Baraholka NaUKMA API",
        "version": "1.0.0",
        "timestamp": datetime.now(),
    }
