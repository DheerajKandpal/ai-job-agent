import time

from app.core.config import settings
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    EXCLUDED_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}

    def __init__(self, app):
        super().__init__(app)
        self.requests = {}

    async def dispatch(self, request, call_next):
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        cutoff = now - settings.RATE_LIMIT_WINDOW_SECONDS

        timestamps = self.requests.get(client_ip, [])
        timestamps = [timestamp for timestamp in timestamps if timestamp > cutoff]

        if timestamps:
            self.requests[client_ip] = timestamps
        else:
            self.requests.pop(client_ip, None)

        if len(timestamps) >= settings.RATE_LIMIT_MAX_REQUESTS:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"},
            )

        timestamps.append(now)
        self.requests[client_ip] = timestamps

        return await call_next(request)
