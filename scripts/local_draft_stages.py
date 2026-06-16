"""
Bite-sized local drafting stages (CR-013).

Tier 0–2 and 4–6 are deterministic. Tier 3 uses one LLM call per claim with fail-closed gates.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

from pipeline_env import resume_bullet_quotas

from candidate_context import primary_employer_slug
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

def _employers() -> tuple[str, ...]:
    from candidate_context import load_employers
    return load_employers()


EMPLOYERS = _employers()
MIN_BULLETS_PER_EMPLOYER = 2
MAX_BULLETS_PER_EMPLOYER = 5
RESUME_CHAR_BUDGET = 3800
SUMMARY_MAX_CHARS = 780
SUMMARY_MIN_SENTENCES = 3
SUMMARY_TEMPLATE_S3 = (
    "Known for translating complex constraints into prioritized roadmaps "
    "and measurable platform outcomes."
)
SUMMARY_MAX_PROOF_SENTENCES = 1
SUMMARY_PROOF_MAX_CHARS = 200
_ATTRIBUTION_PAYOFF_RE = re.compile(
    r",\s*producing a version reliable enough that[^.]+sought to adopt it\.?",
    re.IGNORECASE,
)
_INCOMPLETE_PROOF_TAIL = re.compile(
    r"\b(?:to|and|or|by|for|with|across|against|in|on|of|the|a|an)\s*\.$",
    re.I,
)
MAX_BULLET_WORDS = 28

def _employer_headers() -> Dict[str, str]:
    from candidate_context import load_employer_headers
    return load_employer_headers()


EMPLOYER_EXPERIENCE_HEADERS: Dict[str, str] = _employer_headers()


def experience_skeleton() -> Dict[str, str]:
    return dict(_employer_headers())


def normalize_employer_job_titles(text: str) -> str:
    """Enforce single canonical title per employer on ### experience lines."""
    zts_combined = (
        r"Product Owner\s*/\s*Account Manager",
        r"Account Manager\s*/\s*Product Owner",
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
    )
    lines: List[str] = []
    for line in text.split("\n"):
        low = line.lower()
        if line.strip().startswith("### ") and "/" in line:
            for pat in zts_combined:
                line = re.sub(pat, "Product Owner", line, flags=re.I)
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
    # Fallback fills remaining slots while still respecting project diversity.
    for cid, _score in scored_pool:
        if cid in picked:
            continue
        if diverse:
            pid = project_id_for_claim(cid)
            if pid in seen_projects:
                continue
            seen_projects.add(pid)
        picked.append(cid)
        if len(picked) >= limit:
            break
    return picked


def employer_for_claim_id(claim_id: str) -> str:
    """Tier 1: deterministic routing from master_claims employer field."""
    from candidate_context import employer_for_claim_id as _route
    return _route(claim_id)


def bucket_claim_ids(valid_ids: Dict[str, str]) -> Dict[str, List[str]]:
    buckets: Dict[str, List[str]] = {e: [] for e in EMPLOYERS}
    for cid in valid_ids:
        buckets[employer_for_claim_id(cid)].append(cid)
    return buckets


def _jd_keyword_score(jd_lower: str, text: str) -> int:
    words = set(re.findall(r"[a-z]{4,}", jd_lower))
    text_l = text.lower()
    base = sum(1 for w in words if w in text_l)
    metric_bonus = 3 if re.search(r"\d", text) else 0
    return base + metric_bonus


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
            _pick_diverse_claims(scored, target, diverse=(employer == primary_employer_slug()))
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
            body = valid_ids.get(cid, "")
            metric_bonus = 0.05 if re.search(r"\d", body) else 0.0
            if emb:
                score = cosine_similarity(jd_embedding, emb) + metric_bonus
                scored_pool.append((cid, score))
            else:
                scored_pool.append((cid, -1.0 + metric_bonus))

        scored_pool.sort(key=lambda x: x[1], reverse=True)
        picked = _pick_diverse_claims(
            scored_pool, target, diverse=(employer == primary_employer_slug())
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
            theme_first: List[str] = []
            try:
                from theme_primaries import primary_claim_ids_for_jd
                from jd_tailoring import build_jd_profile_deterministic

                prof = build_jd_profile_deterministic(jd_text)
                theme_first = [
                    c
                    for c in primary_claim_ids_for_jd(jd_text, prof, valid_ids)
                    if employer_for_claim_id(c) == employer
                ]
            except Exception:
                theme_first = []
            candidates = theme_first + pool + [
                c for c in extra_ranked if employer_for_claim_id(c) == employer
            ]
            added = False
            used_projects = {project_id_for_claim(c) for c in grouped_ids[employer]}
            for cid in candidates:
                if cid in bullets or cid not in valid_ids:
                    continue
                if employer == primary_employer_slug() and project_id_for_claim(cid) in used_projects:
                    continue
                bullets[cid] = fallback_bullet_fn(valid_ids[cid])
                grouped_ids[employer].append(cid)
                used_projects.add(project_id_for_claim(cid))
                added = True
                break
            if not added:
                break
    return bullets


_METRIC_COLLISION_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"40%\s*data\s*(?:failure|drop|ingestion|drop-off)", re.I),
    re.compile(r"critical cross-functional data remediation", re.I),
)


