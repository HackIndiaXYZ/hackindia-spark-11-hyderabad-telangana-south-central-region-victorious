"""Markdown rendering for engineering artifacts.

Artifacts are rendered from an agent's structured output rather than written as
prose by the model. That guarantees the document a human reads and the data a
downstream agent consumes are the same information, and it keeps formatting
consistent across every project the platform builds.

These helpers are deliberately plain: tables, headings, and lists. The output is
read in the workspace and exported into generated repositories, so it must stay
legible as raw text.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def heading(text: str, level: int = 1) -> str:
    return f"{'#' * level} {text}"


def paragraph(text: str) -> str:
    return text.strip()


def bullets(items: Iterable[str]) -> str:
    """Render a bullet list, or an explicit note when empty.

    An empty section says so rather than rendering nothing: a heading with no
    content reads as a formatting bug, while "None identified" is a finding.
    """
    rendered = [f"- {item}" for item in items if item]
    return "\n".join(rendered) if rendered else "_None identified._"


def table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    """Render a markdown table, escaping pipes in cell content.

    Cells accept any value, not just strings: agent contracts hold lists of
    identifiers (``requirement_ids``, ``depends_on``) that read naturally as
    comma-separated cells, and forcing every call site to join them first would
    duplicate that formatting across every agent.
    """
    materialised = [[_cell(value) for value in row] for row in rows]

    if not materialised:
        return "_None identified._"

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in materialised)
    return "\n".join(lines)


def code_block(content: str, language: str = "") -> str:
    """Fence a code block, widening the fence if the content contains one."""
    fence = "```"
    while fence in content:
        fence += "`"
    return f"{fence}{language}\n{content}\n{fence}"


def sections(*parts: str) -> str:
    """Join non-empty sections with blank lines between them."""
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def _cell(value: object) -> str:
    """Flatten a value into one table cell.

    Newlines are replaced rather than escaped: a literal newline inside a cell
    breaks the table row entirely in every markdown renderer.
    """
    text = ", ".join(str(item) for item in value) if isinstance(value, list) else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip() or "—"
