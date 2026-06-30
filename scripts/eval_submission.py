"""
LLM-based submission evaluator + fixer.

Scores Resume.md and CoverLetter.md against the R1-R8 / C1-C5 rubric
in data/conversion_rubric.md. Optionally applies a one-pass fix for
NEEDS-ONE-PASS documents.

Usage:
    python scripts/eval_submission.py <company_slug>
    python scripts/eval_submission.py <company_slug> --fix
    python scripts/eval_submission.py <company_slug> --fix --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import call_llm, load_file, SUBMISSIONS_DIR, DATA_DIR, WORK_EXP_FILE

RUBRIC_FILE = os.path.join(DATA_DIR, "conversion_rubric.md")
PROMPT_FILE = os.path.join(
    os.path.dirname(os.path.dirname(DATA_DIR)),
    "Resource", "AI Reusable Prompts",
    "pm_resume_cover_letter_research_report.md"
)

FORBIDDEN_PHRASES = [
    "em dash", "—", "leverage", "passionate", "driven", "dynamic", "innovative",
    "seamless", "transformative", "synergy", "tapestry", "revolutionize",
    "proven track record", "I am excited to apply", "I am confident that",
    "Furthermore,", "Moreover,", "In addition,", "Additionally,"
]

EVAL_SYSTEM = (
    "You are a PM resume and cover letter evaluator. "
    "Score each document strictly against the provided rubric. "
    "Return only valid JSON. No markdown fences."
)

EVAL_JSON_SCHEMA = """
{
  "resume": {
    "total": <int 0-100>,
    "R1_ats_integrity": <int 0-10>,
    "R2_jd_alignment": <int 0-15>,
    "R3_top_third_signal": <int 0-15>,
    "R4_metric_quality": <int 0-20>,
    "R5_pm_craft_coverage": <int 0-15>,
    "R6_seniority_altitude": <int 0-10>,
    "R7_internal_consistency": <int 0-10>,
    "R8_b2b_saas_legibility": <int 0-5>,
    "verdict": "CONVERT-READY" or "NEEDS-ONE-PASS" or "NEEDS-REWORK",
    "blocking_issues": ["issue text"],
    "flags": {"R1": "flag or null", "R2": "flag or null", "R3": "flag or null",
               "R4": "flag or null", "R5": "flag or null", "R6": "flag or null",
               "R7": "flag or null", "R8": "flag or null"}
  },
  "cover_letter": {
    "total": <int 0-100>,
    "C1_opening_hook": <int 0-25>,
    "C2_proof_density": <int 0-25>,
    "C3_role_fit_logic": <int 0-20>,
    "C4_authenticity": <int 0-20>,
    "C5_length_structure": <int 0-10>,
    "verdict": "CONVERT-READY" or "NEEDS-ONE-PASS" or "NEEDS-REWORK",
    "blocking_issues": ["issue text"],
    "flags": {"C1": "flag or null", "C2": "flag or null", "C3": "flag or null",
               "C4": "flag or null", "C5": "flag or null"}
  }
}
"""

FIX_SYSTEM = (
    "You are a PM resume and cover letter editor. "
    "You fix specific issues listed, using ONLY evidence from the provided work history. "
    "Never invent metrics, claims, or accomplishments not in the work history. "
    "Never use: em dashes (—), 'leverage', 'passionate', 'driven', 'dynamic', 'innovative', "
    "'seamless', 'transformative', 'synergy', 'proven track record', 'I am excited to apply', "
    "'I am confident that', 'Furthermore', 'Moreover', 'In addition', 'Additionally'. "
    "No bullet points in cover letters. Return only the full fixed document text."
)


def _load_company_context(folder: str) -> str:
    rp_path = os.path.join(folder, "Research_Packet.json")
    if not os.path.isfile(rp_path):
        return ""
    try:
        data = json.loads(load_file(rp_path))
        mod_a = data.get("Module A", {})
        lines = []
        if mod_a.get("Core Mission/Values"):
            mv = mod_a["Core Mission/Values"]
            stated = mv.get("Stated", "") if isinstance(mv, dict) else str(mv)
            lines.append(f"Mission: {stated}")
        if mod_a.get("Problem Space"):
            lines.append(f"Problem: {mod_a['Problem Space']}")
        biz = mod_a.get("Business Model", {})
        if isinstance(biz, dict) and biz.get("Growth Stage"):
            lines.append(f"Stage: {biz['Growth Stage']}")
        return "\n".join(lines)
    except Exception:
        return ""


def _build_eval_prompt(rubric: str, jd: str, resume_md: str, cover_letter_md: str,
                       company_context: str) -> str:
    ctx_block = f"\nCOMPANY CONTEXT:\n{company_context}\n" if company_context else ""
    return f"""Score the resume and cover letter below against the rubric dimensions.

