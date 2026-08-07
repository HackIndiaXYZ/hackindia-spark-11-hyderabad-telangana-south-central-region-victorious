"""HTTP error envelope and exception handlers.

This module is the *only* place that knows how a domain error becomes an HTTP
response. Domain and orchestration code raises ``VictoriousError`` subclasses and
stays entirely unaware of status codes.

Every error response shares one shape, so the frontend needs a single error
renderer rather than per-endpoint handling:

    {
      "error": {
        "code": "dependency_not_satisfied",
        "message": "Architecture stage requires approved requirements",
        "details": {"missing": ["requirements"]},
        "correlation_id": "3f9a..."
      }
    }
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_correlation_id, get_logger
from app.domain.errors import (
    ApprovalRequiredError,
    ConflictError,
    DependencyNotSatisfiedError,
    NotFoundError,
    ProviderError,
    ValidationError,
    VictoriousError,
)

logger = get_logger(__name__)

# Single source of truth for domain-error -> HTTP-status mapping. Adding a new
# domain error without an entry here yields 500, which is the correct default:
# an unmapped error is a genuine oversight, not something to guess at.
_STATUS_BY_ERROR: dict[type[VictoriousError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ConflictError: status.HTTP_409_CONFLICT,
    DependencyNotSatisfiedError: status.HTTP_409_CONFLICT,
    ApprovalRequiredError: status.HTTP_403_FORBIDDEN,
    ProviderError: status.HTTP_502_BAD_GATEWAY,
}


class ErrorDetail(BaseModel):
    """Body of an error response."""

    code: str = Field(description="Stable machine-readable error identifier.")
    message: str = Field(description="Human-readable description.")
    details: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = Field(
        default=None,
        description="Ties this response to the server logs for the same request.",
    )


class ErrorResponse(BaseModel):
    """Envelope returned for every non-2xx response."""

    error: ErrorDetail


def _render(status_code: int, detail: ErrorDetail) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(ErrorResponse(error=detail)),
    )


def _status_for(exc: VictoriousError) -> int:
    """Resolve a status code, honouring subclass relationships."""
    for error_type, code in _STATUS_BY_ERROR.items():
        if isinstance(exc, error_type):
            return code
    return status.HTTP_500_INTERNAL_SERVER_ERROR


async def _handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, VictoriousError)  # noqa: S101 - handler registered by type
    status_code = _status_for(exc)

    # 5xx means the platform misbehaved and deserves a stack trace; 4xx is the
    # caller's problem and would only add noise at error level.
    log = logger.exception if status_code >= 500 else logger.warning
    log(
        "Request failed: %s",
        exc.code,
        extra={"path": request.url.path, "error_code": exc.code, "status_code": status_code},
    )

    return _render(
        status_code,
        ErrorDetail(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            correlation_id=get_correlation_id(),
        ),
    )


async def _handle_request_validation(request: Request, exc: Exception) -> JSONResponse:
    """Reshape FastAPI's validation errors into the common envelope."""
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    return _render(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        ErrorDetail(
            code="request_validation_error",
            message="The request payload failed validation.",
            details={"errors": jsonable_encoder(exc.errors())},
            correlation_id=get_correlation_id(),
        ),
    )


async def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    """Wrap Starlette's built-in HTTP errors (404 routing, 405, ...)."""
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    return _render(
        exc.status_code,
        ErrorDetail(
            code=f"http_{exc.status_code}",
            message=str(exc.detail),
            correlation_id=get_correlation_id(),
        ),
    )


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler.

    The exception message is deliberately withheld from the client — it may carry
    internal detail — while the correlation ID gives an operator an exact path to
    the logged stack trace.
    """
    logger.exception(
        "Unhandled exception", extra={"path": request.url.path, "error_type": type(exc).__name__}
    )
    return _render(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorDetail(
            code="internal_error",
            message="An unexpected error occurred.",
            correlation_id=get_correlation_id(),
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Wire every handler onto the application."""
    app.add_exception_handler(VictoriousError, _handle_domain_error)
    app.add_exception_handler(RequestValidationError, _handle_request_validation)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected)
