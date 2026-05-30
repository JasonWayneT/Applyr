"""
Bite-sized local drafting stages (CR-013).

Tier 0–2 and 4–6 are deterministic. Tier 3 uses one LLM call per claim with fail-closed gates.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

from pipeline_env import resume_bullet_quotas

from verify_claims import _verify_bullet_local, extract_numeric_tokens

# Mirrors drafting_engine guards — kept here to avoid import cycles.
BLOCKED_TOOLS = [
    "Snowflake", "Tableau", "Looker", "dbt", "Airflow", "Spark", "Kafka",
    "Kubernetes", "Docker", "Terraform", "Helm", "Jenkins", "CircleCI",
    "FHIR", "HL7", "HIPAA", "SOC2", "SOC 2", "ISO 27001",
    "Databricks", "Redshift", "BigQuery", "Fivetran", "Segment",
    "Amplitude", "Mixpanel", "Pendo", "LaunchDarkly",
    "React", "Node.js", "GraphQL", "Rust", "Go",
    "TensorFlow", "PyTorch", "LangChain", "RAG", "LLM pipeline",
    "AWS", "Azure", "GCP", "Heroku",
]

SENIORITY_INFLATION_PHRASES = [
    "led a team of", "led team of", "managed a team", "managed team",
    "director of", "vice president", " vp ", "head of",
    "hired and", "hire and", "supervised",
    "people management", "direct reports",
    "p&l ownership", "revenue owner", "owned billing",
    "shipped ai", "shipped ml", "trained model", "deployed model",
    "built ml", "built ai", "ai pipeline", "ml pipeline",
]

EMPLOYERS = ("cision", "sterkly", "zero_to_sixty")
MIN_BULLETS_PER_EMPLOYER = 2
MAX_BULLETS_PER_EMPLOYER = 5
RESUME_CHAR_BUDGET = 3800
SUMMARY_MAX_CHARS = 780
SUMMARY_MIN_SENTENCES = 3
SUMMARY_PROOF_MAX_CHARS = 175
_INCOMPLETE_PROOF_TAIL = re.compile(
    r"\b(?:to|and|or|by|for|with|across|against|in|on|of|the|a|an)\s*\.$",
    re.I,
)
MAX_BULLET_WORDS = 28

# Canonical resume ### headers — one role title per employer (no slash-combined titles).
EMPLOYER_EXPERIENCE_HEADERS: Dict[str, str] = {
    "cision": (
        "### Product Manager | Cision | September 2021 - January 2026\n"
        "Full Remote\n"
    ),
    "sterkly": (
        "### Product Manager | Sterkly | February 2019 - August 2021\n"
        "San Diego, CA\n"
    ),
    "zero_to_sixty": (
        "### Product Owner | Zero to Sixty | June 2017 - January 2019\n"
        "San Diego, CA\n"
    ),
}


def experience_skeleton() -> Dict[str, str]:
    return dict(EMPLOYER_EXPERIENCE_HEADERS)


def normalize_employer_job_titles(text: str) -> str:
    """Enforce single canonical title per employer on ### experience lines."""
    zts_combined = (
        r"Product Owner\s*/\s*Account Manager",
        r"Account Manager\s*/\s*Product Owner",
        r"Product Owner\s*/\s*Product Manager",
        r"Account Manager\s*/\s*Product Manager",
    )
    cision_hybrid = (
        "Product Owner / Functional Product Manager",
        "Product Owner / Platform Product Manager",
        "Product Owner (Functionally Product Manager)",
        "Product Owner (Functional Scope)",
        "Product Owner → Product Manager (Functional Scope)",
        "Product Owner -> Product Manager (Functional Scope)",
        "Product Owner / Product Manager",
        "Product Owner",
    )
    lines: List[str] = []
    for line in text.split("\n"):
        low = line.lower()
        if "zero to sixty" in low or "zero to 60" in low:
            for pat in zts_combined:
                line = re.sub(pat, "Product Owner", line, flags=re.I)
            if re.search(r"\bAccount Manager\b", line, re.I):
                line = re.sub(r"\bAccount Manager\b", "Product Owner", line, flags=re.I)
        elif "cision" in low:
            for ugly in cision_hybrid:
                line = re.sub(re.escape(ugly), "Product Manager", line, flags=re.I)
            line = re.sub(
                r"Product Manager\s*/\s*Product Manager",
                "Product Manager",
                line,
                flags=re.I,
            )
            line = re.sub(
                r"Product Manager\s*/\s*Platform Product Manager",
                "Product Manager",
                line,
                flags=re.I,
            )
        elif "sterkly" in low:
            line = re.sub(
                r"Product Manager\s*/\s*Product Owner|Product Owner\s*/\s*Product Manager",
                "Product Manager",
                line,
                flags=re.I,
            )
        lines.append(line)
    return "\n".join(lines)


