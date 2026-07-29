"""Select cover proofs from JD × claim catalog only (CR-024 / FR-101)."""
from __future__ import annotations

import re
from typing import List, Set, Tuple

from claim_catalog import ClaimCatalog
from cover_letter_plan import CoverProofSlot
from jd_tailoring import JdProfile, has_ai_signal, score_claim_for_jd

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


def dedupe_cover_proofs(proofs: List[CoverProofSlot]) -> List[CoverProofSlot]:
    """Drop duplicate claim_ids while preserving order."""
    seen: Set[str] = set()
    out: List[CoverProofSlot] = []
    for slot in proofs:
        if slot.claim_id in seen:
            continue
        seen.add(slot.claim_id)
        out.append(slot)
    return out


def is_product_domain_jd(jd_text: str) -> bool:
    """PM roles emphasizing domain ownership, roadmap, and feature strategy."""
    jd_body = _strip_jd_industry_tags(jd_text).lower()
    markers = (
        "product domain",
        "own a key product",
        "feature development",
        "long-term product strategy",
        "long term strateg",
        "product backlog",
        "prioritization of new features",
        "driving requirements",
        "functional spec",
    )
    hits = sum(1 for m in markers if m in jd_body)
    return hits >= 2 or ("product domain" in jd_body and "feature" in jd_body)


def is_connected_devices_jd(jd_text: str) -> bool:
    """IoT / personal safety device / hardware integration JDs."""
    jd_body = _strip_jd_industry_tags(jd_text).lower()
    if any(
        token in jd_body
        for token in (
            "personal safety device",
            "connected device",
            "connected devices",
            "iot ecosystem",
            "device vendor",
            "hardware vendor",
            "firmware update",
            "firmware",
        )
    ):
        return True
    return "iot" in jd_body and "device" in jd_body


def is_marketplace_fintech_jd(need: str, jd_text: str) -> bool:
    """True when JD signals marketplace / lending / funnel context (CR-047)."""
    return _fintech_jd_context(need, jd_text)


def _strip_jd_industry_tags(jd_text: str) -> str:
    """Drop job-board industry tag lines (e.g. 'Fintech • Payments • Software')."""
    lines = []
    for line in jd_text.splitlines():
        stripped = line.strip()
        if stripped.count("•") >= 2 and len(stripped) < 120:
            continue
        lines.append(line)
    return "\n".join(lines)


def _fintech_jd_context(need: str, jd_text: str) -> bool:
    """Marketplace/lending JD — ignore industry-tag footers and standalone 'fintech'."""
    jd_body = _strip_jd_industry_tags(jd_text)
    combined = f"{need} {jd_body}".lower()
    strong_markers = (
        "lender",
        "borrower",
        "loan product",
        "personal loan",
    )
    if any(token in combined for token in strong_markers):
        return True
    if "marketplace" in combined and any(
        token in combined
        for token in ("lender", "borrower", "loan", "lending", "funded volume")
    ):
        return True
    if "funnel" in combined and any(
        token in combined
        for token in ("lender", "borrower", "loan", "funded volume", "approval rate")
    ):
        return True
    if "underwriting" in combined and any(
        token in combined for token in ("lender", "borrower", "loan", "fintech", "marketplace")
    ):
        return True
    return False


