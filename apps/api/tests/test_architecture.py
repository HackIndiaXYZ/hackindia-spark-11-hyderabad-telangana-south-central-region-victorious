"""Executable architecture rules.

`15_Development_Guidelines.md` requires clean architecture and warns that
architectural quality must never be sacrificed for implementation speed. A
document cannot enforce that; a test can.

These tests parse the source tree and fail the build when a layering rule is
violated, so the boundary holds under time pressure instead of eroding quietly.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parent.parent / "app"

# Dependencies point inward. Each layer may import only from itself, the layers
# beneath it, and `core` (cross-cutting infrastructure). `domain` sits innermost
# and may import nothing internal at all.
_FORBIDDEN_IMPORTS: dict[str, tuple[str, ...]] = {
    "domain": ("app.core", "app.api", "app.db", "app.llm", "app.memory",
               "app.agents", "app.orchestration", "app.events"),
    "db": ("app.api", "app.memory", "app.llm", "app.agents", "app.orchestration",
           "app.events"),
    "memory": ("app.api", "app.agents", "app.orchestration"),
    "events": ("app.api", "app.agents", "app.orchestration", "app.llm"),
    "llm": ("app.api", "app.agents", "app.orchestration", "app.memory"),
    "agents": ("app.api", "app.orchestration"),
    "orchestration": ("app.api",),
}

# `domain` must also stay free of frameworks so it can run without I/O.
_FORBIDDEN_THIRD_PARTY_IN_DOMAIN = (
    "fastapi", "starlette", "sqlalchemy", "anthropic", "google",
    "langgraph", "chromadb", "redis", "httpx", "uvicorn",
)


def _iter_modules(layer: str) -> list[Path]:
    """Return every Python module in a layer, or an empty list if absent.

    Layers arrive in later milestones; a rule for a layer that does not exist yet
    is simply inert rather than an error.
    """
    layer_path = APP_ROOT / layer
    if not layer_path.is_dir():
        return []
    return sorted(layer_path.rglob("*.py"))


def _imported_roots(module_path: Path) -> set[str]:
    """Return every module path imported by ``module_path``.

    Uses the AST rather than importing, so the check is static and cannot be
    defeated by import-time side effects.
    """
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    imported: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module)

    return imported


@pytest.mark.parametrize("layer", sorted(_FORBIDDEN_IMPORTS))
def test_layer_does_not_import_outward(layer: str) -> None:
    """No layer may depend on a layer above it."""
    forbidden = _FORBIDDEN_IMPORTS[layer]
    violations: list[str] = []

    for module_path in _iter_modules(layer):
        for imported in _imported_roots(module_path):
            for banned in forbidden:
                if imported == banned or imported.startswith(f"{banned}."):
                    relative = module_path.relative_to(APP_ROOT.parent)
                    violations.append(f"{relative} imports {imported}")

    assert not violations, (
        f"Layer '{layer}' violates inward-dependency rule:\n  " + "\n  ".join(violations)
    )


def test_domain_is_framework_free() -> None:
    """The domain layer must not depend on any framework or client library."""
    violations: list[str] = []

    for module_path in _iter_modules("domain"):
        for imported in _imported_roots(module_path):
            root = imported.split(".")[0]
            if root in _FORBIDDEN_THIRD_PARTY_IN_DOMAIN:
                relative = module_path.relative_to(APP_ROOT.parent)
                violations.append(f"{relative} imports {imported}")

    assert not violations, (
        "Domain layer must stay framework-free:\n  " + "\n  ".join(violations)
    )


def test_domain_layer_exists_and_is_populated() -> None:
    """Guard against the rules above passing vacuously on an empty domain."""
    modules = _iter_modules("domain")
    assert modules, "app/domain must exist — it is the innermost architectural layer"
    assert any(m.name != "__init__.py" for m in modules), "app/domain contains no modules"


def test_composition_root_is_the_only_wiring_point() -> None:
    """Only ``bootstrap`` may construct the container.

    Keeps implementation choices in one auditable file rather than scattered
    across the codebase.
    """
    violations: list[str] = []

    for module_path in APP_ROOT.rglob("*.py"):
        if module_path.name in {"bootstrap.py", "container.py"}:
            continue
        source = module_path.read_text(encoding="utf-8")
        if "Container()" in source:
            violations.append(str(module_path.relative_to(APP_ROOT.parent)))

    assert not violations, (
        "Container must only be constructed in app/core/bootstrap.py, found in:\n  "
        + "\n  ".join(violations)
    )