def dedupe_metric_collision_bullets(
    bullets: Dict[str, str],
    valid_ids: Dict[str, str],
    jd_text: str,
    profile=None,
) -> Dict[str, str]:
    """When two bullets share the same primary metric story, keep the higher-scored claim (FR-241)."""
    from jd_tailoring import JdProfile, score_claim_for_jd

    prof = profile or JdProfile()

    by_key: Dict[str, List[str]] = {}
    for cid, text in bullets.items():
        key = None
        for pat in _METRIC_COLLISION_PATTERNS:
            if pat.search(text):
                key = pat.pattern
                break
        if key:
            by_key.setdefault(key, []).append(cid)

    drop: set[str] = set()
    for cids in by_key.values():
        if len(cids) < 2:
            continue
        ranked = sorted(
            cids,
            key=lambda c: score_claim_for_jd(valid_ids.get(c, bullets.get(c, "")), prof, jd_text),
            reverse=True,
        )
        drop.update(ranked[1:])

    if drop:
        import sys
        print(
            f"    [Compiler] Metric dedupe: dropped {len(drop)} near-duplicate bullet(s).",
            file=sys.stderr,
        )
    return {cid: text for cid, text in bullets.items() if cid not in drop}


def ensure_experience_skeleton_headers(content: str, skeleton: Optional[Dict[str, str]] = None) -> str:
    """Replace bare ### Title | Company headers with full skeleton (dates + location) (FR-242)."""
    sk = skeleton or experience_skeleton()
    from candidate_context import employer_display_name, load_employers_ordered

    headers = _employer_headers()
    lines = content.splitlines()
    out: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("### ") and stripped.count("|") < 2:
            matched_slug = None
            for slug in load_employers_ordered():
                label = employer_display_name(slug, headers)
                if label.lower() in stripped.lower():
                    matched_slug = slug
                    break
            if matched_slug and matched_slug in sk:
                out.extend(sk[matched_slug].strip().splitlines())
                i += 1
                if (
                    i < len(lines)
                    and lines[i].strip()
                    and not lines[i].strip().startswith(("*", "###", "##"))
                    and not re.search(r"\d{4}", lines[i])
                ):
                    i += 1
                continue
        out.append(line)
        i += 1
    return "\n".join(out)


METRIC_BULLET_FLOOR = 4  # minimum number of experience bullets that must contain a digit


def enforce_metric_bullet_floor(
    bullets: Dict[str, str],
    valid_ids: Dict[str, str],
    jd_text: str,
    fallback_bullet_fn,
) -> Dict[str, str]:
    """Swap lowest-relevance non-metric bullets for metric-bearing alternatives (FR-214).

    If the selected bullet set has fewer than METRIC_BULLET_FLOOR bullets containing
    a digit, iteratively replace the lowest-JD-score non-metric bullet with the
    highest-JD-score unselected metric-bearing claim from the same employer.
    Only swaps when a better metric-bearing alternative actually exists.
    """
    jd_lower = jd_text.lower()

    def _score(text: str) -> int:
        return _jd_keyword_score(jd_lower, text)

    def _has_digit(text: str) -> bool:
        return bool(re.search(r"\d", text))

    swaps = 0
    for _ in range(6):
        metric_count = sum(1 for text in bullets.values() if _has_digit(text))
        if metric_count >= METRIC_BULLET_FLOOR:
            break

        selected_ids = set(bullets.keys())
        non_metric = [
            (cid, text) for cid, text in bullets.items() if not _has_digit(text)
        ]
        if not non_metric:
            break

        non_metric.sort(key=lambda x: _score(valid_ids.get(x[0], x[1])))
        swap_out_cid, _ = non_metric[0]
        swap_out_employer = employer_for_claim_id(swap_out_cid)

        candidates = [
            (cid, body)
            for cid, body in valid_ids.items()
            if cid not in selected_ids
            and employer_for_claim_id(cid) == swap_out_employer
            and _has_digit(body)
        ]
        if not candidates:
            break

        candidates.sort(key=lambda x: _score(x[1]), reverse=True)
        swap_in_cid, swap_in_body = candidates[0]

        if _score(swap_in_body) < _score(valid_ids.get(swap_out_cid, "")) - 5:
            break

        del bullets[swap_out_cid]
        bullets[swap_in_cid] = fallback_bullet_fn(swap_in_body)
        swaps += 1

    if swaps:
        import sys
        print(f"    [Compiler] Metric floor: swapped {swaps} bullet(s) to reach {METRIC_BULLET_FLOOR} metric bullets.", file=sys.stderr)

    return bullets


