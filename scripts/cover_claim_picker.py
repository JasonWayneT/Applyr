"""Select cover proofs from JD × claim catalog only (CR-024 / FR-101)."""
from __future__ import annotations

import re
from typing import List, Set, Tuple

from claim_catalog import ClaimCatalog
from cover_letter_plan import CoverProofSlot
from jd_tailoring import JdProfile, score_claim_for_jd

LENS_ALIAS = {
    "lifecycle": "migration",
    "retention": "customer_success",
    "agile": "execution",
    "alignment": "execution",
    "legal": "compliance",
    "support": "customer_success",
    "qa": "process",
    "global": "delivery",
    "salesforce": "automation",
    "conversion": "automation",
    "finance": "business",
    "synthesis": "executive",
}


def canonical_lens(lens: str) -> str:
    key = (lens or "").strip().lower()
    return LENS_ALIAS.get(key, key or "operations")


def _proof_score(claim_text: str, need: str, profile: JdProfile, jd_text: str) -> int:
    score = score_claim_for_jd(claim_text, profile, jd_text)
    text_l = claim_text.lower()
    need_l = need.lower()
    for token in re.findall(r"[a-z]{5,}", need_l):
        if token in text_l:
            score += 3
    if "ranking" in need_l or "franchise" in need_l:
        if "migrat" in text_l:
            score += 8
        if "platform" in text_l:
            score += 5
    if "monetiz" in need_l or "revenue" in need_l:
        if "revenue" in text_l or "$" in claim_text:
            score += 6
    if "data" in need_l and "data" in text_l:
        score += 4
    if re.search(r"\d", claim_text):
        score += 3
    return score


def pick_cover_proofs(
    catalog: ClaimCatalog,
    ranked_needs: List[str],
    profile: JdProfile,
    jd_text: str,
    k: int = 2,
) -> List[CoverProofSlot]:
    if not catalog.claims or not ranked_needs:
        return []

    need0 = ranked_needs[0]
    need1 = ranked_needs[1] if len(ranked_needs) > 1 else ranked_needs[0]

    def best_for_need(
        need: str, exclude_projects: Set[str], min_score: int
    ) -> Tuple[int, CoverProofSlot] | None:
        best: Tuple[int, CoverProofSlot] | None = None
        for cid, rec in catalog.claims.items():
            if rec.project_id and rec.project_id in exclude_projects:
                continue
            sc = _proof_score(rec.body, need, profile, jd_text)
            if sc < min_score:
                continue
            slot = CoverProofSlot(
                claim_id=cid,
                lens=canonical_lens(rec.title),
                jd_need=need,
                employer=rec.employer,
                project_id=rec.project_id or "",
            )
            if best is None or sc > best[0]:
                best = (sc, slot)
        return best

    proofs: List[CoverProofSlot] = []
    used_projects: Set[str] = set()

    first = best_for_need(need0, used_projects, min_score=10)
    if first:
        proofs.append(first[1])
        if first[1].project_id:
            used_projects.add(first[1].project_id)

    if k >= 2:
        second = best_for_need(need1, used_projects, min_score=8)
        if second and second[1].claim_id != (proofs[0].claim_id if proofs else ""):
            proofs.append(second[1])
        elif proofs:
            alt = best_for_need(need1, set(), min_score=8)
            if alt and alt[1].claim_id != proofs[0].claim_id:
                proofs.append(alt[1])

    proofs = proofs[:k]

    def _has_metric(cid: str) -> bool:
        rec = catalog.claims.get(cid)
        return bool(rec and re.search(r"\d", rec.body))

    metric_count = sum(1 for p in proofs if _has_metric(p.claim_id))
    if proofs and metric_count < min(2, len(proofs)):
        best_metric: Tuple[int, CoverProofSlot] | None = None
        for cid, rec in catalog.claims.items():
            if not re.search(r"\d", rec.body):
                continue
            sc = _proof_score(rec.body, need0, profile, jd_text)
            slot = CoverProofSlot(
                claim_id=cid,
                lens=canonical_lens(rec.title),
                jd_need=need0,
                employer=rec.employer,
                project_id=rec.project_id or "",
            )
            if best_metric is None or sc > best_metric[0]:
                best_metric = (sc, slot)
        if best_metric and proofs:
            proofs[0] = best_metric[1]

    if len(proofs) >= 2 and not _has_metric(proofs[1].claim_id):
        need1 = ranked_needs[1] if len(ranked_needs) > 1 else need0
        best_m2: Tuple[int, CoverProofSlot] | None = None
        for cid, rec in catalog.claims.items():
            if not re.search(r"\d", rec.body):
                continue
            if rec.project_id and rec.project_id == proofs[0].project_id:
                continue
            sc = _proof_score(rec.body, need1, profile, jd_text)
            slot = CoverProofSlot(
                claim_id=cid,
                lens=canonical_lens(rec.title),
                jd_need=need1,
                employer=rec.employer,
                project_id=rec.project_id or "",
            )
            if best_m2 is None or sc > best_m2[0]:
                best_m2 = (sc, slot)
        if best_m2:
            proofs[1] = best_m2[1]

    return proofs
