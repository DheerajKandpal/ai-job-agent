import secrets

from app.core.config import settings
from app.core.logging import get_logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = get_logger(__name__)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    EXCLUDED_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}

    def __init__(self, app):
        super().__init__(app)
        self.api_key = settings.API_KEY

    async def dispatch(self, request, call_next):
        if request.method == "OPTIONS" or request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        provided_api_key = request.headers.get("X-API-KEY")
        authorization = request.headers.get("Authorization")
        if (provided_api_key is None or not provided_api_key.strip()) and authorization:
            auth_value = authorization.strip()
            if auth_value.lower().startswith("bearer "):
                provided_api_key = auth_value[7:].strip()

        if provided_api_key is None or not provided_api_key.strip():
            logger.warning(
                "api key missing",
                extra={"path": request.url.path, "method": request.method},
            )
            return JSONResponse(
                status_code=401,
                content={"error": "API key missing"},
            )

        if not secrets.compare_digest(provided_api_key.strip(), self.api_key):
            logger.warning(
                "invalid api key",
                extra={"path": request.url.path, "method": request.method},
            )
            return JSONResponse(
                status_code=403,
                content={"error": "Invalid API key"},
            )

        return await call_next(request)
