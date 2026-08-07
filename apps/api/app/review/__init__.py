"""Engineering review layer.

Reviews every artifact the organization produces: a deterministic structural
score, optionally sharpened by a bounded model judgement.

Sits beside ``app.agents`` and below ``app.orchestration``. It imports memory,
llm, domain, and core — and nothing from Mutagent. Helix specifies, evaluates,
and optimizes this reviewer at development time; `07_System_Architecture.md`
keeps Mutagent out of the runtime execution path, and
``tests/test_architecture.py`` enforces that.
"""

from app.review.checks import CheckResult, is_first_stage, run_checks
from app.review.reviewer import MAX_ADJUSTMENT, EngineeringReviewer, ReviewJudgement

__all__ = [
    "MAX_ADJUSTMENT",
    "CheckResult",
    "EngineeringReviewer",
    "ReviewJudgement",
    "is_first_stage",
    "run_checks",
]
