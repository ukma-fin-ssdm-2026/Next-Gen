"""Точка входу FastAPI: маршрутизація та службові ендпоінти."""

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.openapi.utils import get_openapi
from fastapi.dependencies.models import Dependant
from fastapi.responses import FileResponse, JSONResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from src import __version__
from src.api.deps import get_db_session, get_image_storage
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
from src.db.engine import validate_database_settings
from src.repositories.image_storage import STORAGE_KEY_PATTERN, ImageStorage


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Перевіряє налаштування БД до прийому запитів (REL-03, fail fast)."""
    validate_database_settings()
    yield


app = FastAPI(
    title="Baraholka NaUKMA API",
    description=(
        "REST API для маркетплейсу студентських оголошень Києво-Могилянської академії "
        "(Baraholka NaUKMA). Розроблено за підходом Code-First."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

logger = logging.getLogger(__name__)

# REL-03: швидка відмова при недоступній БД. Клієнт отримує 503 з Retry-After
# замість зависання чи 500 з внутрішніми деталями; пул сам перепідключається
# (pool_pre_ping), коли PostgreSQL знову доступний.
DB_UNAVAILABLE_DETAIL = "База даних тимчасово недоступна. Спробуйте за кілька секунд."
DB_RETRY_AFTER_SECONDS = 5
DB_UNAVAILABLE_RESPONSE = {
    "description": "База даних тимчасово недоступна (REL-03); повторіть запит пізніше",
    "headers": {
        "Retry-After": {
            "description": "Через скільки секунд варто повторити запит",
            "schema": {"type": "integer", "example": DB_RETRY_AFTER_SECONDS},
        }
    },
    "content": {"application/json": {"example": {"detail": DB_UNAVAILABLE_DETAIL}}},
}


@app.exception_handler(OperationalError)
@app.exception_handler(PoolTimeoutError)
async def database_unavailable_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Перетворює збій підключення до БД або вичерпаний пул на HTTP 503."""
    logger.error(
        "База даних недоступна під час %s %s: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": DB_UNAVAILABLE_DETAIL},
        headers={"Retry-After": str(DB_RETRY_AFTER_SECONDS)},
    )


def _depends_on(dependant: Dependant, target: Callable) -> bool:
    """Чи є `target` серед залежностей ендпоінту (на будь-якій глибині)."""
    return any(
        sub.call is target or _depends_on(sub, target) for sub in dependant.dependencies
    )


def _declare_database_unavailable(router: APIRouter) -> None:
    """Додає 503 лише операціям, які відкривають сесію БД (REL-03).

    Тобто 503 бачать у контракті тільки ендпоінти, що справді можуть його
    повернути; /health, /uploads і SPA його не отримують.
    """
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        if not _depends_on(route.dependant, get_db_session):
            continue
        existing = route.responses.get(status.HTTP_503_SERVICE_UNAVAILABLE)
        if existing is None:
            route.responses[status.HTTP_503_SERVICE_UNAVAILABLE] = (
                DB_UNAVAILABLE_RESPONSE
            )
        else:
            # Ендпоінт уже повертає 503 з іншої причини (Entra не налаштовано).
            # Retry-After додається лише у відповідь про недоступну БД.
            route.responses[status.HTTP_503_SERVICE_UNAVAILABLE] = {
                **existing,
                "description": f"{existing['description']}; "
                "або база даних тимчасово недоступна (REL-03)",
                "headers": {
                    **existing.get("headers", {}),
                    **DB_UNAVAILABLE_RESPONSE["headers"],
                },
            }


for _router in (
    listings.router,
    contacts.router,
    favorites.router,
    categories.router,
    category_suggestions.router,
    auth.router,
    moderation.router,
    users.router,
    complaints.router,
    feedback.router,
    activity.router,
):
    _declare_database_unavailable(_router)
    app.include_router(_router, prefix="/api/v1")


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
