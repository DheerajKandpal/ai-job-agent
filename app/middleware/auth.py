import os
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    EXCLUDED_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}

    def __init__(self, app):
        super().__init__(app)
        self.api_key = os.getenv("API_KEY")
        if not self.api_key:
            raise RuntimeError("API_KEY environment variable is not set")

    async def dispatch(self, request, call_next):
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        provided_api_key = request.headers.get("X-API-KEY")

        if provided_api_key is None or not provided_api_key.strip():
            return JSONResponse(
                status_code=401,
                content={"error": "API key missing"},
            )

        if not secrets.compare_digest(provided_api_key.strip(), self.api_key):
            return JSONResponse(
                status_code=403,
                content={"error": "Invalid API key"},
            )

        return await call_next(request)