def project_id_for_claim(claim_id: str) -> str:
    m = re.match(r"^(ACC-\d+)", claim_id or "")
    return m.group(1) if m else (claim_id or "")


def _pick_diverse_claims(
    scored_pool: List[Tuple[str, float]],
    limit: int,
    *,
    diverse: bool = True,
) -> List[str]:
    """Pick top claims; optional one lens per ACC-10x project (Cision depth without repetition)."""
    picked: List[str] = []
    seen_projects: set[str] = set()
    for cid, _score in scored_pool:
        if diverse:
            pid = project_id_for_claim(cid)
            if pid in seen_projects:
                continue
            seen_projects.add(pid)
        picked.append(cid)
        if len(picked) >= limit:
            return picked
    for cid, _score in scored_pool:
        if cid in picked:
            continue
        picked.append(cid)
        if len(picked) >= limit:
            break
    return picked


def employer_for_claim_id(claim_id: str) -> str:
    """Tier 1: deterministic routing from workExperience.md ACC ranges."""
    if claim_id.startswith("ACC-2"):
        return "sterkly"
    if claim_id.startswith("ACC-3"):
        return "zero_to_sixty"
    if claim_id.startswith("ACC-1"):
        return "cision"
    # VOC-* / MET-* default to Cision-era platform context
    return "cision"


def bucket_claim_ids(valid_ids: Dict[str, str]) -> Dict[str, List[str]]:
    buckets: Dict[str, List[str]] = {e: [] for e in EMPLOYERS}
    for cid in valid_ids:
        buckets[employer_for_claim_id(cid)].append(cid)
    return buckets


def _jd_keyword_score(jd_lower: str, text: str) -> int:
    words = set(re.findall(r"[a-z]{4,}", jd_lower))
    text_l = text.lower()
    return sum(1 for w in words if w in text_l)


def select_claims_deterministic(
    jd_text: str,
    valid_ids: Dict[str, str],
    per_employer: int | None = None,
    quotas: Dict[str, int] | None = None,
) -> List[str]:
    """Tier 2 fallback: keyword relevance per employer, no LLM."""
    quotas = quotas or resume_bullet_quotas()
    jd_lower = jd_text.lower()
    buckets = bucket_claim_ids(valid_ids)
    selected: List[str] = []
    for employer in EMPLOYERS:
        target = quotas.get(employer, per_employer or 3)
        ranked = sorted(
            buckets[employer],
            key=lambda cid: _jd_keyword_score(jd_lower, valid_ids.get(cid, "")),
            reverse=True,
        )
        scored = [(cid, float(i)) for i, cid in enumerate(ranked)]
        selected.extend(
            _pick_diverse_claims(scored, target, diverse=(employer == "cision"))
        )
    return list(dict.fromkeys(selected))


def _call_llm_claim_select(system: str, user: str, **kwargs):
    from llm_stages import call_llm_stage
    return call_llm_stage("claim_select", system, user, **kwargs)


