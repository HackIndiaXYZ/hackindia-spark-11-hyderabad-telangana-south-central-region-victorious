"""Error envelope and domain-to-HTTP mapping."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.errors import register_exception_handlers
from app.domain.errors import (
    ApprovalRequiredError,
    ConflictError,
    DependencyNotSatisfiedError,
    NotFoundError,
    ProviderError,
    ValidationError,
    VictoriousError,
)


@pytest.fixture
def error_app() -> FastAPI:
    """Minimal app whose only job is to raise a chosen error."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/raise/{error_name}")
    async def raise_error(error_name: str) -> None:
        errors: dict[str, VictoriousError] = {
            "not_found": NotFoundError("Project not found", details={"id": "p-1"}),
            "validation": ValidationError("Priority must be one of MUST/SHOULD/COULD"),
            "conflict": ConflictError("Artifact was superseded concurrently"),
            "dependency": DependencyNotSatisfiedError(
                "Architecture requires approved requirements",
                details={"missing": ["requirements"]},
            ),
            "approval": ApprovalRequiredError("Technology selection needs sign-off"),
            "provider": ProviderError("Upstream model unavailable"),
            "unexpected": None,  # type: ignore[dict-item]
        }
        if error_name == "unexpected":
            raise RuntimeError("boom")
        raise errors[error_name]

    return app


@pytest.fixture
async def error_client(error_app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=error_app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.parametrize(
    ("path", "expected_status", "expected_code"),
    [
        ("not_found", 404, "not_found"),
        ("validation", 422, "validation_error"),
        ("conflict", 409, "conflict"),
        ("dependency", 409, "dependency_not_satisfied"),
        ("approval", 403, "approval_required"),
        ("provider", 502, "provider_error"),
    ],
)
async def test_domain_errors_map_to_expected_status(
    error_client: AsyncClient, path: str, expected_status: int, expected_code: str
) -> None:
    response = await error_client.get(f"/raise/{path}")

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code


async def test_error_details_are_preserved(error_client: AsyncClient) -> None:
    """Structured detail must survive to the client — the UI renders it."""
    response = await error_client.get("/raise/dependency")

    assert response.json()["error"]["details"] == {"missing": ["requirements"]}


async def test_unexpected_errors_do_not_leak_internals(
    error_client: AsyncClient,
) -> None:
    """A bare exception must not expose its message to the caller."""
    response = await error_client.get("/raise/unexpected")

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert "boom" not in error["message"]


async def test_routing_404_uses_the_same_envelope(error_client: AsyncClient) -> None:
    """Every non-2xx response shares one shape, including framework errors."""
    response = await error_client.get("/no-such-route")

    assert response.status_code == 404
    assert "error" in response.json()
    assert response.json()["error"]["code"] == "http_404"