def _summary_proof_from_bullet(bullet: str, max_chars: int = SUMMARY_PROOF_MAX_CHARS) -> str:
    """
    One grounded proof clause for the summary: must be a substring of the bullet.
    Strips compose bridge prefixes and caps length so the summary block is never mid-word truncated.
    """
    from resume_conversion_eval import (
        is_incomplete_summary_sentence,
        is_participle_proof_fragment,
    )

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

    def _finalize(clause: str) -> str:
        clause = clause.strip()
        if not clause:
            return ""
        if clause[0].islower():
            clause = clause[0].upper() + clause[1:]
        return clause if clause.endswith(".") else f"{clause}."

    def _valid_proof(clause: str) -> bool:
        if not clause or len(clause) > max_chars:
            return False
        finalized = _finalize(clause)
        if is_incomplete_summary_sentence(finalized) or is_participle_proof_fragment(finalized):
            return False
        return True

    # Long single-sentence bullets: only add comma segments that pass completeness checks.
    # Skip parts that start with a digit — these are thousands-separator fragments
    # (e.g. "3,500 active accounts" splits into "3" and "500 active accounts", and
    # "500" is not a valid grounded metric — it doesn't match the bullet corpus value).
    if len(clauses) == 1 and "," in clauses[0]:
        comma_parts = [p.strip() for p in clauses[0].split(",") if p.strip()]
        for part in comma_parts:
            if part and part[0].isdigit():
                continue
            if _valid_proof(part):
                clauses.append(part)

    # Prefer full attribution sentence with adoption payoff when grounded in bullet.
    if clauses:
        full_sentence = clauses[0]
        if _ATTRIBUTION_PAYOFF_RE.search(b) and len(full_sentence) <= max_chars:
            finalized_full = _finalize(full_sentence)
            if not is_incomplete_summary_sentence(finalized_full) and not is_participle_proof_fragment(
                finalized_full
            ):
                return finalized_full
        payoff = _ATTRIBUTION_PAYOFF_RE.search(b)
        if payoff:
            lead = full_sentence.split(",")[0].strip() if "," in full_sentence else full_sentence
            extended = f"{lead}{payoff.group(0)}"
            if not extended.endswith("."):
                extended += "."
            if len(extended) <= max_chars and _valid_proof(extended.rstrip(".")):
                finalized_ext = _finalize(extended.rstrip("."))
                if not is_incomplete_summary_sentence(finalized_ext):
                    return finalized_ext

    ordered = sorted(clauses, key=lambda c: (0 if _prefer_metric(c) else 1, len(c)))

    complete = [c for c in ordered if _valid_proof(c)]
    if complete:
        chosen = _finalize(max(complete, key=len))
        payoff = _ATTRIBUTION_PAYOFF_RE.search(b)
        if payoff and "revenue outcomes" in chosen.lower() and "sought to adopt" not in chosen.lower():
            extended = chosen.rstrip(".") + payoff.group(0)
            if not extended.endswith("."):
                extended += "."
            if len(extended) <= max_chars:
                ext_final = _finalize(extended.rstrip("."))
                if not is_incomplete_summary_sentence(ext_final):
                    return ext_final
        return chosen

    return ""


def _first_metric_clause(bullet: str) -> str:
    """Backward-compatible alias."""
    return _summary_proof_from_bullet(bullet)


def _coalesce_summary_parts(
    parts: List[str],
    *,
    jd_text: str,
    proof_pool: List[str],
    bullets_by_company: Dict[str, List[str]],
    proof_fn,
) -> List[str]:
    """Keep template (2 sentences) + at most one valid proof; never stack multiple proofs."""
    from resume_conversion_eval import (
        is_incomplete_summary_sentence,
        is_participle_proof_fragment,
        score_summary_proof_candidate,
        summary_proof_overlaps_body,
    )

    body_bullets = [b for bl in bullets_by_company.values() for b in bl]
    template = [p for p in parts[:2] if p.strip()]
    proofs = [
        p
        for p in parts[2:]
        if p.strip()
        and not is_incomplete_summary_sentence(p)
        and not is_participle_proof_fragment(p)
    ]
    if proofs:
        proofs.sort(
            key=lambda p: score_summary_proof_candidate(p, jd_text, body_bullets),
            reverse=True,
        )
        return template + [proofs[0]]

    if len(template) >= 2:
        extra = proof_fn(proof_pool)
        if extra and not is_incomplete_summary_sentence(extra) and not is_participle_proof_fragment(extra):
            trial = " ".join(template + [extra])
            if assert_summary_grounded(trial, bullets_by_company)[0]:
                return template + [extra]
    return template


def _pad_summary_template_parts(parts: List[str], theme_phrase: Optional[str] = None) -> List[str]:
    """Pad to SUMMARY_MIN_SENTENCES with template-only s3 — never a second proof (FR-243)."""
    out = [p for p in parts if p.strip()]
    if len(out) >= SUMMARY_MIN_SENTENCES:
        return out[:SUMMARY_MIN_SENTENCES]
    if len(out) <= 2:
        s3 = SUMMARY_TEMPLATE_S3
        if theme_phrase:
            s3 = (
                f"Known for delivering measurable platform outcomes in {theme_phrase}, "
                f"with cross-functional execution across engineering and customer teams."
            )
        if s3 not in out:
            out.append(s3)
    return out[:SUMMARY_MIN_SENTENCES]


