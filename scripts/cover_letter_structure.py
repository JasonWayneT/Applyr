"""Cover letter block assembly (CR-047 — universal structure, archetype variants)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from claim_catalog import ClaimCatalog, ClaimRecord
from cover_claim_picker import (
    is_connected_devices_jd,
    is_marketplace_fintech_jd,
    is_product_domain_jd,
)
from cover_letter_plan import CoverLetterPlan, CoverProofSlot
from cover_phrasing import (
    apply_cover_phrase_polish,
    apply_voice_polish,
    render_structured_close,
    render_trust_hook,
    strip_opener_hook_from_body,
    value_lead_from_story,
    word_min_for_variant,
)

LEGACY_SHORT_PREFIX = "During that period, I also kept"

EMPLOYER_DISPLAY = {
    "cision": "Cision",
    "sterkly": "Sterkly",
    "zero_to_sixty": "Zero to Sixty",
}


@dataclass
class CoverBlock:
    kind: str
    text: str


def detect_archetype(jd_text: str, ranked_needs: List[str]) -> str:
    need0 = ranked_needs[0] if ranked_needs else ""
    if is_marketplace_fintech_jd(need0, jd_text):
        return "marketplace_fintech"
    if is_connected_devices_jd(jd_text):
        return "connected_devices"
    if is_product_domain_jd(jd_text):
        return "product_domain"
    jd_l = jd_text.lower()
    if ("analytics product" in jd_l or "analytics products" in jd_l) and (
        "adopt" in jd_l or "demo" in jd_l
    ):
        return "analytics_adoption"
    return "platform_standard"


def employer_display_name(slug: str) -> str:
    key = (slug or "").strip().lower()
    return EMPLOYER_DISPLAY.get(key, key.replace("_", " ").title() if key else "")


def _employer_scale_phrase(catalog: ClaimCatalog, employer: str) -> str:
    for rec in catalog.claims.values():
        if rec.employer != employer:
            continue
        blob = f"{rec.cover_story or ''} {rec.body}"
        m = re.search(r"\$[\d.]+\s*[MmKk]?\s*ARR", blob)
        if m:
            return m.group(0).strip()
    return ""


def _need_frame_phrase(archetype_id: str, jd_text: str) -> str:
    if archetype_id == "marketplace_fintech":
        parts = ["complex integrations", "customer-facing product problems"]
        jd_l = jd_text.lower()
        if "funnel" in jd_l or "conversion" in jd_l:
            parts.append("funnel conversion with measurable outcomes")
        else:
            parts.append("measurable outcomes")
        return ", ".join(parts)
    return "complex product execution with measurable outcomes"


def render_domain_first_opening(
    company: str, role_title: str, jd_text: str
) -> str:
    role_line = (
        f"{company}'s {role_title} role fits the work I do best: owning complex "
        f"product areas, aligning business and engineering teams, and turning "
        f"customer-visible product problems into measurable product outcomes."
    )
    context = (
        "I bring four years of B2B SaaS platform work and two years of B2C product "
        "experience, where product decisions had to balance customer trust, roadmap "
        "clarity, technical constraints, and business performance."
    )
    return f"{role_line} {context}"


def render_need_first_frame(
    company: str, role_title: str, archetype_id: str, jd_text: str
) -> str:
    phrase = _need_frame_phrase(archetype_id, jd_text)
    return (
        f"{company}'s {role_title} role sits where I have done my best work: "
        f"{phrase}."
    )


def render_work_history_bridge(
    slot: CoverProofSlot,
    catalog: ClaimCatalog,
    *,
    include_scale: bool = True,
) -> str:
    employer = employer_display_name(slot.employer)
    scale = _employer_scale_phrase(catalog, slot.employer) if include_scale else ""
    if scale:
        return (
            f"At {employer}, on a {scale} B2B platform, that was the kind of "
            f"problem I was responsible for solving."
        )
    return (
        f"At {employer}, that was the kind of problem I was responsible for solving."
    )


def render_proof_ladder(
    slot: CoverProofSlot,
    plan: CoverLetterPlan,
    jd_text: str,
    proof_index: int,
) -> str:
    if proof_index != 1:
        return ""
    lens = (slot.lens or "").lower()
    jd_l = jd_text.lower()
    archetype = plan.archetype_id

    if archetype == "marketplace_fintech" and lens in (
        "rebuild",
        "migration",
        "technical",
        "data",
    ):
        if "lender" in jd_l or "onboarding" in jd_l:
            return (
                "That same cross-functional execution matters in partner integrations "
                "and go-lives, including the lender onboarding work central to this role."
            )
        return (
            "That same cross-functional execution matters in partner integrations "
            "and go-lives."
        )
    if archetype == "analytics_adoption":
        return (
            "That same product discipline matters for analytics experiences that need "
            "real adoption, not shelfware demos."
        )
    if archetype == "connected_devices" and proof_index == 1:
        return (
            "That same cross-functional execution carries into device vendor "
            "integrations, firmware release coordination, and platform "
            "interoperability work."
        )
    if archetype == "product_domain":
        return ""
    if "integrat" in jd_l or lens in ("rebuild", "migration", "technical"):
        return (
            "That same cross-functional execution carries into integration and "
            "platform delivery work."
        )
    if archetype == "platform_standard":
        return (
            "That same execution discipline carries into the platform and roadmap "
            "work this role owns."
        )
    return ""


def _story_body_after_hook(story: str, hook: str) -> str:
    body = strip_opener_hook_from_body(story, hook)
    # Only strip the value lead when this story was actually used in the opener.
    # Secondary proofs (hook="") must keep their first sentence or the body
    # will start with a pronoun whose antecedent is missing.
    if hook:
        body = strip_opener_hook_from_body(body, value_lead_from_story(story))
    return body.strip()


def _trim_redundant_proof_sentences(body: str) -> str:
    for pat in (
        r"\s*Business and customer wins moved together[^.]*\.",
        r"\s*customer trust and the business outcome improved together[^.]*\.",
        r"\s*That experience is directly relevant[^.]*\.",
    ):
        body = re.sub(pat, "", body, flags=re.I)
    body = body.strip()
    if body and body[0].islower():
        body = body[0].upper() + body[1:]
    return body


def _append_fintech_outcome_suffix(
    body: str, archetype_id: str, slot: CoverProofSlot
) -> str:
    """Only extend data/trust proof bodies — not integration or legacy slots."""
    if archetype_id != "marketplace_fintech":
        return body
    lens = (slot.lens or "").lower()
    if lens not in ("business", "data", "finance", "pm", "product") or "113" in (
        slot.project_id or ""
    ):
        return body
    if "funnel conversion" in body.lower() and "hurting funnel" in body.lower():
        return body
    if "drop-off" in body.lower() or "drop off" in body.lower():
        body = re.sub(
            r"(eroding trust)\.",
            r"\1 that was hurting funnel conversion and customer trust.",
            body,
            count=1,
            flags=re.I,
        )
        for pat in (
            r"\s*Business and customer wins moved together[^.]*\.",
            r"\s*customer trust and the business outcome improved together[^.]*\.",
        ):
            body = re.sub(pat, "", body, flags=re.I)
        body = body.strip()
        if body and body[0].islower():
            body = body[0].upper() + body[1:]
    return body


def _render_capacity_domain_body(
    slot: CoverProofSlot, catalog: ClaimCatalog
) -> str:
    rec = catalog.claims.get(slot.claim_id)
    if not rec or not rec.cover_story:
        return ""
    employer = employer_display_name(slot.employer)
    story = apply_cover_phrase_polish(rec.cover_story.strip())
    story = re.sub(
        r"competing for a fraction of the original capacity",
        "competing for limited capacity",
        story,
        flags=re.I,
    )
    story = re.sub(
        r"declined non-critical feature requests to protect the stability work preventing churn",
        "protected stability work by making feature trade-offs explicit",
        story,
        flags=re.I,
    )
    story = re.sub(
        r"made every scope trade-off visible",
        "made scope trade-offs visible",
        story,
        flags=re.I,
    )
    story = re.sub(
        r"Retention held at 7% annually",
        "Annual churn held near 7%",
        story,
        flags=re.I,
    )
    if not story.lower().startswith("at "):
        lead = story[0].lower() + story[1:] if story else story
        story = f"At {employer}, {lead}"
    if not story.endswith("."):
        story += "."
    return apply_voice_polish(story)


def _render_domain_trust_body() -> str:
    return apply_voice_polish(
        "When customers said the contact data was wrong, I treated it as a product trust "
        "problem, not a minor bug. I listened through CX and churn signals, partnered with "
        "engineering and database administration on a more reliable data path around failing "
        "ETL processes, and eliminated a 40% drop-off and stale-data complaints that had been "
        "eroding trust."
    )


def _render_domain_trust_intro_body() -> str:
    intro = (
        "I have also owned customer-facing product problems where a technical failure "
        "was also a business problem."
    )
    return f"{intro} {_render_domain_trust_body()}"


def _render_domain_legacy_body(
    slot: CoverProofSlot, catalog: ClaimCatalog
) -> str:
    rec = catalog.claims.get(slot.claim_id)
    if rec and rec.cover_story:
        story = apply_cover_phrase_polish(rec.cover_story.strip())
        story = re.sub(
            r"the company's highest-revenue platform",
            "a high-revenue legacy product",
            story,
            flags=re.I,
        )
        story = re.sub(
            r"I was hired after leadership ended an earlier migration program on",
            "After an earlier migration program ended, I was brought in to keep",
            story,
            flags=re.I,
        )
        story = re.sub(
            r"and needed the legacy product kept viable while customers were retained",
            "viable while customers were retained and a realistic migration path was rebuilt",
            story,
            flags=re.I,
        )
        story = re.sub(
            r"My mandate was stability, security, churn, and cost until a realistic migration path existed",
            "My mandate covered stability, security, churn, and cost, which required close partnership with engineering, DevOps, Legal, and business stakeholders",
            story,
            flags=re.I,
        )
        story = re.sub(
            r"I partnered with engineering, DevOps, and Legal on monitoring, compliant cleanups, and outage reduction so the platform stayed dependable through that bridge period\.?",
            "",
            story,
            flags=re.I,
        )
        story = story.strip()
        if story and not story.endswith("."):
            story += "."
        prefix = "I applied the same discipline to broader platform ownership."
        return apply_voice_polish(f"{prefix} {story}")
    return apply_voice_polish(
        "I applied the same discipline to broader platform ownership. "
        "After an earlier migration program ended, I was brought in to keep a high-revenue "
        "legacy product viable while customers were retained and a realistic migration path "
        "was rebuilt. My mandate covered stability, security, churn, and cost, which required "
        "close partnership with engineering, DevOps, Legal, and business stakeholders."
    )


def _render_data_trust_marketplace_body() -> str:
    """Primary data/trust proof for marketplace letters (CR-047 / Splash v7)."""
    return (
        "I listened through CX and churn signals, aligned engineering and database "
        "administration on a more reliable data path around failing ETL processes, "
        "and eliminated a 40% drop-off that was hurting funnel conversion and "
        "customer trust."
    )


def _render_integration_marketplace_body(rec: ClaimRecord) -> str:
    """Shorter integration proof for marketplace letters (CR-047 / Splash v7)."""
    return (
        "A B2B PR attribution tool was becoming unstable during a full Google "
        "Analytics platform migration. I rebuilt the integration by studying system "
        "behavior and delivered a pipeline that was more stable and better documented. "
        "Two other internal platform teams later used it as their reference model."
    )


def render_proof_body(
    slot: CoverProofSlot,
    catalog: ClaimCatalog,
    archetype_id: str,
    opener_hook: str = "",
) -> str:
    rec = catalog.claims.get(slot.claim_id)
    if not rec or not rec.cover_story:
        from cover_narrative_templates import render_proof_paragraph

        return render_proof_paragraph(slot, catalog, "")

    if archetype_id == "product_domain":
        cid = slot.claim_id or ""
        if cid.startswith("ACC-105"):
            return _render_capacity_domain_body(slot, catalog)
        if cid.startswith("ACC-102"):
            return _render_domain_trust_body()

    if archetype_id == "marketplace_fintech":
        cid = slot.claim_id or ""
        lens = (slot.lens or "").lower()
        if cid.startswith("ACC-102") and lens in ("business", "data", "finance"):
            return apply_voice_polish(_render_data_trust_marketplace_body())
        if lens in ("rebuild", "migration", "technical") and cid.startswith("ACC-113"):
            return apply_voice_polish(_render_integration_marketplace_body(rec))

    story = rec.cover_story.strip()
    if not story.endswith("."):
        story += "."
    body = _story_body_after_hook(story, opener_hook)
    body = apply_cover_phrase_polish(body)
    body = _trim_redundant_proof_sentences(body)
    body = _append_fintech_outcome_suffix(body, archetype_id, slot)
    body = apply_voice_polish(body)
    if _word_count_text(body) < 70:
        full = apply_voice_polish(apply_cover_phrase_polish(story))
        full = _story_body_after_hook(full, opener_hook)
        if _word_count_text(full) > _word_count_text(body):
            body = full
    return body


def render_legacy_short(
    slot: CoverProofSlot, catalog: ClaimCatalog
) -> str:
    rec = catalog.claims.get(slot.claim_id)
    churn_clause = "holding annual churn near 7%"
    if rec and rec.cover_story and "7%" in rec.cover_story:
        m = re.search(
            r"(?:holding|held)[^.]*7%[^.]*|near 7%[^.]*",
            rec.cover_story,
            re.I,
        )
        if m:
            churn_clause = m.group(0).strip().rstrip(".")
            if not churn_clause.lower().startswith("hold"):
                churn_clause = f"holding annual churn near 7%"
    return (
        "During that period, I also kept the broader legacy platform dependable "
        f"through a migration bridge, {churn_clause} while balancing stability, "
        "security, and roadmap trade-offs."
    )


def _domain_proof_order(proofs: List[CoverProofSlot]) -> List[CoverProofSlot]:
    priority = {
        "process": 0,
        "execution": 0,
        "agile": 0,
        "roadmap": 0,
        "business": 1,
        "data": 1,
        "finance": 1,
        "product": 3,
        "platform": 3,
        "lifecycle": 3,
        "retention": 3,
        "customer_success": 3,
        "executive": 2,
    }

    def key(slot: CoverProofSlot) -> Tuple[int, str]:
        cid = slot.claim_id or ""
        if cid.startswith("ACC-105"):
            return (0, cid)
        if cid.startswith("ACC-102"):
            return (1, cid)
        if cid.startswith("ACC-101"):
            return (99, cid)
        return (priority.get((slot.lens or "").lower(), 2), cid)

    return sorted(proofs, key=key)


def _marketplace_proof_order(proofs: List[CoverProofSlot]) -> List[CoverProofSlot]:
    priority = {
        "business": 0,
        "data": 0,
        "finance": 0,
        "rebuild": 1,
        "migration": 1,
        "technical": 1,
        "product": 2,
        "platform": 2,
        "lifecycle": 2,
        "customer_success": 2,
        "retention": 2,
    }

    def key(slot: CoverProofSlot) -> Tuple[int, str]:
        return (priority.get((slot.lens or "").lower(), 1), slot.claim_id)

    return sorted(proofs, key=key)


def render_opener_block(
    plan: CoverLetterPlan,
    jd_text: str,
    primary_story: str,
) -> str:
    if plan.opening_variant == "need_first":
        trust_hook = render_trust_hook(primary_story) if primary_story else ""
        frame = render_need_first_frame(
            plan.company_display, plan.role_title, plan.archetype_id, jd_text
        )
        parts = [frame]
        if trust_hook:
            parts.append(trust_hook)
        return apply_voice_polish(" ".join(parts))

    if plan.opening_variant == "domain_first":
        return apply_voice_polish(
            render_domain_first_opening(
                plan.company_display, plan.role_title, jd_text
            )
        )

    from cover_narrative_templates import render_application_first_opening

    need0 = plan.ranked_needs[0] if plan.ranked_needs else plan.jd_goal
    opening = render_application_first_opening(
        plan.company_display,
        plan.role_title,
        need0,
        plan.theme_keywords,
        jd_text,
        primary_story=primary_story,
    )
    if plan.research_hook:
        opening = f"{plan.research_hook} {opening}"
    if plan.archetype_id == "connected_devices" and "connected device" not in opening.lower():
        opening = (
            f"{opening.rstrip()} The role centers on connected device lifecycles, "
            f"vendor integrations, and platform interoperability."
        )
    return apply_voice_polish(opening)


def build_cover_blocks(
    plan: CoverLetterPlan,
    catalog: ClaimCatalog,
    jd_text: str,
) -> List[CoverBlock]:
    blocks: List[CoverBlock] = []
    proofs = list(plan.proofs)
    if plan.archetype_id == "marketplace_fintech":
        proofs = _marketplace_proof_order(proofs)
    elif plan.archetype_id == "product_domain":
        proofs = _domain_proof_order(proofs)

    def _is_legacy_platform_slot(s: CoverProofSlot) -> bool:
        pid = s.project_id or ""
        if "101" in pid or (s.claim_id or "").startswith("ACC-101"):
            return True
        return (s.lens or "").lower() in (
            "product",
            "platform",
            "lifecycle",
            "migration",
            "pm",
        ) and "101" in pid

    legacy_slots = [s for s in proofs if _is_legacy_platform_slot(s)]
    if (
        plan.archetype_id == "marketplace_fintech"
        and not legacy_slots
        and "ACC-101-PM" in catalog.claims
    ):
        need0 = plan.ranked_needs[0] if plan.ranked_needs else ""
        legacy_slots = [
            CoverProofSlot(
                "ACC-101-PM",
                "pm",
                need0,
                catalog.claims["ACC-101-PM"].employer,
                "ACC-101",
            )
        ]
    main_slots = [s for s in proofs if s not in legacy_slots]

    primary_story = ""
    if plan.archetype_id == "product_domain":
        for cid in ("ACC-105-PROCESS", "ACC-105-EXECUTION"):
            rec = catalog.claims.get(cid)
            if rec and rec.cover_story:
                primary_story = rec.cover_story
                break
    story_slots = main_slots or proofs
    if not primary_story:
        for slot in story_slots:
            rec = catalog.claims.get(slot.claim_id)
            if rec and rec.cover_story:
                primary_story = rec.cover_story
                break

    if plan.opening_variant == "need_first":
        opener_hook = render_trust_hook(primary_story) if primary_story else ""
    elif plan.opening_variant == "domain_first":
        opener_hook = ""
    else:
        opener_hook = render_trust_hook(primary_story) or value_lead_from_story(
            primary_story
        )
        opener_hook = opener_hook if primary_story else ""

    blocks.append(
        CoverBlock("opener", render_opener_block(plan, jd_text, primary_story))
    )

    rendered_main_ids: set[str] = set()
    for i, slot in enumerate(main_slots):
        parts: List[str] = []
        if i == 0 and plan.archetype_id != "product_domain":
            omit_scale = bool(
                legacy_slots and plan.archetype_id != "marketplace_fintech"
            )
            # Also omit scale when another main slot's cover_story will repeat it,
            # preventing "Repeated $40M ARR" recruiter QA failures.
            if not omit_scale:
                scale = _employer_scale_phrase(catalog, slot.employer)
                if scale and any(
                    scale in (getattr(catalog.claims.get(s.claim_id), "cover_story", "") or "")
                    for s in main_slots[1:]
                ):
                    omit_scale = True
            parts.append(
                render_work_history_bridge(
                    slot, catalog, include_scale=not omit_scale
                )
            )
        ladder = render_proof_ladder(slot, plan, jd_text, proof_index=i)
        if ladder:
            parts.append(ladder)
        if plan.archetype_id == "product_domain" and i == 1:
            body = _render_domain_trust_intro_body()
        else:
            body = render_proof_body(
                slot,
                catalog,
                plan.archetype_id,
                opener_hook=opener_hook if i == 0 else "",
            )
        if body:
            parts.append(body)
        if parts:
            blocks.append(CoverBlock("proof", " ".join(parts)))
            rendered_main_ids.add(slot.claim_id)

    if legacy_slots:
        if plan.archetype_id == "marketplace_fintech":
            legacy_text = render_legacy_short(legacy_slots[0], catalog)
        elif plan.archetype_id == "product_domain":
            legacy_text = _render_domain_legacy_body(legacy_slots[0], catalog)
        else:
            legacy_text = render_proof_body(
                legacy_slots[0], catalog, plan.archetype_id
            )
        blocks.append(CoverBlock("legacy_proof", legacy_text))

    close = render_structured_close(plan.company_display, jd_text, plan.archetype_id)
    blocks.append(CoverBlock("close", close))

    return pad_cover_blocks_to_min(
        blocks,
        plan,
        catalog,
        jd_text,
        proofs,
        legacy_slots,
        rendered_main_ids,
        opener_hook,
    )


def blocks_to_prose(blocks: List[CoverBlock]) -> str:
    return "\n\n".join(b.text for b in blocks if b.text.strip())


def _word_count_text(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _valid_opener_context_phrase(text: str) -> bool:
    """Reject truncated pain-point fragments unfit for opener padding."""
    t = text.strip().rstrip(".")
    if len(t) < 28 or len(t) > 140:
        return False
    if len(t.split()) < 6:
        return False
    tl = t.lower()
    if any(
        tl.startswith(prefix)
        for prefix in (
            # Articles / prepositions
            "build ",
            "and ",
            "with ",
            "the ",
            "to ",
            "for ",
            "in an ",
            "in a ",
            # JD imperative verb starters — responsibility bullets, not pain points
            # infinitive, 3rd-person singular, and -ing (gerund/participial) forms
            "drive ", "drives ", "driving ",
            "own ", "owns ", "owning ",
            "solve ", "solves ", "solving ",
            "scale ", "scales ", "scaling ",
            "grow ", "grows ", "growing ",
            "lead ", "leads ", "leading ",
            "run ", "runs ", "running ",
            "engage ", "engages ", "engaging ",
            "deliver ", "delivers ", "delivering ",
            "develop ", "develops ", "developing ",
            "manage ", "manages ", "managing ",
            "expand ", "expands ", "expanding ",
            "ensure ", "ensures ", "ensuring ",
            "support ", "supports ", "supporting ",
            "improve ", "improves ", "improving ",
            "establish ", "establishes ", "establishing ",
            "partner ", "partners ", "partnering ",
            "help ", "helps ", "helping ",
            "reduce ", "reduces ", "reducing ",
            "create ", "creates ", "creating ",
            "define ", "defines ", "defining ",
            "collaborate ", "collaborates ", "collaborating ",
            "execute ", "executes ", "executing ",
            "identify ", "identifies ", "identifying ",
            "design ", "designs ", "designing ",
            "plan ", "plans ", "planning ",
            "coordinate ", "coordinates ", "coordinating ",
            "maintain ", "maintains ", "maintaining ",
            "track ", "tracks ", "tracking ",
            "review ", "reviews ", "reviewing ",
            "build ", "builds ", "building ",
            "leverage ", "leverages ", "leveraging ",
            "thrive ", "thrives ", "thriving ",
            "work ", "works ", "working ",
            "adapt ", "adapts ", "adapting ",
            # Candidate-fit / culture phrases common in JD postings
            "interested ", "excited ", "passionate ",
            "you will ", "you'll ", "you are ",
            "we are ", "we're ", "our team ",
            "this role ", "the role ", "the ideal ",
            "we're looking ", "we are looking ", "looking for ",
            "experience ",
            "candidates ",
            "product ",
        )
    ):
        return False
    return True


def _expand_opener_with_jd_context(
    opener: str, plan: CoverLetterPlan, jd_text: str
) -> str:
    """Add one JD-grounded sentence when the opener is thin (application-first only)."""
    if plan.opening_variant == "need_first":
        return opener
    if plan.opening_variant == "domain_first":
        return opener
    if plan.archetype_id == "connected_devices":
        return opener
    candidates: List[str] = []
    for pain in plan.pain_points or []:
        pain = pain.strip()
        if (
            _valid_opener_context_phrase(pain)
            and pain.lower() not in opener.lower()
        ):
            candidates.append(pain.rstrip("."))
    from cover_jd_needs import need_to_goal_phrase

    for need in plan.ranked_needs or []:
        goal = need_to_goal_phrase(need).strip()
        if (
            len(goal) >= 24
            and goal.lower() not in opener.lower()
            and _valid_opener_context_phrase(goal)
        ):
            candidates.append(goal.rstrip("."))
            break
    if not candidates:
        return opener
    cand = candidates[0]
    cand = cand[0].upper() + cand[1:] if cand else cand
    return f"{opener.rstrip()} {cand}."


def _insert_proof_before_close(blocks: List[CoverBlock], text: str) -> None:
    if not text.strip():
        return
    close_idx = next(
        (i for i, b in enumerate(blocks) if b.kind == "close"),
        len(blocks),
    )
    blocks.insert(close_idx, CoverBlock("proof", text))


def pad_cover_blocks_to_min(
    blocks: List[CoverBlock],
    plan: CoverLetterPlan,
    catalog: ClaimCatalog,
    jd_text: str,
    proofs: List[CoverProofSlot],
    legacy_slots: List[CoverProofSlot],
    rendered_main_ids: set[str],
    opener_hook: str,
) -> List[CoverBlock]:
    """Expand substantive content until the letter reaches the audit word band."""
    target = word_min_for_variant(plan.opening_variant)

    def current_wc() -> int:
        return _word_count_text(blocks_to_prose(blocks))

    if current_wc() >= target:
        return blocks

    for i, block in enumerate(blocks):
        if block.kind == "opener":
            expanded = _expand_opener_with_jd_context(block.text, plan, jd_text)
            if expanded != block.text:
                blocks[i] = CoverBlock("opener", expanded)
                if current_wc() >= target:
                    return blocks
            break

    if legacy_slots and current_wc() < target:
        for i, block in enumerate(blocks):
            if block.kind in ("proof", "legacy_proof") and block.text.startswith(LEGACY_SHORT_PREFIX):
                full = render_proof_body(
                    legacy_slots[0], catalog, plan.archetype_id
                )
                if full and full != block.text:
                    blocks[i] = CoverBlock("legacy_proof", full)
                break

    proof_count = sum(1 for b in blocks if b.kind == "proof")
    for slot in proofs:
        if current_wc() >= target:
            break
        if slot.claim_id in rendered_main_ids:
            continue
        if slot in legacy_slots:
            continue
        ladder = render_proof_ladder(slot, plan, jd_text, proof_index=proof_count)
        rec = catalog.claims.get(slot.claim_id)
        if not (rec and rec.cover_story) and current_wc() >= target:
            continue
        body = render_proof_body(slot, catalog, plan.archetype_id)
        parts = [p for p in (ladder, body) if p]
        if parts:
            _insert_proof_before_close(blocks, " ".join(parts))
            rendered_main_ids.add(slot.claim_id)
            proof_count += 1

    # Expand the legacy_proof block to its full cover_story when still below target.
    # The initial render strips the lead sentence; restoring it adds ~25-30 words for
    # platform_standard letters where the opener does not use that story's trust hook.
    if current_wc() < target and legacy_slots and plan.archetype_id == "platform_standard":
        slot0 = legacy_slots[0]
        rec0 = catalog.claims.get(slot0.claim_id)
        if rec0 and rec0.cover_story:
            full_body = apply_voice_polish(
                apply_cover_phrase_polish(rec0.cover_story.strip())
            )
            for i, block in enumerate(blocks):
                if block.kind == "legacy_proof":
                    if _word_count_text(full_body) > _word_count_text(block.text):
                        blocks[i] = CoverBlock("legacy_proof", full_body)
                    break

    # Render any unrendered legacy slots as additional proof blocks when still below target.
    if current_wc() < target and len(legacy_slots) > 1:
        rendered_legacy_ids = {legacy_slots[0].claim_id}
        for slot in legacy_slots[1:]:
            if current_wc() >= target:
                break
            if slot.claim_id in rendered_legacy_ids:
                continue
            rec = catalog.claims.get(slot.claim_id)
            employer = employer_display_name(slot.employer)
            if rec and rec.cover_story:
                full_story = apply_voice_polish(
                    apply_cover_phrase_polish(rec.cover_story.strip())
                )
                scale = _employer_scale_phrase(catalog, slot.employer)
                if scale:
                    connector = (
                        f"At {employer}, on a {scale} B2B platform, the same period of "
                        f"platform stewardship also required managing retention and churn "
                        f"outcomes with the same discipline as the product roadmap and "
                        f"stability work."
                    )
                else:
                    connector = (
                        f"At {employer}, that same period of platform stewardship also "
                        f"required managing retention and churn outcomes with the same "
                        f"discipline as the product roadmap and stability work."
                    )
                body = f"{connector} {full_story}"
            else:
                body = render_proof_body(slot, catalog, plan.archetype_id)
            if body:
                _insert_proof_before_close(blocks, body)
                rendered_legacy_ids.add(slot.claim_id)

    return blocks
