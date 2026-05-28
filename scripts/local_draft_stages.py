"""
Bite-sized local drafting stages (CR-013).

Tier 0–2 and 4–6 are deterministic. Tier 3 uses one LLM call per claim with fail-closed gates.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

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
RESUME_CHAR_BUDGET = 3200
MAX_BULLET_WORDS = 28


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


def select_claims_deterministic(jd_text: str, valid_ids: Dict[str, str], per_employer: int = 3) -> List[str]:
    """Tier 2 fallback: keyword relevance per employer, no LLM."""
    jd_lower = jd_text.lower()
    buckets = bucket_claim_ids(valid_ids)
    selected: List[str] = []
    for employer in EMPLOYERS:
        ranked = sorted(
            buckets[employer],
            key=lambda cid: _jd_keyword_score(jd_lower, valid_ids.get(cid, "")),
            reverse=True,
        )
        selected.extend(ranked[:per_employer])
    return selected


def _call_llm_claim_select(system: str, user: str, **kwargs):
    from llm_stages import call_llm_stage
    return call_llm_stage("claim_select", system, user, **kwargs)


def select_claims_per_employer_local(
    jd_text: str,
    valid_ids: Dict[str, str],
    call_llm_fn=None,
    per_employer: int = 3,
) -> List[str]:
    """Tier 2 Vector Search: Use local embeddings to rank claims via cosine similarity."""
    import os
    import json
    import sys
    from utils import DATA_DIR
    from local_embeddings import get_embedding, cosine_similarity
    
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
        return select_claims_deterministic(jd_text, valid_ids, per_employer)
        
    # Embed the JD requirements
    # We truncate JD slightly to avoid exceeding context window for embeddings
    jd_embedding = get_embedding(jd_text[:3000])
    
    if not jd_embedding:
        print("    [Vector Search] JD embedding failed. Falling back to keyword search.", file=sys.stderr)
        return select_claims_deterministic(jd_text, valid_ids, per_employer)

    for employer in EMPLOYERS:
        pool = buckets[employer]
        if not pool:
            continue
            
        # Score pool via cosine similarity
        scored_pool = []
        for cid in pool:
            emb = claim_embeddings.get(cid)
            if emb:
                score = cosine_similarity(jd_embedding, emb)
                scored_pool.append((cid, score))
            else:
                scored_pool.append((cid, -1.0))
                
        # Sort by score descending
        scored_pool.sort(key=lambda x: x[1], reverse=True)
        picked = [cid for cid, score in scored_pool[:per_employer]]
        
        if len(picked) < MIN_BULLETS_PER_EMPLOYER:
            fallback = select_claims_deterministic(jd_text, valid_ids, per_employer=per_employer)
            for cid in fallback:
                if employer_for_claim_id(cid) == employer and cid not in picked:
                    picked.append(cid)
                if len(picked) >= per_employer:
                    break
                    
        selected.extend(picked[:per_employer])
        
    return list(dict.fromkeys(selected))


def validate_bullet_for_local(source_text: str, bullet: str) -> Tuple[bool, Optional[str]]:
    """Tier 3 gates: numeric grounding + blocked tools + seniority + length."""
    valid, err = _verify_bullet_local(source_text, bullet)
    if not valid:
        return False, err

    lower = bullet.lower()
    for tool in BLOCKED_TOOLS:
        pat = r"(?<![\w-])" + re.escape(tool.lower()) + r"(?![\w-])"
        if re.search(pat, lower):
            return False, f"Blocked tool: {tool}"

    for phrase in SENIORITY_INFLATION_PHRASES:
        if phrase in lower:
            return False, f"Seniority inflation: {phrase}"

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
    """Pad with deterministic fallbacks from employer pools if selection under-filled."""
    grouped_ids: Dict[str, List[str]] = {e: [] for e in EMPLOYERS}
    for cid in bullets:
        grouped_ids[employer_for_claim_id(cid)].append(cid)

    buckets = bucket_claim_ids(valid_ids)
    extra = select_claims_deterministic(jd_text, valid_ids, per_employer=min_per + 1)

    for employer in EMPLOYERS:
        count = len(grouped_ids[employer])
        if count >= min_per:
            continue
        for cid in buckets[employer] + [i for i in extra if employer_for_claim_id(i) == employer]:
            if cid in bullets or cid not in valid_ids:
                continue
            bullets[cid] = fallback_bullet_fn(valid_ids[cid])
            grouped_ids[employer].append(cid)
            if len(grouped_ids[employer]) >= min_per:
                break
    return bullets


def _first_metric_clause(bullet: str) -> str:
    """One short proof line from a bullet without repeating the whole bullet."""
    m = re.search(
        r"(\$[\d,]+(?:\s*(?:M|million|K))?|\d{1,3}(?:,\d{3})+|\d+%|\~?\d+\s+accounts|\d+\s+users)",
        bullet,
        re.IGNORECASE,
    )
    if m:
        start = max(0, bullet.lower().find(m.group(0).lower()) - 40)
        snippet = bullet[start:].split(".")[0].strip()
        if len(snippet) > 120:
            snippet = snippet[:120].rsplit(" ", 1)[0]
        return snippet
    return bullet.split(".")[0][:120].strip()


def build_summary_deterministic(
    bullets_by_company: Dict[str, List[str]],
    jd_text: str,
    profile=None,
) -> str:
    """Tier 4 v2: themes + one metric proof. Uses BM25 to pick the best matching bullet."""
    from local_embeddings import BM25
    
    all_bullets = []
    for blist in bullets_by_company.values():
        all_bullets.extend(blist)
        
    top_bullet = None
    if all_bullets:
        if jd_text:
            bm25 = BM25(all_bullets)
            top_results = bm25.get_top_n(jd_text, n=1)
            if top_results:
                best_idx = top_results[0][0]
                top_bullet = all_bullets[best_idx]
        if not top_bullet:
            top_bullet = all_bullets[0]

    if profile and getattr(profile, "priority_themes", None):
        blocked = {"zenoti", "airo", "spa", "medical aesthetics"}
        themes = [
            t for t in profile.priority_themes[:4]
            if not any(b in t.lower() for b in blocked)
        ][:2]
        if themes:
            theme_intro = (
                "B2B SaaS Product Manager with 6+ years in "
                + themes[0]
                + (f" and {themes[1]}" if len(themes) > 1 else "")
                + "."
            )
        else:
            theme_intro = (
                "B2B SaaS Product Manager with 6+ years stabilizing revenue-bearing platforms "
                "and cross-functional delivery."
            )
    else:
        theme_intro = (
            "B2B SaaS Product Manager with 6+ years stabilizing revenue-bearing platforms "
            "and cross-functional delivery."
        )

    if top_bullet:
        proof = _first_metric_clause(top_bullet)
        summary = f"{theme_intro} {proof}."
    else:
        summary = theme_intro

    if len(summary) > 380:
        summary = summary[:377].rsplit(" ", 1)[0] + "."
    return summary


def _jd_hook_sentence(jd_text: str, company_name: str, profile=None) -> str:
    from utils import call_llm
    
    # Try local LLM first for a highly customized intro
    if jd_text:
        system_prompt = (
            "You are a professional technical recruiter writing an opening hook for a cover letter for Jason Taylor. "
            "Write exactly ONE sentence. "
            f"Format strictly: 'I am applying for the [Job Title] role at {company_name}, where my background in [1-2 key skills from JD] aligns with your focus on [1 key goal from JD].' "
            "Do not include any greeting or signature. Output ONLY the single sentence."
        )
        try:
            custom_hook = call_llm(system_prompt, f"JD Text:\n{jd_text[:4000]}", temperature=0.2)
            if custom_hook and custom_hook.startswith("I am") and len(custom_hook) < 300:
                return custom_hook.strip()
        except Exception as e:
            import sys
            print(f"    [Local Draft Warning] Failed to generate custom cover letter hook: {e}", file=sys.stderr)

    # Fallback to keyword extraction
    if profile and getattr(profile, "priority_themes", None):
        theme_str = ", ".join(profile.priority_themes[:2])
    else:
        jd_lower = jd_text.lower()
        themes = []
        for kw, phrase in (
            ("platform", "platform reliability and scale"),
            ("data", "data integrity and ingestion"),
            ("migration", "customer migration and retention"),
            ("security", "security backlog and risk reduction"),
            ("saas", "B2B SaaS product delivery"),
            ("roadmap", "roadmap prioritization and execution"),
        ):
            if kw in jd_lower:
                themes.append(phrase)
        theme_str = ", ".join(themes[:2]) if themes else "B2B SaaS product execution"
    return (
        f"I am applying for the opportunity at {company_name} where my background in {theme_str} "
        f"aligns with the role's priorities."
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
    from claim_composer import strip_bridge_prefix

    raw_proof = proof_bullets or list(bullets.values())[:4]
    proof = [strip_bridge_prefix(b) for b in raw_proof]
    if len(proof) < 2:
        raise ValueError("Need at least 2 validated bullets for cover letter")

    paras = [
        _jd_hook_sentence(jd_text, company_name, profile),
        proof[0],
        proof[1] if len(proof) > 1 else proof[0],
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
    if len(content) <= max_chars:
        return content
    lines = content.split("\n")
    trimmed = []
    total = 0
    for line in lines:
        if line.startswith("* ") and total + len(line) > max_chars - 200:
            continue
        trimmed.append(line)
        total += len(line) + 1
    return "\n".join(trimmed).strip() + "\n"


