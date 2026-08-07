"""Dependency injection container.

Components register against a *protocol* and resolve by that protocol, never by
concrete type. That indirection is what makes the roadmap's swap points real
rather than aspirational: the Anthropic provider can be exchanged for Gemini or
the fixture replayer, and the SQL memory repository for any other implementation,
without a single call site changing.

Deliberately small. A full IoC framework would add magic and a dependency for
behaviour that fits in a hundred lines, and FastAPI already owns request-scoped
injection — this container owns *application*-scoped wiring.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, TypeVar

from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class ContainerError(RuntimeError):
    """Raised when a dependency is resolved that was never registered."""


class Container:
    """Application-scoped registry of protocol implementations.

    Two lifetimes are supported:

    - **singleton** — one instance for the process. The default, and correct for
      stateless collaborators (providers, repositories, buses).
    - **factory** — a fresh instance per resolution, for anything holding
      per-use mutable state.
    """

    def __init__(self) -> None:
        self._factories: dict[type, Callable[[], Any]] = {}
        self._singletons: dict[type, Any] = {}
        self._singleton_keys: set[type] = set()

    def register_singleton(self, protocol: type[T], factory: Callable[[], T]) -> None:
        """Register a lazily-constructed, cached implementation.

        The factory runs on first resolution rather than at registration, so
        startup does not pay for components a given process never uses.
        """
        self._factories[protocol] = factory
        self._singleton_keys.add(protocol)
        logger.debug("Registered singleton", extra={"protocol": protocol.__name__})

    def register_instance(self, protocol: type[T], instance: T) -> None:
        """Register an already-constructed implementation."""
        self._singletons[protocol] = instance
        self._singleton_keys.add(protocol)
        logger.debug("Registered instance", extra={"protocol": protocol.__name__})

    def register_factory(self, protocol: type[T], factory: Callable[[], T]) -> None:
        """Register an implementation constructed fresh on every resolution."""
        self._factories[protocol] = factory
        self._singleton_keys.discard(protocol)
        logger.debug("Registered factory", extra={"protocol": protocol.__name__})

    def resolve(self, protocol: type[T]) -> T:
        """Return the implementation registered for ``protocol``.

        Raises:
            ContainerError: if nothing is registered. Failing loudly at the call
                site beats silently handing back ``None`` and failing later.
        """
        if protocol in self._singletons:
            return self._singletons[protocol]  # type: ignore[no-any-return]

        factory = self._factories.get(protocol)
        if factory is None:
            raise ContainerError(
                f"No implementation registered for {protocol.__name__}. "
                "Register it in app.core.bootstrap before resolving."
            )

        instance = factory()
        if protocol in self._singleton_keys:
            self._singletons[protocol] = instance
        return instance  # type: ignore[no-any-return]

    def has(self, protocol: type) -> bool:
        """Return whether ``protocol`` has an implementation registered."""
        return protocol in self._singletons or protocol in self._factories

    async def aclose(self) -> None:
        """Dispose every instantiated singleton that exposes a close hook.

        Called on application shutdown so database engines, HTTP clients, and
        provider sessions are released deterministically instead of at GC time.
        """
        for protocol, instance in self._singletons.items():
            closer = getattr(instance, "aclose", None) or getattr(instance, "close", None)
            if closer is None:
                continue
            try:
                result = closer()
                if inspect.isawaitable(result):
                    await result
            # Broad by design: shutdown is best-effort, and one failing disposer
            # must not prevent the remaining singletons from being released.
            except Exception:
                logger.exception(
                    "Failed to close dependency", extra={"protocol": protocol.__name__}
                )

        self._singletons.clear()

    def clear(self) -> None:
        """Reset all registrations. Used by tests to isolate wiring."""
        self._factories.clear()
        self._singletons.clear()
        self._singleton_keys.clear()
