"""
Deterministic fixes for conversion critique failures (FR-228, FR-229, FR-230).

Maps fixable CW codes to summary/framing actions before strict gate or export.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

FIXABLE_CODES: frozenset[str] = frozenset(
    {"CW-009", "CW-011", "CW-012", "CW-013", "CW-014", "CW-015", "CW-016"}
)

REMEDIATION_HINTS: Dict[str, str] = {
    "CW-009": "PDF header order wrong — re-export; if persistent, check compile_single.py flex layout.",
    "CW-011": "Summary sentence incomplete — regen with grounded proof or shorten theme phrase.",
    "CW-012": "Sterkly lacks PM context — ensure developer/partnership bullet; check claim catalog.",
    "CW-013": "Multiple or fragment proof sentences — keep one outcome-led proof in summary.",
    "CW-014": "Summary theme not experience-backed — move JD-only theme to cover letter bridge.",
    "CW-015": "Attribution proof missing adoption payoff — use full Cision bullet clause when grounded.",
    "CW-016": "Summary proof duplicates experience bullet — pick different proof or use template s3.",
}


def extract_failing_codes(issues: List[str]) -> List[str]:
    """Return blocking CW codes present in critique issue strings."""
    found: List[str] = []
    for issue in issues or []:
        m = re.match(r"\[(CW-\d+)\]", issue)
        if m and m.group(1) in FIXABLE_CODES and m.group(1) not in found:
            found.append(m.group(1))
    return found


def has_fixable(critique: Dict[str, Any]) -> bool:
    if critique.get("pass"):
        return False
    codes = extract_failing_codes(critique.get("issues") or [])
    return bool(codes)


def format_critique_failure(
    critique: Dict[str, Any],
    retry_log: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Human-readable error for STRICT_CONVERSION_CRITIQUE."""
    codes = extract_failing_codes(critique.get("issues") or [])
    lines = [
        "Conversion critique failed (STRICT_CONVERSION_CRITIQUE=1).",
        f"Unresolved codes: {', '.join(codes) or 'unknown'}",
    ]
    for code in codes:
        hint = REMEDIATION_HINTS.get(code)
        if hint:
            lines.append(f"  [{code}] {hint}")
    for issue in (critique.get("issues") or [])[:5]:
        lines.append(f"  - {issue}")
    if retry_log:
        lines.append(f"Retry attempts: {len(retry_log)}")
        for entry in retry_log[-3:]:
            lines.append(
                f"  · attempt {entry.get('attempt')}: {entry.get('action')} "
                f"({', '.join(entry.get('codes', []))})"
            )
    return "\n".join(lines)


def apply_critique_fixes(
    failing_codes: List[str],
    *,
    bullets: Dict[str, str],
    valid_ids: Dict[str, str],
    jd_text: str,
    fallback_bullet_fn: Callable[..., str],
    retry_state: Dict[str, Any],
    attempt: int,
) -> Dict[str, Any]:
    """
    Apply deterministic fixes for fixable critique codes.

    Returns dict with changed, bullets, retry_opts, log_entry, and action flags
    for the compiler to rebuild summary / bullets_by_company / PDF.
    """
    codes = [c for c in failing_codes if c in FIXABLE_CODES]
    if not codes:
        return {
            "changed": False,
            "bullets": bullets,
            "log_entry": None,
            "rebuild_summary": False,
            "reframe_bullets": False,
            "pdf_only": False,
            "retry_opts": retry_state.get("retry_opts") or {},
        }

    actions: List[str] = []
    changed = False
    new_bullets = dict(bullets)
    retry_opts = dict(retry_state.get("retry_opts") or {})

    if "CW-012" in codes:
        from conversion_framing import enforce_conversion_framing

        reframed = enforce_conversion_framing(
            new_bullets, valid_ids, jd_text, fallback_bullet_fn
        )
        if reframed != new_bullets:
            new_bullets = reframed
        changed = True
        actions.append("reframe_sterkly")

    if "CW-014" in codes:
        retry_opts["theme_skip"] = retry_opts.get("theme_skip", 0) + 1
        changed = True
        actions.append("theme_skip")

    if "CW-015" in codes:
        retry_opts["force_attribution_payoff"] = True
        changed = True
        actions.append("force_attribution_payoff")

    if "CW-011" in codes or "CW-013" in codes or "CW-016" in codes:
        retry_opts["proof_skip"] = retry_opts.get("proof_skip", 0) + 1
        changed = True
        actions.append("proof_rotate")

    if "CW-016" in codes:
        changed = True
        actions.append("drop_dup_proof")

    pdf_only = False
    if "CW-009" in codes and not any(
        a in actions
        for a in (
            "reframe_sterkly",
            "theme_skip",
            "force_attribution_payoff",
            "proof_rotate",
            "drop_dup_proof",
        )
    ):
        actions.append("pdf_recompile_only")
        changed = True
        pdf_only = True

    retry_state["retry_opts"] = retry_opts

    log_entry = {
        "attempt": attempt,
        "codes": codes,
        "action": "+".join(actions) if actions else "none",
    }

    rebuild_summary = any(
        c in codes for c in ("CW-011", "CW-013", "CW-014", "CW-015", "CW-012", "CW-016")
    )

    return {
        "changed": changed,
        "bullets": new_bullets,
        "log_entry": log_entry,
        "rebuild_summary": rebuild_summary and not pdf_only,
        "reframe_bullets": "CW-012" in codes,
        "pdf_only": pdf_only,
        "retry_opts": retry_opts,
    }