RUBRIC:
{rubric}
{ctx_block}
JOB DESCRIPTION:
{jd}

RESUME:
{resume_md}

COVER LETTER:
{cover_letter_md}

Return ONLY valid JSON (no markdown fences) matching this exact schema:
{EVAL_JSON_SCHEMA}

Rules:
- total must equal the sum of the sub-scores
- verdict must match the threshold: Resume 70+ = CONVERT-READY, 50-69 = NEEDS-ONE-PASS, <50 = NEEDS-REWORK
- verdict must match the threshold: Cover Letter 65+ = CONVERT-READY, 45-64 = NEEDS-ONE-PASS, <45 = NEEDS-REWORK
- blocking_issues: only list what keeps the document BELOW threshold. Empty list if CONVERT-READY.
- flags: per-dimension notes as specified in the rubric. null if no issue.
"""


def _build_fix_prompt(doc_type: str, document: str, blocking_issues: list[str],
                      jd: str, work_exp: str, company: str) -> str:
    issues_text = "\n".join(f"- {i}" for i in blocking_issues)
    if doc_type == "resume":
        instructions = (
            "Fix ONLY the bullets and sections causing the blocking issues below. "
            "Do not rewrite sections that are not flagged. "
            "Keep all metrics exact as stated in the work history. "
            "Use strong action verbs. Keep bullets 1-2 lines each."
        )
    else:
        instructions = (
            "Fix ONLY the specific issues listed below. "
            "Do not restate the resume. Keep 250-400 words total, 3-4 paragraphs, no bullets. "
            "Open with something specific about the company or role — not generic enthusiasm. "
            "Include 1-2 accomplishments that are directly relevant."
        )
    return f"""Fix this {doc_type} for {company}. Apply ONLY the changes needed to address the blocking issues.

WORK HISTORY (ground truth — all claims must trace here):
{work_exp[:6000]}

JOB DESCRIPTION:
{jd[:3000]}

BLOCKING ISSUES TO FIX:
{issues_text}

INSTRUCTIONS:
{instructions}

CURRENT DOCUMENT:
{document}