def _proof_score(
    claim_text: str,
    need: str,
    profile: JdProfile,
    jd_text: str,
    cover_story: str | None = None,
) -> int:
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
    if "security" in need_l or "security" in jd_text.lower():
        if "security" in text_l or "vulnerab" in text_l:
            score += 8
    if re.search(r"\d", claim_text):
        score += 3
    if cover_story:
        score += 10
        story_l = cover_story.lower()
        for token in re.findall(r"[a-z]{5,}", need_l):
            if token in story_l:
                score += 2
    if is_product_domain_jd(jd_text):
        story_l = (cover_story or "").lower()
        combined = f"{text_l} {story_l}"
        for sig, bonus in (
            ("capacity", 10),
            ("backlog", 9),
            ("roadmap", 9),
            ("stakeholder", 8),
            ("priorit", 8),
            ("trade-off", 7),
            ("trade off", 7),
            ("churn", 6),
            ("retention", 6),
        ):
            if sig in combined:
                score += bonus
    if is_connected_devices_jd(jd_text):
        story_l = (cover_story or "").lower()
        combined = f"{text_l} {story_l}"
        for sig, bonus in (
            ("secur", 10),
            ("compliance", 8),
            ("integrat", 8),
            ("vendor", 7),
            ("firmware", 6),
            ("device", 6),
            ("penetration", 8),
            ("vulnerab", 8),
        ):
            if sig in combined:
                score += bonus
    if _fintech_jd_context(need, jd_text):
        story_l = (cover_story or "").lower()
        combined = f"{text_l} {story_l}"
        for sig, bonus in (
            ("drop-off", 12),
            ("drop off", 12),
            ("integrat", 8),
            ("funnel", 8),
            ("convers", 7),
            ("experiment", 6),
            ("marketplace", 7),
            ("api", 5),
            ("onboard", 5),
            ("partner", 4),
            ("match", 4),
        ):
            if sig in combined:
                score += bonus
    if has_ai_signal(jd_text):
        # JD explicitly signals AI/LLM relevance (FR-209) but no existing bonus
        # block favored AI-specific proof points, so the one grounded AI-tooling
        # claim (ACC-401-AITOOLS) never competed with generic PM claims for a
        # slot even on JDs that named AI/LLM fluency as a core requirement.
        story_l = (cover_story or "").lower()
        combined = f"{text_l} {story_l}"
        for sig, bonus in (
            ("claude", 10),
            ("gemini", 10),
            ("prompt engineer", 10),
            ("agentic", 9),
            ("llm", 8),
            ("ai pipeline", 8),
            ("automation pipeline", 6),
            ("python", 5),
        ):
            if sig in combined:
                score += bonus
    return score


def _refill_proofs_to_k(
    proofs: List[CoverProofSlot],
    k: int,
    ranked_needs: List[str],
    best_for_need,
) -> List[CoverProofSlot]:
    """After dedupe or metric swaps, top up proof slots without repeating claim_ids."""
    proofs = dedupe_cover_proofs(proofs)
    while len(proofs) < k:
        need_i = ranked_needs[len(proofs) % len(ranked_needs)]
        used_projects = {p.project_id for p in proofs if p.project_id}
        used_ids = {p.claim_id for p in proofs}
        extra = best_for_need(
            need_i,
            used_projects,
            min_score=6,
            exclude_claim_ids=used_ids,
        )
        if not extra:
            break
        proofs.append(extra[1])
        if extra[1].project_id:
            used_projects.add(extra[1].project_id)
    return proofs[:k]


_FALLBACK_NEEDS = [
    "product roadmap and cross-functional stakeholder alignment",
    "platform delivery and customer-facing product outcomes",
]


