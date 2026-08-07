"""Prompt loading and rendering.

Prompts live as markdown files under ``app/agents/prompts/`` rather than as
string literals in code. They are the specification an agent reasons from, so
they belong in version control as reviewable text with their own diff history —
a prompt change is an engineering change, and burying it in a Python string
hides it in code review.
"""

from __future__ import annotations

import string
from functools import lru_cache
from pathlib import Path

from app.domain.errors import VictoriousError

PROMPT_DIR = Path(__file__).parent / "prompts"


class PromptError(VictoriousError):
    """A prompt template is missing or was rendered with incomplete variables."""

    code = "prompt_error"


class _StrictTemplate(string.Template):
    """``$name`` substitution that refuses to silently leave placeholders unfilled.

    Standard ``format`` would collide with the braces in JSON examples and code
    blocks that prompts routinely contain; ``$``-substitution does not.
    """

    idpattern = r"[a-z][a-z0-9_]*"


@lru_cache(maxsize=64)
def load_prompt(name: str) -> str:
    """Load a prompt template by filename stem.

    Cached: templates are immutable for the lifetime of the process, and every
    agent invocation would otherwise re-read from disk.

    Raises:
        PromptError: if no such template exists.
    """
    path = PROMPT_DIR / f"{name}.md"

    if not path.is_file():
        available = sorted(p.stem for p in PROMPT_DIR.glob("*.md"))
        raise PromptError(
            f"Prompt template '{name}' not found",
            details={"available": available, "directory": str(PROMPT_DIR)},
        )

    return path.read_text(encoding="utf-8")


def render_prompt(name: str, **variables: str) -> str:
    """Render a template with the given variables.

    Raises:
        PromptError: if the template references a variable that was not supplied.
            Failing loudly matters — an unsubstituted ``$context`` reaching a
            model produces a plausible-looking answer to the wrong question,
            which is far harder to diagnose than a startup error.
    """
    template = _StrictTemplate(load_prompt(name))

    try:
        return template.substitute(**variables)
    except KeyError as exc:
        raise PromptError(
            f"Prompt '{name}' requires a variable that was not supplied",
            details={"missing": str(exc).strip("'"), "supplied": sorted(variables)},
        ) from exc


def available_prompts() -> list[str]:
    """Return every template name on disk. Used by diagnostics and tests."""
    return sorted(path.stem for path in PROMPT_DIR.glob("*.md"))