def select_claims_per_employer_local(
    jd_text: str,
    valid_ids: Dict[str, str],
    call_llm_fn=None,
    per_employer: int | None = None,
    quotas: Dict[str, int] | None = None,
) -> List[str]:
    """Tier 2 Vector Search: Use local embeddings to rank claims via cosine similarity."""
    import os
    import json
    import sys
    from utils import DATA_DIR
    from local_embeddings import get_embedding, cosine_similarity

    quotas = quotas or resume_bullet_quotas()
    buckets = bucket_claim_ids(valid_ids)
    selected: List[str] = []
    
    # Load claim embeddings
    claim_embeddings = {}
    cache_path = os.path.join(DATA_DIR, "claim_embeddings.json")
    try:
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                claim_embeddings = json.load(f)
    except Exception as e:
        print(f"    [Vector Search] Failed to load claim embeddings: {e}", file=sys.stderr)
        
    if not claim_embeddings:
        print("    [Vector Search] No embeddings cache found. Falling back to keyword search.", file=sys.stderr)
        return select_claims_deterministic(jd_text, valid_ids, per_employer, quotas)

    jd_embedding = get_embedding(jd_text[:3000])

    if not jd_embedding:
        print("    [Vector Search] JD embedding failed. Falling back to keyword search.", file=sys.stderr)
        return select_claims_deterministic(jd_text, valid_ids, per_employer, quotas)

    for employer in EMPLOYERS:
        pool = buckets[employer]
        if not pool:
            continue

        target = quotas.get(employer, per_employer or 3)
        scored_pool = []
        for cid in pool:
            emb = claim_embeddings.get(cid)
            if emb:
                score = cosine_similarity(jd_embedding, emb)
                scored_pool.append((cid, score))
            else:
                scored_pool.append((cid, -1.0))

        scored_pool.sort(key=lambda x: x[1], reverse=True)
        picked = _pick_diverse_claims(
            scored_pool, target, diverse=(employer == "cision")
        )

        if len(picked) < target:
            fallback = select_claims_deterministic(jd_text, valid_ids, quotas=quotas)
            for cid in fallback:
                if employer_for_claim_id(cid) == employer and cid not in picked:
                    picked.append(cid)
                if len(picked) >= target:
                    break

        selected.extend(picked[:target])

    return list(dict.fromkeys(selected))


_SOURCE_VERB = re.compile(
    r"\b(led|managed|built|designed|implemented|delivered|drove|created|established|"
    r"reduced|improved|scaled|launched|owned|partnered|integrated|resolved|stabilized)\b",
    re.I,
)


def _verb_allowed(source_text: str, bullet: str) -> bool:
    """First word of bullet should align with a verb used in source (CR-021)."""
    src_verbs = {m.group(1).lower() for m in _SOURCE_VERB.finditer(source_text)}
    if not src_verbs:
        return True
    first = bullet.strip().split()[0].lower().rstrip(".,;:")
    return first in src_verbs or any(first.startswith(v[:4]) for v in src_verbs)


def validate_bullet_for_local(source_text: str, bullet: str) -> Tuple[bool, Optional[str]]:
    """Tier 3 gates: numeric grounding + blocked tools + seniority + length."""
    valid, err = _verify_bullet_local(source_text, bullet)
    if not valid:
        return False, err

    if not _verb_allowed(source_text, bullet):
        return False, "Action verb not grounded in source claim"

    lower = bullet.lower()
    for tool in BLOCKED_TOOLS:
        pat = r"(?<![\w-])" + re.escape(tool.lower()) + r"(?![\w-])"
        if re.search(pat, lower):
            return False, f"Blocked tool: {tool}"

    for phrase in SENIORITY_INFLATION_PHRASES:
        if phrase in lower:
            return False, f"Seniority inflation: {phrase}"

    from tone_guard import tone_violations

    tone_hits = tone_violations(bullet)
    if tone_hits:
        return False, f"Blocked tone (FR-096): {tone_hits[0]}"

    if len(bullet.split()) > MAX_BULLET_WORDS:
        return False, f"Exceeds {MAX_BULLET_WORDS} words"

    if not re.match(r"^[A-Za-z]", bullet.strip()):
        return False, "Must start with action verb"

    return True, None


def ensure_minimum_bullets_per_employer(
    bullets: Dict[str, str],
    valid_ids: Dict[str, str],
    jd_text: str,
    fallback_bullet_fn,
    min_per: int = MIN_BULLETS_PER_EMPLOYER,
) -> Dict[str, str]:
    """Backward-compatible wrapper — pads to resume_bullet_quotas targets."""
    return ensure_employer_quotas(bullets, valid_ids, jd_text, fallback_bullet_fn)