def _jd_metric_teaser_proof(
    proof_pool: List[str],
    body_bullets: List[str],
    jd_text: str = "",
) -> str:
    """Non-verbatim metric proof for rubric when clause extraction duplicates body (FR-250)."""
    from resume_conversion_eval import (
        is_incomplete_summary_sentence,
        is_participle_proof_fragment,
        summary_proof_overlaps_body,
    )

    for bullet in proof_pool:
        metric = re.search(
            r"\$[\d.]+[KMB]|\b\d{1,3}%|\b\d{3,}\+?\s*(?:accounts|users|customers)\b",
            bullet,
            re.I,
        )
        if not metric:
            continue
        val = metric.group(0).strip()
        proof = (
            f"Recent platform work spanned {val} in scope with measurable reliability "
            f"and cross-functional delivery outcomes."
        )
        if not proof.endswith("."):
            proof += "."
        if summary_proof_overlaps_body(proof, body_bullets, min_chars=36):
            continue
        if is_incomplete_summary_sentence(proof) or is_participle_proof_fragment(proof):
            continue
        return proof
    return ""


def build_summary_deterministic(
    bullets_by_company: Dict[str, List[str]],
    jd_text: str,
    profile=None,
    fit_summary: str = "",
    retry_opts: Optional[Dict] = None,
) -> str:
    """Tier 4 v3: 3–4 grounded sentences; primary employer bullets drive proof (no LLM)."""
    retry_opts = retry_opts or {}
    theme_skip = int(retry_opts.get("theme_skip") or 0)
    proof_skip = int(retry_opts.get("proof_skip") or 0)
    force_attribution_payoff = bool(retry_opts.get("force_attribution_payoff"))

    from candidate_context import primary_employer_slug
    from local_embeddings import BM25

    primary = primary_employer_slug()
    cision_bullets = list(bullets_by_company.get(primary, []))
    all_bullets = [b for bl in bullets_by_company.values() for b in bl]

    top_cision = None
    second_cision = None
    if cision_bullets:
        if jd_text:
            bm25 = BM25(cision_bullets)
            # Fetch up to 5 hits and reorder so metric-bearing bullets appear first
            n_hits = min(5, len(cision_bullets))
            hits = bm25.get_top_n(jd_text, n=n_hits)
            if hits:
                metric_hits = [h for h in hits if re.search(r"\d", cision_bullets[h[0]])]
                non_metric_hits = [h for h in hits if not re.search(r"\d", cision_bullets[h[0]])]
                ordered_hits = metric_hits + non_metric_hits
                top_cision = cision_bullets[ordered_hits[0][0]]
                if len(ordered_hits) > 1:
                    second_cision = cision_bullets[ordered_hits[1][0]]
        if not top_cision:
            top_cision = next(
                (b for b in cision_bullets if re.search(r"\d", b)), cision_bullets[0]
            )
        if not second_cision and len(cision_bullets) > 1:
            second_cision = next(
                (b for b in cision_bullets if b != top_cision and re.search(r"\d", b)),
                cision_bullets[1],
            )

    from conversion_framing import defensive_summary_violations, has_security_jd_signal
    from resume_conversion_eval import (
        is_incomplete_summary_sentence,
        is_participle_proof_fragment,
        score_summary_proof_candidate,
        summary_proof_overlaps_body,
    )

    all_body_bullets_flat = [b for bl in bullets_by_company.values() for b in bl]

    blocked = {"zenoti", "airo", "spa", "medical aesthetics"}
    themes: List[str] = []
    if profile and getattr(profile, "priority_themes", None):
        themes = [
            t for t in profile.priority_themes[:6]
            if not any(b in t.lower() for b in blocked)
        ]
    if not has_security_jd_signal(jd_text):
        themes = [
            t for t in themes
            if "security" not in t.lower() and "risk reduction" not in t.lower()
        ]

    bullet_corpus = " ".join(all_bullets)
    from experience_theme_guard import summary_focus_phrase

    theme_phrase = (
        summary_focus_phrase(themes, bullet_corpus, max_items=3, theme_skip=theme_skip)
        if themes
        else None
    )
    if theme_phrase:
        s1 = (
            f"Product Manager with 6+ years of experience across enterprise SaaS platforms, "
            f"technical workflows, and internal tooling, with recent focus on {theme_phrase}."
        )
    else:
        s1 = (
            "Product Manager with 6+ years of experience across enterprise SaaS platforms, "
            "technical workflows, and internal tooling, most recently maintaining a high-value "
            "enterprise platform through data integrity, customer migration, and infrastructure cost reduction."
        )

    s2 = (
        "Experienced partnering with engineering, DevOps, CX, and upgrade teams "
        "to ship reliable platform capabilities under resource constraints."
    )

    # Guard: prevent the 40% data failure stat from appearing in the proof
    # sentence when it is already present as an experience bullet (avoids verbatim duplication).
    _SUMMARY_STAT_BLOCKLIST = re.compile(
        r"40%\s*data\s*failure|40%\s*data\s*drop|40%\s*drop.off",
        re.IGNORECASE,
    )

    sentences = [s1, s2]

    def _proof_allowed(bullet: str, proof: str = "") -> bool:
        if has_security_jd_signal(jd_text):
            return True
        if defensive_summary_violations(bullet, jd_text):
            return False
        # Block stat-duplicating bullets from appearing in the summary proof
        # when the same stat already appears in an experience bullet.
        all_body_bullets = [b for bl in bullets_by_company.values() for b in bl]
        if proof and summary_proof_overlaps_body(proof, all_body_bullets):
            return False
        if _SUMMARY_STAT_BLOCKLIST.search(bullet):
            if any(_SUMMARY_STAT_BLOCKLIST.search(b) for b in all_body_bullets):
                return False
        # Block verbatim-copy proof sentences: use the extracted proof (shorter than
        # the full bullet) for token comparison so that a brief teaser of a long bullet
        # isn't blocked while a full-length copy is.
        check_text = proof if proof else bullet
        check_tokens = set(re.findall(r"[a-z]{4,}", check_text.lower()))
        if proof and bullet:
            pl = proof.lower().rstrip(".")
            bl = bullet.lower()
            if pl in bl and len(pl) / max(len(bl), 1) >= 0.65:
                return False
        if check_tokens:
            for body_b in all_body_bullets:
                body_tokens = set(re.findall(r"[a-z]{4,}", body_b.lower()))
                if not body_tokens:
                    continue
                overlap = len(check_tokens & body_tokens) / len(check_tokens)
                length_ratio = len(check_tokens) / max(1, len(body_tokens))
                # Block when proof is both high-overlap AND nearly as long as the
                # experience bullet (i.e. a near-verbatim copy, not a short teaser).
                if overlap >= 0.80 and length_ratio >= 0.70:
                    return False
        return True

    def _best_summary_proof(pool: List[str]) -> str:
        """Select one grounded proof sentence (FR-223): metric/outcome openers beat fragments."""
        if force_attribution_payoff:
            attr_pool = [b for b in pool if _ATTRIBUTION_PAYOFF_RE.search(b)]
            if attr_pool:
                pool = attr_pool
        ranked: List[tuple] = []
        for bullet in pool:
            proof = _summary_proof_from_bullet(bullet)
            if not proof or is_incomplete_summary_sentence(proof):
                continue
            if not _proof_allowed(bullet, proof):
                continue
            if not has_security_jd_signal(jd_text) and defensive_summary_violations(proof, jd_text):
                continue
            if is_participle_proof_fragment(proof):
                continue
            trial = " ".join(sentences + [proof])
            if not assert_summary_grounded(trial, bullets_by_company)[0]:
                continue
            ranked.append((score_summary_proof_candidate(proof, jd_text, all_body_bullets_flat), proof))
        if not ranked:
            for bullet in pool:
                proof = _summary_proof_from_bullet(bullet)
                if not proof or is_incomplete_summary_sentence(proof):
                    continue
                if not _proof_allowed(bullet, proof):
                    continue
                trial = " ".join(sentences + [proof])
                if assert_summary_grounded(trial, bullets_by_company)[0]:
                    ranked.append(
                        (score_summary_proof_candidate(proof, jd_text, all_body_bullets_flat), proof)
                    )
        if not ranked:
            return ""
        ranked.sort(key=lambda x: x[0], reverse=True)
        if proof_skip:
            ranked = ranked[proof_skip:]
        if not ranked:
            return ""
        metric_ranked = [(s, p) for s, p in ranked if re.search(r"\d", p)]
        if metric_ranked:
            return metric_ranked[0][1]
        return ranked[0][1]

    proof_pool: List[str] = []
    if top_cision:
        proof_pool.append(top_cision)
    if second_cision and second_cision != top_cision:
        proof_pool.append(second_cision)
    for b in cision_bullets:
        if b not in proof_pool:
            proof_pool.append(b)

    best_proof = _best_summary_proof(proof_pool)
    if best_proof:
        sentences.append(best_proof)

    if not has_security_jd_signal(jd_text):
        sentences = [
            s for s in sentences if not defensive_summary_violations(s, jd_text)
        ]

    sentences = sentences[: 2 + SUMMARY_MAX_PROOF_SENTENCES]
    if sentences and sentences[-1].rstrip().endswith(("allocations.", "allocations", "compliance.", "teams.")):
        sentences = sentences[:-1]

    fit_clean = (fit_summary or "").strip()
    try:
        from pipeline_env import allow_fit_summary
    except ImportError:
        allow_fit_summary = lambda: False  # type: ignore

    if allow_fit_summary() and fit_clean and len(fit_clean) > 20 and len(sentences) <= 2:
        fit_sent = fit_clean.split(".")[0].strip()
        if fit_sent and not fit_sent.endswith("."):
            fit_sent += "."
        if (
            fit_sent
            and not is_incomplete_summary_sentence(fit_sent)
            and not is_participle_proof_fragment(fit_sent)
        ):
            ok_fit, _ = assert_summary_grounded(fit_sent, bullets_by_company)
            if ok_fit:
                sentences.append(fit_sent)

    sentences = [
        s
        for s in sentences
        if not is_incomplete_summary_sentence(s) and not is_participle_proof_fragment(s)
    ]
    if len(sentences) > 2 + SUMMARY_MAX_PROOF_SENTENCES:
        template = sentences[:2]
        proofs = sentences[2:]
        proofs.sort(
            key=lambda p: score_summary_proof_candidate(p, jd_text, all_body_bullets_flat),
            reverse=True,
        )
        sentences = template + proofs[:SUMMARY_MAX_PROOF_SENTENCES]

    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", " ".join(sentences).strip()) if p.strip()]
    parts = _coalesce_summary_parts(
        parts,
        jd_text=jd_text,
        proof_pool=proof_pool,
        bullets_by_company=bullets_by_company,
        proof_fn=lambda pool: _best_summary_proof(pool),
    )
    while len(" ".join(parts)) > SUMMARY_MAX_CHARS and len(parts) > 2:
        if len(parts) > 2:
            parts = parts[:-1]
        else:
            break

    sents = [p.strip() for p in re.split(r"(?<=[.!?])\s+", " ".join(parts).strip()) if p.strip()]
    proof_sents = sents[2:]
    if proof_sents and summary_proof_overlaps_body(proof_sents[0], all_body_bullets_flat):
        teaser = _jd_metric_teaser_proof(proof_pool, all_body_bullets_flat, jd_text)
        summary = (
            " ".join(sents[:2] + [teaser])
            if teaser
            else " ".join(_pad_summary_template_parts(sents[:2], theme_phrase))
        )
    elif len(sents) < SUMMARY_MIN_SENTENCES:
        teaser = _jd_metric_teaser_proof(proof_pool, all_body_bullets_flat, jd_text)
        if teaser and len(sents) == 2 and assert_summary_grounded(
            " ".join(sents + [teaser]), bullets_by_company
        )[0]:
            summary = " ".join(sents + [teaser])
        else:
            summary = " ".join(_pad_summary_template_parts(sents, theme_phrase))
    else:
        summary = " ".join(sents)

    if not assert_summary_grounded(summary, bullets_by_company)[0]:
        summary = " ".join(_pad_summary_template_parts(parts[:2], theme_phrase))
    return summary


