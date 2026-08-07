"""Retry policy for provider calls.

Implemented here rather than per adapter so every provider degrades identically,
and so the policy is one auditable thing rather than three.

Two failure classes are distinguished deliberately:

- **Transport failures** (rate limits, timeouts, 5xx) are transient. Retrying the
  identical request is correct.
- **Schema violations** — valid transport, output that will not validate — are
  not transient. Retrying the identical request repeats the same mistake, so the
  caller supplies a corrected request carrying the validation error, giving the
  model the information it needs to do better.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

from app.core.logging import get_logger
from app.domain.errors import ProviderError

logger = get_logger(__name__)

_BASE_DELAY_SECONDS = 0.5
_MAX_DELAY_SECONDS = 8.0


class TransientProviderError(ProviderError):
    """A provider failure worth retrying unchanged."""

    code = "provider_transient_error"


class SchemaViolationError(ProviderError):
    """Provider output could not be validated against the requested schema."""

    code = "provider_schema_violation"


def backoff_delay(attempt: int) -> float:
    """Return the delay before ``attempt`` (0-based), with jitter.

    Jitter matters under concurrency: seven agents retrying on the same schedule
    would resynchronise into a thundering herd against the same rate limit.
    """
    delay: float = min(_BASE_DELAY_SECONDS * float(2**attempt), _MAX_DELAY_SECONDS)
    jitter: float = 0.5 + random.random() / 2  # noqa: S311 - jitter, not crypto
    return delay * jitter


async def with_retries[R](
    operation: Callable[[int], Awaitable[R]],
    *,
    max_retries: int,
    description: str,
) -> R:
    """Run ``operation`` until it succeeds or retries are exhausted.

    Args:
        operation: Receives the 0-based attempt number, so a caller can vary the
            request between attempts — which is how schema violations are
            corrected rather than merely repeated.
        max_retries: Additional attempts after the first.
        description: Included in logs and in the final error.

    Returns:
        The operation's result.

    Raises:
        ProviderError: when every attempt fails. The last failure is the cause.
    """
    last_error: ProviderError | None = None

    for attempt in range(max_retries + 1):
        try:
            return await operation(attempt)
        except (TransientProviderError, SchemaViolationError) as exc:
            last_error = exc

            if attempt == max_retries:
                break

            delay = backoff_delay(attempt)
            logger.warning(
                "Provider call failed, retrying",
                extra={
                    "operation": description,
                    "attempt": attempt + 1,
                    "max_attempts": max_retries + 1,
                    "delay_seconds": round(delay, 2),
                    "error_code": exc.code,
                },
            )
            await asyncio.sleep(delay)

    raise ProviderError(
        f"{description} failed after {max_retries + 1} attempts",
        details={
            "attempts": max_retries + 1,
            "last_error": last_error.message if last_error else "unknown",
        },
    )
