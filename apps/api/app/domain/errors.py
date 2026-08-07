"""Domain-level error hierarchy.

This module is deliberately free of any framework, transport, or persistence
concern. Domain code raises these errors to describe *what went wrong in the
engineering domain*; the transport layer (``app.core.errors``) is solely
responsible for deciding how each one is represented over HTTP.

Keeping the two separate is what allows the orchestration and agent layers to be
exercised in tests, in a CLI, or inside a background worker without dragging
FastAPI into the domain.
"""

from __future__ import annotations

from typing import Any


class VictoriousError(Exception):
    """Base class for every error raised by Project Victorious domain code.

    Attributes:
        message: Human-readable description, safe to surface to an operator.
        code: Stable, machine-readable identifier. Clients switch on this rather
            than on message text, so it must not change once released.
        details: Structured context for debugging and for the Approval Center to
            render *why* something failed. Must never contain secrets.
    """

    code: str = "victorious_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class NotFoundError(VictoriousError):
    """A requested entity does not exist in the shared organizational memory."""

    code = "not_found"


class ValidationError(VictoriousError):
    """Input violated a domain invariant.

    Distinct from a request-schema failure, which never reaches the domain.
    """

    code = "validation_error"


class ConflictError(VictoriousError):
    """The requested change conflicts with the current state of the project.

    Raised, for example, when two engineering agents produce contradictory
    artifacts for the same lifecycle stage, or when an artifact version is
    superseded concurrently.
    """

    code = "conflict"


class DependencyNotSatisfiedError(VictoriousError):
    """An engineering stage or agent was invoked before its inputs were ready.

    The Executive AI relies on this to enforce lifecycle ordering rather than
    letting an agent reason over incomplete upstream context.
    """

    code = "dependency_not_satisfied"


class ApprovalRequiredError(VictoriousError):
    """A human approval gate blocks the requested transition.

    Surfaces the human-in-the-loop guarantee as a first-class domain outcome
    instead of an implicit branch inside the orchestrator.
    """

    code = "approval_required"


class ProviderError(VictoriousError):
    """An external provider (LLM, vector store, cache) failed.

    Wrapping provider faults in a domain error keeps retry, fallback, and
    degradation policy decisions inside the platform rather than leaking a
    vendor SDK exception into orchestration code.
    """

    code = "provider_error"