def ensure_employer_quotas(
    bullets: Dict[str, str],
    valid_ids: Dict[str, str],
    jd_text: str,
    fallback_bullet_fn,
    quotas: Dict[str, int] | None = None,
) -> Dict[str, str]:
    """Pad composed bullets until each employer hits quota (default 5 / 3 / 3)."""
    quotas = quotas or resume_bullet_quotas()
    grouped_ids: Dict[str, List[str]] = {e: [] for e in EMPLOYERS}
    for cid in bullets:
        grouped_ids[employer_for_claim_id(cid)].append(cid)

    buckets = bucket_claim_ids(valid_ids)
    jd_lower = jd_text.lower()
    extra_ranked = select_claims_deterministic(jd_text, valid_ids, quotas=quotas)

    for employer in EMPLOYERS:
        target = quotas.get(employer, 3)
        while len(grouped_ids[employer]) < target:
            pool = sorted(
                buckets[employer],
                key=lambda cid: _jd_keyword_score(jd_lower, valid_ids.get(cid, "")),
                reverse=True,
            )
            candidates = pool + [
                c for c in extra_ranked if employer_for_claim_id(c) == employer
            ]
            added = False
            used_projects = {project_id_for_claim(c) for c in grouped_ids[employer]}
            for cid in candidates:
                if cid in bullets or cid not in valid_ids:
                    continue
                if employer == "cision" and project_id_for_claim(cid) in used_projects:
                    continue
                bullets[cid] = fallback_bullet_fn(valid_ids[cid])
                grouped_ids[employer].append(cid)
                used_projects.add(project_id_for_claim(cid))
                added = True
                break
            if not added:
                break
    return bullets


def _summary_proof_from_bullet(bullet: str, max_chars: int = SUMMARY_PROOF_MAX_CHARS) -> str:
    """
    One grounded proof clause for the summary: must be a substring of the bullet.
    Strips compose bridge prefixes and caps length so the summary block is never mid-word truncated.
    """
    b = bullet.strip()
    if not b:
        return ""

    if re.match(r"^[^:]{8,44}:\s", b):
        after_bridge = b.split(":", 1)[1].strip()
        if len(after_bridge) >= 24:
            b = after_bridge

    clauses: List[str] = []
    for piece in re.split(r"(?<=[.])\s+", b):
        piece = piece.strip()
        if piece:
            clauses.append(piece.split(".")[0].strip())
    if not clauses:
        clauses = [b.split(".")[0].strip()]

    def _prefer_metric(clause: str) -> bool:
        return bool(re.search(r"\d", clause))

    ordered = sorted(clauses, key=lambda c: (0 if _prefer_metric(c) else 1, len(c)))

    def _finalize(clause: str) -> str:
        clause = clause.strip()
        if not clause:
            return ""
        if clause[0].islower():
            clause = clause[0].upper() + clause[1:]
        return clause if clause.endswith(".") else f"{clause}."

    complete = [c for c in ordered if c and len(c) <= max_chars]
    if complete:
        return _finalize(max(complete, key=len))

    for clause in ordered:
        if not clause:
            continue
        trimmed = clause[:max_chars].rsplit(" ", 1)[0].strip()
        while trimmed and _INCOMPLETE_PROOF_TAIL.search(_finalize(trimmed)):
            trimmed = trimmed.rsplit(" ", 1)[0].strip()
        if len(trimmed) >= 40:
            return _finalize(trimmed)
    return ""


def _first_metric_clause(bullet: str) -> str:
    """Backward-compatible alias."""
    return _summary_proof_from_bullet(bullet)