# ---------------------------------------------------------------------------
# Core Competencies section builder (FR-195)
# ---------------------------------------------------------------------------

_SKILL_LABELS: Dict[str, str] = {
    # Roadmap / planning
    "Roadmap": "Product Roadmap",
    "Roadmap Prioritization": "Product Roadmap",
    # Agile
    "Agile": "Agile / Scrum",
    "Agile Planning": "Agile / Scrum",
    "Agile Ceremonies": "Agile / Scrum",
    "PI Planning": "PI Planning",
    "Sprint Planning": "Sprint Planning",
    # Backlog
    "Backlog Grooming": "Backlog Management",
    "Backlog Management": "Backlog Management",
    "Backlog Prioritization": "Backlog Management",
    # Stakeholder / cross-functional
    "Stakeholder Management": "Stakeholder Management",
    "Cross-functional": "Cross-functional Alignment",
    "Cross-functional Alignment": "Cross-functional Alignment",
    "Organization-wide Alignment": "Stakeholder Management",
    # Requirements / specs
    "Requirements Gathering": "Requirements Gathering",
    "Product Specs": "PRD / Spec Writing",
    "Business Translation": "PRD / Spec Writing",
    "User Story Writing": "User Story Writing",
    "Synthesis": "Requirements Synthesis",
    # Capacity / planning
    "Capacity Modeling": "Capacity Planning",
    "Capacity Planning": "Capacity Planning",
    "Resource Allocation": "Resource Planning",
    # Platform / data / integration
    "Platform Stability": "Platform Stability",
    "Platform Stabilization": "Platform Stability",
    "Data Integrity": "Data Integrity",
    "Data Pipeline": "Data Pipeline Management",
    "Content Pipeline": "Content Pipeline Management",
    "Content Licensing": "Content Licensing",
    "API / Integration": "API & Integration",
    "Technical Product Management": "Technical Product Management",
    # Migration / retention
    "Migration Planning": "Migration Strategy",
    "Migrations": "Migration Strategy",
    "Customer Retention": "Customer Retention",
    "Retention": "Customer Retention",
    "Product Lifecycle": "Product Lifecycle Management",
    # Compliance / risk
    "Compliance": "Compliance Workflows",
    "Risk Mitigation": "Risk Management",
    "Change Management": "Change Management",
    "Privacy": "Privacy & Compliance",
    "GDPR/CCPA": "Privacy & Compliance",
    # Go-to-market / analytics
    "Go-to-Market": "Go-to-Market",
    "Competitive Analysis": "Competitive Analysis",
    "Executive Presentation": "Executive Communication",
    # Delivery / process
    "Prioritization": "Prioritization",
    "Process Improvement": "Process Improvement",
    "Process Optimization": "Process Improvement",
    "SDLC": "SDLC",
    "QA": "QA & Release",
    "Quality Assurance": "QA & Release",
    "Release Management": "QA & Release",
    # Engineering / technical collaboration
    "Engineering Alignment": "Engineering Collaboration",
    "Technical Problem Solving": "Technical Problem Solving",
    "Technical Resilience": "Technical Resilience",
}

