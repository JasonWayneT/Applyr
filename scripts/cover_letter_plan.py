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
    pain_points: List[str] = field(default_factory=list)
    # Epic 3 — pre-selected CL claims with scores
    selected_cl_claims: List[Dict[str, Any]] = field(default_factory=list)
    # Epic 7 — generated hook metadata
    generated_hook: Optional[str] = None
    hook_attempts: int = 0
    # Epic 9 — gap detection metadata
    detected_gaps: List[Dict[str, Any]] = field(default_factory=list)
    gap_acknowledged: bool = False
    # Epic 8 — fast eval metadata
    fast_eval_warning: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["proofs"] = [asdict(p) for p in self.proofs]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoverLetterPlan":
        proofs = [
            CoverProofSlot(**p) if isinstance(p, dict) else p
            for p in (data.get("proofs") or [])
        ]
        return cls(
            company_display=data.get("company_display", ""),
            role_title=data.get("role_title", ""),
            ranked_needs=list(data.get("ranked_needs") or []),
            match_thesis=data.get("match_thesis", ""),
            interest_via_match=data.get("interest_via_match", ""),
            opening_variant=data.get("opening_variant", "problem_first"),
            proofs=proofs,
            archetype_id=data.get("archetype_id", "standard"),
            jd_goal=data.get("jd_goal", ""),
            research_hook=data.get("research_hook"),
            theme_keywords=list(data.get("theme_keywords") or []),
            pain_points=list(data.get("pain_points") or []),
            selected_cl_claims=list(data.get("selected_cl_claims") or []),
            generated_hook=data.get("generated_hook"),
            hook_attempts=int(data.get("hook_attempts") or 0),
            detected_gaps=list(data.get("detected_gaps") or []),
            gap_acknowledged=bool(data.get("gap_acknowledged", False)),
            fast_eval_warning=bool(data.get("fast_eval_warning", False)),
        )