def build_summary_deterministic(
    bullets_by_company: Dict[str, List[str]],
    jd_text: str,
    profile=None,
    fit_summary: str = "",
) -> str:
    """Tier 4 v3: 3–4 grounded sentences; Cision bullets drive proof (no LLM)."""
    from local_embeddings import BM25

    cision_bullets = list(bullets_by_company.get("cision", []))
    all_bullets = [b for bl in bullets_by_company.values() for b in bl]

    top_cision = None
    second_cision = None
    if cision_bullets:
        if jd_text:
            bm25 = BM25(cision_bullets)
            hits = bm25.get_top_n(jd_text, n=min(2, len(cision_bullets)))
            if hits:
                top_cision = cision_bullets[hits[0][0]]
                if len(hits) > 1:
                    second_cision = cision_bullets[hits[1][0]]
        if not top_cision:
            top_cision = cision_bullets[0]
        if not second_cision and len(cision_bullets) > 1:
            second_cision = cision_bullets[1]

    blocked = {"zenoti", "airo", "spa", "medical aesthetics"}
    themes: List[str] = []
    if profile and getattr(profile, "priority_themes", None):
        themes = [
            t for t in profile.priority_themes[:4]
            if not any(b in t.lower() for b in blocked)
        ][:3]

    if themes:
        from cover_prose import format_themes_for_prose, _short_theme_label

        theme_phrase = format_themes_for_prose(themes, max_items=2)
        s1 = f"B2B SaaS Product Manager with 6+ years in {theme_phrase}."
    else:
        s1 = (
            "B2B SaaS Product Manager with 6+ years stabilizing revenue-bearing platforms "
            "and cross-functional delivery."
        )

    s2 = (
        "Experienced partnering with engineering, DevOps, and customer-facing teams "
        "to ship reliable platform capabilities under resource constraints."
    )
    if themes and len(themes) > 2:
        from cover_prose import _short_theme_label

        third = _short_theme_label(themes[2])
        if len(third) > 55:
            third = third[:52].rsplit(" ", 1)[0]
        s2 = f"Focused on {third} in complex legacy B2B SaaS environments."

    sentences = [s1, s2]

    def _append_proof(bullet: str) -> bool:
        proof = _summary_proof_from_bullet(bullet)
        if not proof:
            return False
        joined = " ".join(sentences).lower()
        if proof.lower() in joined:
            return False
        trial = " ".join(sentences + [proof])
        ok, _ = assert_summary_grounded(trial, bullets_by_company)
        if not ok:
            return False
        sentences.append(proof)
        return True

    def _append_proof_from_pool(pool: List[str]) -> bool:
        for bullet in pool:
            if _append_proof(bullet):
                return True
        return False

    if top_cision:
        if not _append_proof(top_cision):
            _append_proof_from_pool([b for b in cision_bullets if b != top_cision])

    if len(sentences) < 4 and second_cision and second_cision != top_cision:
        _append_proof(second_cision)
    if len(sentences) < 4 and cision_bullets:
        _append_proof_from_pool(cision_bullets)

    fit_clean = (fit_summary or "").strip()
    try:
        from pipeline_env import allow_fit_summary
    except ImportError:
        allow_fit_summary = lambda: False  # type: ignore

    if allow_fit_summary() and fit_clean and len(fit_clean) > 20 and len(sentences) < 4:
        fit_sent = fit_clean.split(".")[0].strip()
        if len(fit_sent) > SUMMARY_PROOF_MAX_CHARS:
            fit_sent = fit_sent[:SUMMARY_PROOF_MAX_CHARS].rsplit(" ", 1)[0]
        if fit_sent and not fit_sent.endswith("."):
            fit_sent += "."
        ok_fit, _ = assert_summary_grounded(fit_sent, bullets_by_company)
        if ok_fit:
            sentences.append(fit_sent)

    summary = " ".join(sentences[:4])
    ok, _ = assert_summary_grounded(summary, bullets_by_company)
    if not ok:
        summary = " ".join(sentences[:2])
        for extra in sentences[2:4]:
            trial = f"{summary} {extra}".strip()
            if assert_summary_grounded(trial, bullets_by_company)[0]:
                summary = trial

    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", summary.strip()) if p.strip()]
    while len(summary) > SUMMARY_MAX_CHARS and len(parts) > SUMMARY_MIN_SENTENCES:
        parts.pop()
        summary = " ".join(parts)

    if len(parts) < SUMMARY_MIN_SENTENCES and cision_bullets:
        _append_proof_from_pool(cision_bullets)
        summary = " ".join(sentences[:4])
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", summary.strip()) if p.strip()]
        while len(summary) > SUMMARY_MAX_CHARS and len(parts) > SUMMARY_MIN_SENTENCES:
            parts.pop()
            summary = " ".join(parts)

    return summary


