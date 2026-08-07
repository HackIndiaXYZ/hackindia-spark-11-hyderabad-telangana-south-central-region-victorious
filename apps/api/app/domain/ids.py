"""Prefixed entity identifiers.

Identifiers carry a type prefix (``art_9f2c…``, ``run_41ab…``). Two reasons:

1. A traceability graph rendered in the UI, a log line, and an API response all
   become self-describing — you can tell an artifact from an agent run without
   consulting a schema.
2. Passing an agent-run ID where an artifact ID belongs is caught by inspection
   rather than by a confusing empty result.

Random rather than sequential: identifiers appear in URLs, and sequential IDs
would leak how many projects exist.
"""

from __future__ import annotations

import uuid
from enum import StrEnum


class IdPrefix(StrEnum):
    """Type prefixes for every persisted entity."""

    PROJECT = "prj"
    ARTIFACT = "art"
    VERSION = "ver"
    AGENT_RUN = "run"
    TRACE_EDGE = "edg"
    APPROVAL = "apr"
    EVENT = "evt"
    REVIEW = "rev"
    TASK = "tsk"


def new_id(prefix: IdPrefix) -> str:
    """Mint a new identifier for the given entity type."""
    return f"{prefix.value}_{uuid.uuid4().hex}"


def prefix_of(identifier: str) -> str | None:
    """Return the type prefix of an identifier, or ``None`` if malformed."""
    head, separator, _ = identifier.partition("_")
    return head if separator else None


def is_id_of(identifier: str, prefix: IdPrefix) -> bool:
    """Return whether ``identifier`` denotes an entity of the given type."""
    return prefix_of(identifier) == prefix.value