def pick_cover_proofs(
    catalog: ClaimCatalog,
    ranked_needs: List[str],
    profile: JdProfile,
    jd_text: str,
    k: int = 2,
) -> List[CoverProofSlot]:
    if not catalog.claims:
        return []
    # When no needs were extracted from the JD, fall back to generic PM themes
    # rather than returning an empty proof list (which produces an empty letter body).
    if not ranked_needs:
        ranked_needs = _FALLBACK_NEEDS

    need0 = ranked_needs[0]
    need1 = ranked_needs[1] if len(ranked_needs) > 1 else ranked_needs[0]

    def best_for_need(
        need: str,
        exclude_projects: Set[str],
        min_score: int,
        exclude_claim_ids: Set[str] | None = None,
    ) -> Tuple[int, CoverProofSlot] | None:
        best: Tuple[int, CoverProofSlot] | None = None
        blocked_ids = exclude_claim_ids or set()
        for cid, rec in catalog.claims.items():
            if cid in blocked_ids:
                continue
            if rec.project_id and rec.project_id in exclude_projects:
                continue
            sc = _proof_score(rec.body, need, profile, jd_text, cover_story=rec.cover_story)
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
            if second[1].project_id:
                used_projects.add(second[1].project_id)
        elif proofs:
            alt = best_for_need(need1, set(), min_score=8)
            if alt and alt[1].claim_id != proofs[0].claim_id:
                proofs.append(alt[1])

    if k >= 3 and proofs:
        need2 = ranked_needs[2] if len(ranked_needs) > 2 else need1
        third = best_for_need(need2, used_projects, min_score=6)
        if third and third[1].claim_id not in {p.claim_id for p in proofs}:
            proofs.append(third[1])

    proofs = proofs[:k]

    def _has_metric(cid: str) -> bool:
        rec = catalog.claims.get(cid)
        return bool(rec and re.search(r"\d", rec.body))

    # The AI-tooling claim (ACC-401-AITOOLS) has no metric by design — it is a
    # qualitative capability claim, not a quantified outcome, and CLAUDE.md's
    # anti-hallucination rules forbid inventing a number just to satisfy this
    # density check. Without this guard it reliably won the initial pick on
    # AI-signal JDs (see has_ai_signal-gated bonus above) and then got silently
    # discarded here for lacking a digit, which was the actual root cause of the
    # cover letter never using it even when it was clearly the best-scoring proof.
    def _protected_ai_slot(idx: int) -> bool:
        return (
            has_ai_signal(jd_text)
            and idx < len(proofs)
            and proofs[idx].claim_id == "ACC-401-AITOOLS"
        )

    metric_count = sum(1 for p in proofs if _has_metric(p.claim_id))
    if proofs and metric_count < min(2, len(proofs)) and not _protected_ai_slot(0):
        best_metric: Tuple[int, CoverProofSlot] | None = None
        for cid, rec in catalog.claims.items():
            if not re.search(r"\d", rec.body):
                continue
            sc = _proof_score(rec.body, need0, profile, jd_text, cover_story=rec.cover_story)
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

    if len(proofs) >= 2 and not _has_metric(proofs[1].claim_id) and not _protected_ai_slot(1):
        need1 = ranked_needs[1] if len(ranked_needs) > 1 else need0
        best_m2: Tuple[int, CoverProofSlot] | None = None
        for cid, rec in catalog.claims.items():
            if not re.search(r"\d", rec.body):
                continue
            if rec.project_id and rec.project_id == proofs[0].project_id:
                continue
            sc = _proof_score(rec.body, need1, profile, jd_text, cover_story=rec.cover_story)
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

    if is_product_domain_jd(jd_text):
        return _product_domain_proofs(catalog, ranked_needs, k)

    return _refill_proofs_to_k(proofs, k, ranked_needs, best_for_need)


def _product_domain_proofs(
    catalog: ClaimCatalog,
    ranked_needs: List[str],
    k: int,
) -> List[CoverProofSlot]:
    """Fixed proof stack for domain-ownership PM roles: capacity → trust → extras."""
    need0 = ranked_needs[0] if ranked_needs else ""
    need1 = ranked_needs[1] if len(ranked_needs) > 1 else need0
    slots: List[CoverProofSlot] = []
    for cid, need in (
        ("ACC-105-PROCESS", need0),
        ("ACC-102-BUS", need1),
    ):
        rec = catalog.claims.get(cid)
        if not rec:
            continue
        slots.append(
            CoverProofSlot(
                claim_id=cid,
                lens=canonical_lens(rec.title),
                jd_need=need,
                employer=rec.employer,
                project_id=rec.project_id or "",
            )
        )
    rec101 = catalog.claims.get("ACC-101-PM")
    if rec101 and len(slots) < k:
        slots.append(
            CoverProofSlot(
                claim_id="ACC-101-PM",
                lens=canonical_lens(rec101.title),
                jd_need=need1,
                employer=rec101.employer,
                project_id=rec101.project_id or "",
            )
        )
    return slots[:k]
