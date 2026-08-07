"""Dependency injection container behaviour."""

from __future__ import annotations

from typing import Protocol

import pytest

from app.core.container import Container, ContainerError


class Greeter(Protocol):
    def greet(self) -> str: ...


class EnglishGreeter:
    def greet(self) -> str:
        return "hello"


class FrenchGreeter:
    def greet(self) -> str:
        return "bonjour"


def test_resolves_registered_singleton() -> None:
    container = Container()
    container.register_singleton(Greeter, EnglishGreeter)  # type: ignore[type-abstract]

    assert container.resolve(Greeter).greet() == "hello"  # type: ignore[type-abstract]


def test_singleton_returns_the_same_instance() -> None:
    container = Container()
    container.register_singleton(Greeter, EnglishGreeter)  # type: ignore[type-abstract]

    assert container.resolve(Greeter) is container.resolve(Greeter)  # type: ignore[type-abstract]


def test_factory_returns_a_new_instance_each_time() -> None:
    container = Container()
    container.register_factory(Greeter, EnglishGreeter)  # type: ignore[type-abstract]

    assert container.resolve(Greeter) is not container.resolve(Greeter)  # type: ignore[type-abstract]


def test_singleton_factory_is_lazy() -> None:
    """Nothing is constructed until first resolution."""
    constructed = False

    def build() -> EnglishGreeter:
        nonlocal constructed
        constructed = True
        return EnglishGreeter()

    container = Container()
    container.register_singleton(Greeter, build)  # type: ignore[type-abstract]

    assert constructed is False
    container.resolve(Greeter)  # type: ignore[type-abstract]
    assert constructed is True


def test_implementation_can_be_swapped_without_touching_call_sites() -> None:
    """The property the whole architecture depends on.

    Swapping Anthropic for Gemini, or SQL memory for any other store, is exactly
    this operation performed in the composition root.
    """
    container = Container()
    container.register_singleton(Greeter, EnglishGreeter)  # type: ignore[type-abstract]
    assert container.resolve(Greeter).greet() == "hello"  # type: ignore[type-abstract]

    container.clear()
    container.register_singleton(Greeter, FrenchGreeter)  # type: ignore[type-abstract]
    assert container.resolve(Greeter).greet() == "bonjour"  # type: ignore[type-abstract]


def test_resolving_unregistered_protocol_fails_loudly() -> None:
    container = Container()

    with pytest.raises(ContainerError, match="No implementation registered"):
        container.resolve(Greeter)  # type: ignore[type-abstract]


async def test_aclose_disposes_singletons() -> None:
    closed = False

    class Closable:
        async def aclose(self) -> None:
            nonlocal closed
            closed = True

    container = Container()
    container.register_instance(Closable, Closable())

    await container.aclose()

    assert closed is True
    assert container.has(Closable) is False


async def test_aclose_survives_a_failing_disposer() -> None:
    """Shutdown must be best-effort: one bad disposer cannot block the rest."""
    second_closed = False

    class Exploding:
        def close(self) -> None:
            raise RuntimeError("cannot close")

    class Fine:
        def close(self) -> None:
            nonlocal second_closed
            second_closed = True

    container = Container()
    container.register_instance(Exploding, Exploding())
    container.register_instance(Fine, Fine())

    await container.aclose()

    assert second_closed is True