_SKIP_TAGS: set = {
    # Outcomes (not skills)
    "Cost Reduction", "Cost Savings", "Revenue Protection", "Churn Prevention",
    "Churn Rate", "Churn Reduction", "ROI", "Conversion Rate", "Scaling",
    "Competitive Advantage", "Competitive Gap", "Feature Launch",
    "Product Adoption", "Product Continuity",
    # Too vague / not resume-ready
    "Velocity", "Collaboration", "Communication", "Continuity", "Initiative",
    "Problem Identification", "Delivery", "Alignment",
    # Too technical for PM row 1
    "macOS", "Scripting", "Automation", "Tooling", "GDPR/CCPA",
    "SLA", "Alerting", "Monitoring", "Access Control", "Governance",
    "ETL", "API Integration", "Platform Migration", "Platform Architecture",
    "Platform Scale", "Third-Party Integration", "Third-Party Terms",
    "Vendor Terms", "Vendor Management", "Vendor Failure Recovery",
    "Storage Optimization", "Infrastructure Deprecation", "Infrastructure",
    "Technical Debt", "Sunsetting", "Phased Rollout",
    "Operational Delivery", "Engineering Support", "Engineering Operations",
    "Operations", "CS Alignment", "Onboarding",
    # Already covered by tools row
    "Google Analytics", "Jira", "Salesforce", "CRM", "CRM Integration",
    "PR Attribution", "Global Coordination", "Distributed Teams",
    # Misc duplicates resolved above
    "Custom Requirements", "Multi-Platform Ownership",
}