Return the full fixed document. No explanations, no markdown fences around the whole document.
"""


# ---------------------------------------------------------------------------
# Epic 8 — Fast pre-queue eval (C1 hook + C3 proof density only)
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field as _dc_field

FAST_EVAL_THRESHOLD = 0.65


@dataclass
class FastEvalResult:
    hook_score: float           # C1 score (0.0–1.0)
    proof_density_score: float  # C3 score (0.0–1.0)
    passed: bool                # True if both >= threshold
    failing_slots: list = _dc_field(default_factory=list)  # ["HOOK"] | ["PROOF_1"] | both


_FAST_EVAL_SYSTEM = (
    "You are a cover letter evaluator. "
    "Score only C1 (Opening Hook) and C3 (Proof Density) from the rubric. "
    "C1 = 0.0-1.0: Does the first paragraph reference a specific company or role detail? "
    "C3 = 0.0-1.0: Does the body include at least one accomplishment with a specific outcome? "
    "Return ONLY valid JSON: {\"C1\": <float>, \"C3\": <float>}. No other text."
)


def fast_eval_cl(cl_text: str, jd_profile=None) -> FastEvalResult:
    """Score C1 (hook) and C3 (proof density) in one LLM call (Story 8.1)."""
    themes = ""
    if jd_profile:
        theme_list = getattr(jd_profile, "priority_themes", [])
        themes = f"\nJD themes: {', '.join(theme_list[:3])}" if theme_list else ""

    prompt = (
        f"Score this cover letter on C1 and C3 only.{themes}\n\n"
        f"COVER LETTER:\n{cl_text[:3000]}\n\n"
        "Return JSON: {\"C1\": <0.0-1.0>, \"C3\": <0.0-1.0>}"
    )

    raw = call_llm(
        system_prompt=_FAST_EVAL_SYSTEM,
        user_prompt=prompt,
        temperature=0.1,
        response_mime_type="application/json",
    )

    c1, c3 = 0.5, 0.5
    if raw:
        try:
            import json as _json
            cleaned = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            data = _json.loads(cleaned)
            c1 = float(data.get("C1", 0.5))
            c3 = float(data.get("C3", 0.5))
        except Exception:
            pass

    c1 = max(0.0, min(1.0, c1))
    c3 = max(0.0, min(1.0, c3))
    failing = []
    if c1 < FAST_EVAL_THRESHOLD:
        failing.append("HOOK")
    if c3 < FAST_EVAL_THRESHOLD:
        failing.append("PROOF_1")

    return FastEvalResult(
        hook_score=c1,
        proof_density_score=c3,
        passed=len(failing) == 0,
        failing_slots=failing,
    )


def evaluate(slug: str, verbose: bool = False) -> dict | None:
    folder = os.path.join(SUBMISSIONS_DIR, slug)
    if not os.path.isdir(folder):
        print(f"[ERROR] Folder not found: {folder}")
        return None

    resume_path = os.path.join(folder, "Resume.md")
    cl_path = os.path.join(folder, "CoverLetter.md")
    jd_path = os.path.join(folder, "Original_JD.txt")

    for path, label in [(resume_path, "Resume.md"), (cl_path, "CoverLetter.md"),
                        (jd_path, "Original_JD.txt")]:
        if not os.path.isfile(path):
            print(f"[SKIP] {slug}: missing {label}")
            return None

    rubric = load_file(RUBRIC_FILE)
    jd = load_file(jd_path)
    resume_md = load_file(resume_path)
    cover_letter_md = load_file(cl_path)
    company_context = _load_company_context(folder)

    if not rubric:
        print(f"[ERROR] Cannot load rubric: {RUBRIC_FILE}")
        return None

    prompt = _build_eval_prompt(rubric, jd, resume_md, cover_letter_md, company_context)

    print(f"  [eval] Scoring {slug}...", end=" ", flush=True)
    raw = call_llm(
        system_prompt=EVAL_SYSTEM,
        user_prompt=prompt,
        temperature=0.1,
        response_mime_type="application/json",
    )

    if not raw:
        print("FAILED (LLM returned nothing)")
        return None

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"FAILED (JSON parse error: {e})")
        if verbose:
            print(f"  Raw response:\n{raw[:500]}")
        return None

    r = result.get("resume", {})
    c = result.get("cover_letter", {})

    # Normalize: derive verdict from score if LLM verdict contradicts the threshold
    def _normalize(doc: dict, threshold_ready: int, threshold_rework: int) -> dict:
        total = doc.get("total", 0)
        expected = (
            "CONVERT-READY" if total >= threshold_ready else
            "NEEDS-REWORK" if total < threshold_rework else
            "NEEDS-ONE-PASS"
        )
        if doc.get("verdict") != expected:
            doc["verdict"] = expected
            if expected == "CONVERT-READY":
                doc["blocking_issues"] = []
        return doc

    r = _normalize(r, threshold_ready=70, threshold_rework=50)
    c = _normalize(c, threshold_ready=65, threshold_rework=45)
    result["resume"] = r
    result["cover_letter"] = c

    r_verdict = r.get("verdict", "?")
    c_verdict = c.get("verdict", "?")
    r_total = r.get("total", 0)
    c_total = c.get("total", 0)

    status = "READY" if r_verdict == "CONVERT-READY" and c_verdict == "CONVERT-READY" else "BLOCKED"
    print(f"Resume {r_total}/100 [{r_verdict}]  CL {c_total}/100 [{c_verdict}]  => {status}")

    if verbose and r.get("blocking_issues"):
        print(f"  Resume issues:")
        for issue in r["blocking_issues"]:
            print(f"    - {issue}")
    if verbose and c.get("blocking_issues"):
        print(f"  CL issues:")
        for issue in c["blocking_issues"]:
            print(f"    - {issue}")

    result["_meta"] = {
        "slug": slug,
        "status": status,
        "resume_verdict": r_verdict,
        "cover_letter_verdict": c_verdict,
        "resume_total": r_total,
        "cover_letter_total": c_total,
    }

    report_path = os.path.join(folder, "eval_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return result


def fix_document(slug: str, doc_type: str, result: dict, dry_run: bool = False) -> bool:
    """Apply a one-pass fix to a document that is NEEDS-ONE-PASS."""
    folder = os.path.join(SUBMISSIONS_DIR, slug)
    if doc_type == "resume":
        path = os.path.join(folder, "Resume.md")
        score_key = "resume"
    else:
        path = os.path.join(folder, "CoverLetter.md")
        score_key = "cover_letter"

    doc_result = result.get(score_key, {})
    verdict = doc_result.get("verdict", "")
    if verdict == "CONVERT-READY":
        return False
    if verdict == "NEEDS-REWORK":
        print(f"  [fix] {slug} {doc_type}: NEEDS-REWORK (too far below threshold for auto-fix)")
        return False

    blocking_issues = doc_result.get("blocking_issues", [])
    if not blocking_issues:
        print(f"  [fix] {slug} {doc_type}: no blocking issues listed")
        return False

    document = load_file(path)
    jd = load_file(os.path.join(folder, "Original_JD.txt"))
    work_exp = load_file(WORK_EXP_FILE)
    company = slug.replace("_", " ").title()

    prompt = _build_fix_prompt(doc_type, document, blocking_issues, jd, work_exp, company)

    print(f"  [fix] Rewriting {slug} {doc_type} ({len(blocking_issues)} issue(s))...", end=" ", flush=True)
    fixed = call_llm(
        system_prompt=FIX_SYSTEM,
        user_prompt=prompt,
        temperature=0.3,
    )

    if not fixed:
        print("FAILED (LLM returned nothing)")
        return False

    if dry_run:
        print(f"DRY-RUN (would write {len(fixed)} chars)")
        print("--- PREVIEW (first 400 chars) ---")
        print(fixed[:400])
        return False

    with open(path, "w", encoding="utf-8") as f:
        f.write(fixed)
    print(f"SAVED ({len(fixed)} chars)")
    return True


def main():
    parser = argparse.ArgumentParser(description="Evaluate and optionally fix a submission")
    parser.add_argument("slug", help="Company slug (folder name under data/submissions/)")
    parser.add_argument("--fix", action="store_true", help="Apply fixes for NEEDS-ONE-PASS documents")
    parser.add_argument("--dry-run", action="store_true", help="Preview fixes without writing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show blocking issues inline")
    args = parser.parse_args()

    result = evaluate(args.slug, verbose=args.verbose)
    if result is None:
        sys.exit(1)

    if args.fix:
        r_verdict = result.get("resume", {}).get("verdict", "")
        c_verdict = result.get("cover_letter", {}).get("verdict", "")
        if r_verdict == "NEEDS-ONE-PASS":
            fix_document(args.slug, "resume", result, dry_run=args.dry_run)
        if c_verdict == "NEEDS-ONE-PASS":
            fix_document(args.slug, "cover_letter", result, dry_run=args.dry_run)

        if not args.dry_run and (r_verdict == "NEEDS-ONE-PASS" or c_verdict == "NEEDS-ONE-PASS"):
            print(f"\n  Re-evaluating after fix...")
            evaluate(args.slug, verbose=args.verbose)


if __name__ == "__main__":
    main()
