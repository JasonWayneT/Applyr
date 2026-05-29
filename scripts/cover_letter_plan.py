"""Cover letter plan schema (CR-024 / FR-098)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CoverProofSlot:
    claim_id: str
    lens: str
    jd_need: str
    employer: str
    project_id: str = ""


@dataclass
class CoverLetterPlan:
    company_display: str
    role_title: str
    ranked_needs: List[str] = field(default_factory=list)
    match_thesis: str = ""
    interest_via_match: str = ""
    opening_variant: str = "problem_first"
    proofs: List[CoverProofSlot] = field(default_factory=list)
    archetype_id: str = "standard"
    jd_goal: str = ""
    research_hook: Optional[str] = None
    theme_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["proofs"] = [asdict(p) for p in self.proofs]
        return d
