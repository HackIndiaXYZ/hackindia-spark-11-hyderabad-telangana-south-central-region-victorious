"""Pure domain layer — the innermost ring of the architecture.

Holds the vocabulary of the engineering organization: artifacts, lifecycle
stages, traceability edges, agent contracts, approvals, and the errors that
describe engineering failures.

This package must remain free of frameworks, I/O, and persistence. Anything here
can be exercised without a database, a network, or an event loop, which is what
makes the orchestration rules testable in isolation.

Enforced by ``tests/test_architecture.py``.
"""

from app.domain.errors import (
    ApprovalRequiredError,
    ConflictError,
    DependencyNotSatisfiedError,
    NotFoundError,
    ProviderError,
    ValidationError,
    VictoriousError,
)

__all__ = [
    "ApprovalRequiredError",
    "ConflictError",
    "DependencyNotSatisfiedError",
    "NotFoundError",
    "ProviderError",
    "ValidationError",
    "VictoriousError",
]
