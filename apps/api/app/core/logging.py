"""Structured logging with request correlation.

Every log line carries a ``correlation_id`` that ties it to the originating HTTP
request. Once the orchestration layer lands in Milestone 3, the same identifier
propagates through agent runs, so a single engineering decision can be traced
from the API call that triggered it through every agent that contributed to it.

That property is the logging half of the traceability guarantee the platform is
built around; the data half lives in the memory model.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from app.core.config import ObservabilitySettings

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)

# Attributes present on every LogRecord. Anything outside this set was supplied
# by the caller via ``extra=`` and is therefore promoted into the JSON payload.
_RESERVED_ATTRS = frozenset(
    {
        "args", "asctime", "created", "exc_info", "exc_text", "filename",
        "funcName", "levelname", "levelno", "lineno", "module", "msecs",
        "message", "msg", "name", "pathname", "process", "processName",
        "relativeCreated", "stack_info", "thread", "threadName", "taskName",
    }
)


def get_correlation_id() -> str | None:
    """Return the correlation ID bound to the current context, if any."""
    return _correlation_id.get()


@contextmanager
def correlation_context(correlation_id: str | None = None) -> Iterator[str]:
    """Bind a correlation ID for the duration of the block.

    Generates one when not supplied, so background work started outside a request
    is still traceable.
    """
    resolved = correlation_id or str(uuid.uuid4())
    token = _correlation_id.set(resolved)
    try:
        yield resolved
    finally:
        _correlation_id.reset(token)


class JSONFormatter(logging.Formatter):
    """Render records as single-line JSON for log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if correlation_id := get_correlation_id():
            payload["correlation_id"] = correlation_id

        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable output for local development."""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname:<8} {record.name:<28} {record.getMessage()}"
        if correlation_id := get_correlation_id():
            base = f"[{correlation_id[:8]}] {base}"
        if record.exc_info:
            base = f"{base}\n{self.formatException(record.exc_info)}"
        return base


def configure_logging(settings: ObservabilitySettings) -> None:
    """Install the root logging configuration.

    Idempotent: existing handlers are replaced, so repeated calls in tests or
    under a reloading server do not duplicate output.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter() if settings.json_logs else ConsoleFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level)

    # Uvicorn installs its own handlers; defer to ours so every line is structured.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger. Preferred over ``logging.getLogger``."""
    return logging.getLogger(name)
