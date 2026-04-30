import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import configure_logging, get_logger, reset_request_id, set_request_id
from app.middleware.auth import APIKeyAuthMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.routes.applications import router as applications_router
from app.routes.cover_letter import router as cover_letter_router
from app.routes.match import router as match_router
from app.routes.tailor import router as tailor_router
from app.services.tracker.db_service import check_database_connection, init_database

configure_logging()

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)
logger = get_logger(__name__)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(APIKeyAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(match_router)
app.include_router(tailor_router)
app.include_router(cover_letter_router)
app.include_router(applications_router)

@app.on_event("startup")
def on_startup() -> None:
    try:
        settings.validate()
        check_database_connection()
        init_database()
        logger.info("startup validation passed")
    except Exception as exc:
        logger.critical(
            "startup validation failed",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={"error": str(exc)},
        )
        raise


@app.on_event("shutdown")
def on_shutdown() -> None:
    logger.info("application shutdown complete")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
    token = set_request_id(request_id)
    started_at = time.monotonic()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        logger.exception(
            "request failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
            },
        )
        raise
    finally:
        duration_ms = round((time.monotonic() - started_at) * 1000, 2)
        logger.info(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "client": request.client.host if request.client else None,
            },
        )
        reset_request_id(token)


@app.exception_handler(ValueError)
def handle_value_error(_: Request, exc: ValueError) -> JSONResponse:
    logger.warning("value error", extra={"error": str(exc)})
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.exception_handler(Exception)
def handle_exception(_: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled error",
        exc_info=(type(exc), exc, exc.__traceback__),
        extra={"error": str(exc)},
    )
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.APP_ENV}
