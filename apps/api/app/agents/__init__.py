"""The AI engineering organization.

One module per engineering specialist, each a subclass of :class:`BaseAgent` with
its own typed output contract and its own versioned prompt. Eight agents fill the
seven MVP roles from `09_MVP_Roadmap.md`; see :mod:`app.agents.organization`.
"""

from app.agents.base import BaseAgent
from app.agents.business_analyst import BusinessAnalystAgent, BusinessAnalystOutput
from app.agents.contracts import (
    AgentOutput,
    AgentResult,
    ArtifactDraft,
    TraceLink,
)
from app.agents.documentation import (
    DeploymentPreparationAgent,
    DeploymentPreparationOutput,
    DocumentationAgent,
    DocumentationOutput,
)
from app.agents.full_stack_engineer import (
    FullStackEngineerAgent,
    FullStackEngineerOutput,
)
from app.agents.organization import AGENT_CLASSES, build_organization
from app.agents.product_manager import ProductManagerAgent, ProductManagerOutput
from app.agents.prompts import PromptError, available_prompts, load_prompt, render_prompt
from app.agents.qa_engineer import QAEngineerAgent, QAEngineerOutput
from app.agents.software_architect import (
    ArchitectOutput,
    ImplementationPlannerAgent,
    ImplementationPlanOutput,
    SoftwareArchitectAgent,
)

__all__ = [
    "AGENT_CLASSES",
    "AgentOutput",
    "AgentResult",
    "ArchitectOutput",
    "ArtifactDraft",
    "BaseAgent",
    "BusinessAnalystAgent",
    "BusinessAnalystOutput",
    "DeploymentPreparationAgent",
    "DeploymentPreparationOutput",
    "DocumentationAgent",
    "DocumentationOutput",
    "FullStackEngineerAgent",
    "FullStackEngineerOutput",
    "ImplementationPlanOutput",
    "ImplementationPlannerAgent",
    "ProductManagerAgent",
    "ProductManagerOutput",
    "PromptError",
    "QAEngineerAgent",
    "QAEngineerOutput",
    "SoftwareArchitectAgent",
    "TraceLink",
    "available_prompts",
    "build_organization",
    "load_prompt",
    "render_prompt",
]