def assert_summary_grounded(summary: str, bullets_by_company: Dict[str, List[str]]) -> Tuple[bool, Optional[str]]:
    """Summary metric clauses must be substrings of selected bullets (CR-021)."""
    corpus = " ".join(b for bl in bullets_by_company.values() for b in bl)
    if not corpus.strip():
        return True, None
    ok_nums, err = audit_text_against_bullet_corpus(summary, corpus)
    if not ok_nums:
        return False, err
    # Only verify metric-bearing fragments (not tenure boilerplate like "6+ years")
    for frag in re.findall(r"[^.!?]*\d[^.!?]*[.!?]?", summary):
        frag_c = frag.strip()
        if len(frag_c) < 8:
            continue
        if re.search(r"\b6\+\s*years\b", frag_c, re.I):
            continue
        if not re.search(r"(\$|\d{2,}|\d+%|\d+\s*(?:accounts|users))", frag_c, re.I):
            continue
        if frag_c.lower() in corpus.lower():
            continue
        if any(frag_c.lower() in b.lower() for b in corpus.split(".")):
            continue
        return False, f"Summary fragment not grounded: {frag_c[:60]}"
    return True, None


def _extract_job_title(jd_text: str) -> str:
    patterns = (
        r"seeking a\s+([^.\n]{8,72}?)(?:\s+to\s+|\s+who\s+|\s+that\s+|\.)",
        r"looking for a\s+([^.\n]{8,72}?)(?:\s+to\s+|\s+who\s+|\s+that\s+|\.)",
        r"hiring a\s+([^.\n]{8,72}?)(?:\s+to\s+|\s+who\s+|\.)",
    )
    for pat in patterns:
        m = re.search(pat, jd_text, re.I)
        if m:
            title = re.sub(r"\s+", " ", m.group(1).strip())
            if 8 <= len(title) <= 72:
                return title
    if re.search(r"\bproduct manager\b", jd_text, re.I):
        return "Product Manager"
    return "Product Manager"


def _jd_goal_phrase(profile, jd_text: str) -> str:
    jd_l = jd_text.lower()
    if "ranking" in jd_l or "list franchise" in jd_l or "intelligence platform" in jd_l:
        return "scaling rankings and intelligence platform capabilities"
    if "monetiz" in jd_l:
        return "unlocking monetization through scalable platform delivery"
    if profile and profile.requirements:
        req = profile.requirements[0].strip()
        if len(req) > 95:
            req = req[:92].rsplit(" ", 1)[0]
        if req:
            return req[0].lower() + req[1:] if req[0].isupper() else req
    if profile and len(profile.priority_themes) > 2:
        return profile.priority_themes[2]
    return "delivering measurable platform and cross-functional outcomes"


def _jd_hook_sentence(jd_text: str, company_name: str, profile=None) -> str:
    from pipeline_env import cover_hook_mode
    from utils import call_llm

    if cover_hook_mode() != "template" and jd_text:
        system_prompt = (
            "You are a professional technical recruiter writing an opening hook for a cover letter for Jason Taylor. "
            "Write exactly ONE sentence. "
            f"Format strictly: 'I am applying for the [Job Title] role at {company_name}, where my background in [1-2 key skills from JD] aligns with your focus on [1 key goal from JD].' "
            "Do not include any greeting or signature. Output ONLY the single sentence."
        )
        try:
            custom_hook = call_llm(
                system_prompt,
                f"JD Text:\n{jd_text[:4000]}",
                temperature=0.0,
                provider_override=["local"],
            )
            if custom_hook and custom_hook.startswith("I am") and len(custom_hook) < 300:
                hook = custom_hook.strip()
                ok, err = audit_text_against_bullet_corpus(
                    hook, jd_text[:2000]
                )
                if ok:
                    return hook
        except Exception as e:
            import sys
            print(f"    [Local Draft Warning] Failed to generate custom cover letter hook: {e}", file=sys.stderr)

    # Template / keyword extraction (FR-131): role title + themes + JD-specific goal
    from cover_prose import format_themes_for_prose

    if profile and getattr(profile, "priority_themes", None):
        theme_str = format_themes_for_prose(profile.priority_themes, max_items=2)
    else:
        from jd_tailoring import THEME_KEYWORDS

        jd_lower = jd_text.lower()
        themes = []
        for kw, phrase in THEME_KEYWORDS:
            if kw in jd_lower and phrase not in themes:
                themes.append(phrase)
        theme_str = (
            format_themes_for_prose(themes, max_items=2)
            if themes
            else "B2B SaaS product execution"
        )

    title = _extract_job_title(jd_text)
    goal = _jd_goal_phrase(profile, jd_text)
    return (
        f"I am applying for the {title} role at {company_name}, where my background in "
        f"{theme_str} aligns with your focus on {goal}."
    )


