"""Full Stack Engineer Agent.

`09_MVP_Roadmap.md` has this role temporarily represent Frontend, Backend, and
Database engineering: "This allows the platform to validate engineering
coordination before introducing additional specialization." The three specialists
arrive in V2 per `11_Future_Roadmap.md`.

Per ADR-0006 the output is an **inspectable repository scaffold** — real files a
reviewer can read, traced to the architecture and requirements that justify them
— not a runnable application. `13_Demo_and_Pitch.md` Step 6 asks for generated
structure to be displayed, which is what this produces.
"""

from __future__ import annotations

from pydantic import Field

from app.agents.base import BaseAgent
from app.agents.contracts import AgentOutput, ArtifactDraft
from app.agents.models import SourceFile
from app.agents.rendering import bullets, code_block, heading, paragraph, sections, table
from app.domain.artifacts import ArtifactType
from app.domain.lifecycle import AgentRole, LifecycleStage
from app.memory.context_builder import ProjectContext

#: Files are written as individual artifacts so each carries its own traceability
#: and version history. Beyond this many, the Development Center becomes a wall
#: of files rather than a readable scaffold, and the token cost stops paying for
#: itself.
MAX_SOURCE_FILES = 12


class FullStackEngineerOutput(AgentOutput):
    """What the Full Stack Engineer produces."""

    repository_tree: list[str] = Field(
        default_factory=list,
        description="Every path in the proposed repository, directories included.",
    )
    stack_summary: str = Field(
        description="How the approved technology decisions map onto this layout."
    )
    files: list[SourceFile] = Field(
        default_factory=list,
        description=(
            "Key files, written in full. Choose the ones that carry the design: "
            "domain models, schema, primary API surface, a representative UI "
            "component. Not boilerplate a reader can infer."
        ),
    )
    not_implemented: list[str] = Field(
        default_factory=list,
        description=(
            "What this scaffold deliberately does not include. Stated so a "
            "reviewer is never misled about how complete the output is."
        ),
    )


class FullStackEngineerAgent(BaseAgent[FullStackEngineerOutput]):
    """Produces the repository scaffold from an approved plan."""

    role = AgentRole.FULL_STACK_ENGINEER
    stage = LifecycleStage.IMPLEMENTATION
    output_model = FullStackEngineerOutput
    prompt_name = "full_stack_engineer"

    def build_task(self, context: ProjectContext) -> str:
        return (
            f"Produce the repository scaffold for **{context.project_name}**.\n\n"
            "Use exactly the technologies the approved technology decisions "
            "name — this is not the place to revisit them. Lay out the "
            "repository to match the approved architecture's components.\n\n"
            f"Write at most {MAX_SOURCE_FILES} files, in full, choosing the ones "
            "that carry the design: the data model, the schema, the primary API "
            "surface, one representative UI component. Skip boilerplate a reader "
            "can infer.\n\n"
            "Be explicit in `not_implemented` about what this scaffold leaves "
            "out. The organization does not claim the generated project runs, "
            "and overstating it would be worse than the gap itself."
        )

    def compose_artifacts(
        self, output: FullStackEngineerOutput, context: ProjectContext
    ) -> list[ArtifactDraft]:
        links = self._links(output)
        files = output.files[:MAX_SOURCE_FILES]

        structure = sections(
            heading(f"Repository Structure — {context.project_name}"),
            heading("Stack", 2),
            paragraph(output.stack_summary),
            heading("Layout", 2),
            code_block("\n".join(output.repository_tree) or "(empty)"),
            heading("Files written in full", 2),
            table(
                ["Path", "Language", "Purpose"],
                [[file.path, file.language, file.purpose] for file in files],
            ),
            heading("Not implemented", 2),
            paragraph(
                "This is an inspectable scaffold, not a running application. "
                "The following is deliberately absent:"
            ),
            bullets(output.not_implemented),
        )

        drafts = [
            ArtifactDraft(
                type=ArtifactType.REPOSITORY_STRUCTURE,
                title=f"Repository Structure — {context.project_name}",
                body_markdown=structure,
                content={
                    "tree": output.repository_tree,
                    "files": [file.path for file in files],
                    "not_implemented": output.not_implemented,
                },
                summary=f"{len(output.repository_tree)} paths, {len(files)} files written",
                derived_from=links,
            )
        ]

        drafts.extend(
            ArtifactDraft(
                type=ArtifactType.SOURCE_FILE,
                title=file.path,
                body_markdown=sections(
                    heading(file.path),
                    paragraph(file.purpose),
                    code_block(file.content, file.language),
                ),
                content={
                    "path": file.path,
                    "language": file.language,
                    "content": file.content,
                },
                summary=file.purpose[:200],
                derived_from=links,
            )
            for file in files
        )

        return drafts
