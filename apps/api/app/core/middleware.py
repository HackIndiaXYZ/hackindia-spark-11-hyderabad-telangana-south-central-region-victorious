"""HTTP middleware.

Correlation IDs are established here, at the outermost layer, so every log line
emitted while handling a request — including those from agents invoked deep in
the orchestration graph — carries the same identifier.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import correlation_context, get_logger

logger = get_logger(__name__)

CORRELATION_HEADER = "X-Correlation-ID"

# Probe endpoints are polled continuously; logging them buries real traffic.
_UNLOGGED_PATHS = frozenset({"/health", "/health/live", "/health/ready"})


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Bind a correlation ID to the request context and echo it to the client.

    An inbound ``X-Correlation-ID`` is honoured so a trace can span the browser,
    the API, and any downstream service; otherwise one is generated.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        inbound = request.headers.get(CORRELATION_HEADER)

        with correlation_context(inbound) as correlation_id:
            request.state.correlation_id = correlation_id
            response = await call_next(request)
            response.headers[CORRELATION_HEADER] = correlation_id
            return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Emit one structured line per request with method, path, status, duration."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in _UNLOGGED_PATHS:
            return await call_next(request)

        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000

        logger.info(
            "%s %s -> %s",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "http_method": request.method,
                "http_path": request.url.path,
                "http_status": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return response