def assemble_cover_letter_deterministic(
    company_name: str,
    jd_text: str,
    bullets: Dict[str, str],
    header_block: str,
    proof_bullets: Optional[List[str]] = None,
    profile=None,
) -> str:
    """Tier 5: four paragraphs; body sentences are approved bullets only."""
    from claim_composer import format_cover_proof_sentence

    raw_proof = proof_bullets or list(bullets.values())[:4]
    proof = [format_cover_proof_sentence(b) for b in raw_proof if b and b.strip()]
    proof = [p for p in proof if p]
    if len(proof) < 2:
        raise ValueError("Need at least 2 validated bullets for cover letter")

    from tone_guard import sanitize_submission_tone

    paras = [
        sanitize_submission_tone(_jd_hook_sentence(jd_text, company_name, profile)),
        sanitize_submission_tone(proof[0]),
        sanitize_submission_tone(proof[1] if len(proof) > 1 else proof[0]),
    ]
    paras.append(
        "I would welcome the chance to discuss how this experience maps to your team's goals. "
        "Thank you for your consideration."
    )
    body = "\n\n".join(paras)
    header = header_block.strip() if header_block.strip() else (
        "# JASON TAYLOR\n\n"
        "San Diego, CA | [REDACTED_PHONE] | [REDACTED_EMAIL] | linkedin.com/in/redacted-linkedin-slug"
    )
    return f"{header}\n\n{body}\n"


def audit_text_against_bullet_corpus(text: str, bullet_corpus: str) -> Tuple[bool, Optional[str]]:
    """Tier 6: any multi-digit number in final doc must appear in bullet corpus."""
    corpus_nums = extract_numeric_tokens(bullet_corpus.replace(",", ""))
    text_nums = extract_numeric_tokens(text.replace(",", ""))
    invented = {n for n in text_nums if len(n) > 1 and n not in corpus_nums}
    # allow common tenure and contact-header fragments [REDACTED_PHONE])
    invented -= {"2017", "2018", "2019", "2021", "2026", "760", "317", "8264"}
    if invented:
        return False, f"Document introduces numbers not in bullet corpus: {sorted(invented)}"
    return True, None


def enforce_resume_char_budget(content: str, max_chars: int = RESUME_CHAR_BUDGET) -> str:
    """Last-resort trim: drop bullet lines from end of file (never summary/header)."""
    if len(content) <= max_chars:
        return content
    lines = content.split("\n")
    bullet_idxs = [i for i, ln in enumerate(lines) if ln.startswith("* ")]
    while len("\n".join(lines)) > max_chars and bullet_idxs:
        lines.pop(bullet_idxs.pop())
    return "\n".join(lines).strip() + "\n"


def count_bullets_by_employer(content: str) -> Dict[str, int]:
    """Count bullets under each employer section for QA."""
    counts = {e: 0 for e in EMPLOYERS}
    current = None
    for line in content.splitlines():
        low = line.lower()
        if "###" in line and "cision" in low:
            current = "cision"
        elif "###" in line and "sterkly" in low:
            current = "sterkly"
        elif "###" in line and ("zero" in low or "sixty" in low):
            current = "zero_to_sixty"
        elif line.startswith("* ") and current:
            counts[current] += 1
    return counts