def build_skills_section(
    bullets_with_ids: Dict[str, str],
    jd_text: str = "",
    profile=None,
) -> str:
    """Build the ## CORE COMPETENCIES two-row section (FR-195).

    Row 1: PM methodology skills harvested from the tags of selected claims.
           Sorted by (evidence frequency + JD requirements-section boost).
           Capped at 12 items.
    Row 2: Static verified tools from data/skills_catalog.json.
           Sorted by JD requirements-section token match.

    Returns empty string when no claims are selected (safe no-op).
    """
    import json
    import os
    from utils import PROJECT_ROOT

    if not bullets_with_ids:
        return ""

    # Load catalog to resolve claim IDs → tags
    try:
        from claim_catalog import load_catalog
        catalog = load_catalog()
        claims_data = catalog.claims if catalog.claims else {}
    except Exception:
        claims_data = {}

    # Get requirements subsection for JD-aware sorting
    from jd_tailoring import extract_req_section
    req_section = extract_req_section(jd_text) if jd_text else ""
    req_lower = req_section.lower()

    _GENERIC_TOKENS = {"technical", "literacy", "suite", "google", "microsoft"}

    def _jd_boost(label: str) -> int:
        tokens = re.findall(r"[a-z]{3,}", label.lower())
        filtered = [t for t in tokens if t not in _GENERIC_TOKENS]
        return sum(1 for t in filtered if t in req_lower)

    # Harvest tags from selected claims and count frequency
    tag_counts: Dict[str, int] = {}
    for cid in bullets_with_ids:
        claim = claims_data.get(cid)
        if not claim:
            continue
        tags = claim.tags if hasattr(claim, "tags") else (claim.get("tags", []) if isinstance(claim, dict) else [])
        for tag in tags:
            if tag not in _SKIP_TAGS:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # Map tags to display labels, merge duplicates, score by frequency + JD boost
    label_scores: Dict[str, int] = {}
    for tag, count in tag_counts.items():
        label = _SKILL_LABELS.get(tag, tag)
        score = count + _jd_boost(label) * 2
        if label not in label_scores or score > label_scores[label]:
            label_scores[label] = score

    row1_skills = sorted(label_scores.keys(), key=lambda l: -label_scores[l])[:10]

    if not row1_skills:
        return ""

    # Load static tools list
    skills_path = os.path.join(PROJECT_ROOT, "data", "skills_catalog.json")
    row2_tools: List[str] = []
    if os.path.exists(skills_path):
        try:
            with open(skills_path, encoding="utf-8") as f:
                sc = json.load(f)

            # Gather all tools from catalog, filtering to those anchored in
            # claim tags (evidence-backed) OR surfaced in the JD req section
            # (role-relevant). This prevents the full tool list from shipping
            # regardless of what bullets were actually selected.
            claim_tags_lower: set = set()
            if bullets_with_ids:
                try:
                    from claim_catalog import load_catalog
                    cat = load_catalog()
                    for cid in bullets_with_ids:
                        rec = cat.claims.get(cid)
                        if rec:
                            claim_tags_lower.update(t.lower() for t in rec.tags)
                except Exception:
                    pass

            req_lower = req_section.lower()
            all_tools: List[str] = []
            for category_tools in sc.values():
                if isinstance(category_tools, list):
                    for tool in category_tools:
                        tool_lower = tool.lower()
                        # Include if: present in req section OR mentioned in claim tags
                        # OR JD boost score > 0 (means req section matched something)
                        jd_hit = _jd_boost(tool) > 0
                        tag_hit = any(tl in tool_lower or tool_lower in tl for tl in claim_tags_lower)
                        if jd_hit or tag_hit:
                            all_tools.append(tool)

            # Floor: if filtering produces fewer than 4 tools, backfill with
            # the next highest-JD-scoring tools not already included.
            if len(all_tools) < 4:
                for category_tools in sc.values():
                    if isinstance(category_tools, list):
                        for tool in category_tools:
                            if tool not in all_tools:
                                all_tools.append(tool)
                            if len(all_tools) >= 4:
                                break
                    if len(all_tools) >= 4:
                        break

            def _tool_allowed(label: str) -> bool:
                return not any(
                    re.search(
                        r"(?<![\w-])" + re.escape(blocked) + r"(?![\w-])",
                        label,
                        re.I,
                    )
                    for blocked in BLOCKED_TOOLS
                )

            all_tools = [t for t in all_tools if _tool_allowed(t)]
            all_tools.sort(key=lambda t: -_jd_boost(t))
            row2_tools = all_tools[:8]  # cap at 8 to keep row visually balanced
        except Exception:
            pass

    parts = ["## CORE COMPETENCIES", ""]
    parts.append(" | ".join(row1_skills))
    if row2_tools:
        parts.append("")
        parts.append(" | ".join(row2_tools))
    parts.append("")
    return "\n".join(parts)


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
        from utils import load_identity_profile

        candidate_name = (load_identity_profile().get("name") or "the candidate").strip()
        system_prompt = (
            f"You are a professional technical recruiter writing an opening hook for a cover letter for {candidate_name}. "
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
    if header_block.strip():
        header = header_block.strip()
    else:
        from utils import format_contact_header_block
        header = format_contact_header_block().strip()
    return f"{header}\n\n{body}\n"


def audit_text_against_bullet_corpus(text: str, bullet_corpus: str) -> Tuple[bool, Optional[str]]:
    """Tier 6: any multi-digit number in final doc must appear in bullet corpus."""
    corpus_nums = extract_numeric_tokens(bullet_corpus.replace(",", ""))
    text_nums = extract_numeric_tokens(text.replace(",", ""))
    invented = {n for n in text_nums if len(n) > 1 and n not in corpus_nums}
    # allow common tenure digits and phone fragments from the configured contact header
    from utils import load_identity_profile
    phone_digits = re.sub(r"\D", "", load_identity_profile().get("phone", ""))
    phone_fragments = {phone_digits[i:i + 3] for i in range(0, len(phone_digits), 3)} if phone_digits else set()
    invented -= {"2017", "2018", "2019", "2021", "2026", *phone_fragments}
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


def build_projects_section(jd_text: str = "") -> str:
    """Build the optional PROJECTS section for AI/LLM-role JDs (FR-208).

    Reads data/projects_catalog.json and returns a formatted markdown block
    containing only entries where ai_relevant=True. Returns an empty string
    when no entries match or the catalog is missing.
    """
    import os

    from utils import PROJECT_ROOT

    catalog_path = os.path.join(PROJECT_ROOT, "data", "projects_catalog.json")
    try:
        with open(catalog_path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return ""

    MAX_PROJECTS = 3
    all_projects = [p for p in data.get("projects", []) if p.get("ai_relevant")]
    projects = sorted(all_projects, key=lambda p: p.get("priority", 99))[:MAX_PROJECTS]
    if not projects:
        return ""

    lines = ["## PROJECTS", ""]
    for proj in projects:
        name = proj.get("name", "")
        stack = proj.get("stack", "")
        outcome = proj.get("outcome", "")
        if not name or not outcome:
            continue
        lines.append(f"**{name}** | {stack}")
        lines.append(f"* {outcome}")
        lines.append("")

    if len(lines) <= 2:
        return ""

    return "\n".join(lines).rstrip() + "\n"


def count_bullets_by_employer(content: str) -> Dict[str, int]:
    """Count bullets under each employer section for QA."""
    from candidate_context import employer_display_name, load_employer_headers, load_employers

    employers = load_employers()
    counts = {e: 0 for e in employers}
    headers = load_employer_headers()
    current = None
    for line in content.splitlines():
        low = line.lower()
        if line.strip().startswith("### "):
            for slug in employers:
                name = employer_display_name(slug, headers).lower()
                if name in low or slug.replace("_", " ") in low:
                    current = slug
                    break
        elif line.startswith("* ") and current:
            counts[current] += 1
    return counts


