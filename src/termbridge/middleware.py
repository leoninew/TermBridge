import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        path = request.url.path
        if request.url.query:
            path = f"{path}?{request.url.query}"

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "Request failed method=%s path=%s duration_ms=%.2f",
                request.method,
                path,
                duration_ms,
            )
            raise

        duration_ms = (time.perf_counter() - started) * 1000
        log = logger.info
        if response.status_code >= 500:
            log = logger.error
        elif response.status_code >= 400:
            log = logger.warning

        log(
            "Request completed method=%s path=%s status=%s duration_ms=%.2f",
            request.method,
            path,
            response.status_code,
            duration_ms,
        )
        return response
