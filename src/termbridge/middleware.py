import logging
import time
from collections.abc import AsyncIterator

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import Message

logger = logging.getLogger(__name__)
BODY_LOG_LIMIT = 1024


def _full_path(request: Request) -> str:
    path = request.url.path
    if request.url.query:
        path = f"{path}?{request.url.query}"
    return path


def _is_json_content_type(content_type: str) -> bool:
    media_type = content_type.split(";", maxsplit=1)[0].strip().lower()
    return media_type == "application/json" or media_type.endswith("+json")


def _truncate_body(body: str) -> str:
    return body[:BODY_LOG_LIMIT]


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def _try_get_request_body(self, request: Request) -> str | None:
        if request.method == "GET" or not _is_json_content_type(request.headers.get("content-type", "")):
            return None

        try:
            body_bytes = await request.body()
            if not body_bytes:
                return None

            async def receive() -> Message:
                return {"type": "http.request", "body": body_bytes}

            request._receive = receive
            return body_bytes.decode("utf-8", errors="replace")
        except Exception as exc:
            logger.warning("Request body read failed error=%s", exc)
            return None

    async def _try_get_response_body(self, response: Response) -> str | None:
        if not _is_json_content_type(response.headers.get("content-type", "")):
            return None

        try:
            body = b""
            async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                body += chunk
            if not body:
                return None

            async def restore() -> AsyncIterator[bytes]:
                yield body

            response.body_iterator = restore()  # type: ignore[attr-defined]
            return body.decode("utf-8", errors="replace")
        except Exception as exc:
            logger.warning("Response body read failed error=%s", exc)
            return None

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        path = _full_path(request)

        logger.info("Request begin method=%s path=%s", request.method, path)
        request_body = await self._try_get_request_body(request)
        if request_body:
            logger.info("Request body=%s", _truncate_body(request_body))

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
            response = JSONResponse(
                status_code=500,
                content={"code": "internal_error", "error": "Internal server error"},
            )

        duration_ms = (time.perf_counter() - started) * 1000
        log = logger.info
        if response.status_code >= 500:
            log = logger.error
        elif response.status_code >= 400:
            log = logger.warning

        response_body = await self._try_get_response_body(response)
        log(
            "Request end method=%s path=%s status=%s duration_ms=%.2f",
            request.method,
            path,
            response.status_code,
            duration_ms,
        )
        if response_body:
            log("Response body=%s", _truncate_body(response_body))
        return response
