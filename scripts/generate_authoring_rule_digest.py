#!/usr/bin/env python3
"""
Generate the lean authoring rule digest for CR-074.
# Implements FR-254, NFR-007, FR-319, AC-417

Writes:
  data/authoring_rule_digest.md        — the rule digest (no PII; tracked is fine)
  data/authoring_rule_digest.version   — first 16 hex chars of sha256(content)

Also available as a module: generate_digest() returns (content, version_str).

Usage:
    python scripts/generate_authoring_rule_digest.py
    python scripts/generate_authoring_rule_digest.py --check  # size check only, no write

Exit: 0 on success, 1 if content exceeds 10000-char hard limit.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent
_DIGEST_PATH = _REPO_ROOT / "data" / "authoring_rule_digest.md"
_VERSION_PATH = _REPO_ROOT / "data" / "authoring_rule_digest.version"

# Hard ceiling — fail the generator above this, so callers notice immediately
_HARD_CHAR_LIMIT = 10_000
# Target (warn but don't fail if between TARGET and HARD)
_SOFT_CHAR_TARGET = 8_000

# ---------------------------------------------------------------------------
# The digest content is hardcoded here — no reads of PII files (workExperience.md,
# aiProjects.md, master_claims.json).  All process rules only.
# ---------------------------------------------------------------------------

_DIGEST_CONTENT = """\
# Authoring Rule Digest — CR-074

Lean authoring reference. Load this + the packet. Do NOT load agent_context_pack.md,
full CLAUDE.md, or the claims catalog.

---

## 1. Closed-World Rule (hardest constraint)

Use ONLY claim_ids, excerpts, and claim_constraints from the authoring packet.
Excerpts are retrieved workExperience.md (or aiProjects.md) spans, not catalog text.
Write fresh prose from those facts. Obey each card's Attribution and Prohibited
fields. Never round CONTRIBUTED into OWNED. Never invent a metric, tool, company
name, team name, or date not present in the packet. If the packet has no evidence
for a JD item, note the gap in soft_gaps — do not fabricate a claim to fill it.

---

## 1b. Optimization bar (hard — Round 4)

Done is NOT "clears rubric 70/65." Done is: every soft_gap / domain soft stretch uses the
packet's mapped claim_ids (strongest honest bridge); never substitute a weaker proxy when
that bridge excerpt is present; hard gaps are never claimed as owned. Prefer the JD's bare
honest base title only. Bullets stay ~2–3 lines. When two claims map to the same JD item,
prefer OWNED in the resume.

---

## 2. Resume Structure

Author writes only: PROFESSIONAL SUMMARY (exactly 3 sentences), optional CORE
COMPETENCIES, and bullets under PROFESSIONAL EXPERIENCE. Do not write name/contact,
role titles/dates/locations, or the EDUCATION degree line. A post-author injector
overwrites those from workExperience.md. Keep headings as markers:
`## PROFESSIONAL SUMMARY`, optional `## CORE COMPETENCIES`,
`## PROFESSIONAL EXPERIENCE`, `## EDUCATION`. Keep three `###` role markers in
order: Cision, Sterkly, Zero To Sixty. Bullet counts: 5–6 / 2–3 / 2–3. One page.

**Summary rules:**
- Exactly 3 sentences — not 2, not 4. Characterizes positioning/scope/how he works, not achievements.
- At most 1 proof sentence; preferred default is 0. Say "cross-functionally," never the partner list.
- Heading must be literally `## PROFESSIONAL SUMMARY`. Optional bold subtitle mirrors THIS JD.
  Never default to "B2B SaaS Platform Product Manager."
- HARD_BLOCK (LR-031): no "B2B SaaS" in the summary unless Original_JD.txt uses "SaaS."

---

## 3. Resume Bullet Rules

- Order by JD-relevance: `required` before `preferred` or `responsibilities`. Tie-break: hard metric.
- Two mapped claim_ids: stronger (OWNED > CONTRIBUTED) in the resume; second may support the letter.
- 3-role excerpt cards with no JD map: use only to fill a role that has no JD-mapped claim. Never
  force a low-relevance claim over a higher-relevance one from the same employer.
- Lead with the metric. ~2–3 lines. No multi-sentence blocks.
- Cross-functional partners only from: Engineering, DBA, DevOps, Customer Experience (CX),
  Customer Support, Sales, Account Management, Legal, InfoSec, Product Marketing,
  Executive/Presidential Leadership, Upgrades.
- Never use internal codenames. VOC: Airo → "a macOS security product"; Platform Data Remediation
  → "centralized platform data remediation initiative"; Core B2B SaaS Platform → "customer-facing
  B2B SaaS media monitoring and contact database platform"; Centralized Contact Database →
  "centralized contact source-of-truth database"; Critical Save Program → "high-risk account
  retention program"; White Glove Accounts → "premium high-revenue enterprise clients".
- Draft each claim ONLY under its Employer role. A Cision story stays Cision.

---

## 4. Cover Letter Structure

Author writes only the body (250–400 words, no bullets). Do not write name/contact,
"Dear Hiring Manager,", "Best regards,", or the closing name. Injector fills those.
Opening hook: specific to the company or role. Do NOT open with "I am writing to express my interest."

---

## 5. Cover Letter Argument Rules

- Depth on 1-2 stories. Choose each because it covers several of the role's top
  requirements at once, not one story per requirement. Tell them with context the
  resume bullets cannot carry. Never restate resume bullets. Optionally one plain
  sentence bridging a soft gap. Never list requirements. No T-letter format. A
  forwarded unused high-priority claim goes in only if it is one of those stories.
- Argue fit only. Never acknowledge a gap, skill absence, or inexperience.
- No gap-confession language: "is new territory for me," "I have not yet," "are new to me," or any variant.
- Do NOT argue from workforce reduction, headcount shrinking, executive turnover, or
  "operating through constraint" via team size — not even via an approved euphemism.
- Do NOT assert fit with: "maps directly," "exact fit," "perfectly suited," "uniquely qualified."
  Show fit with a specific fact instead.
- Do NOT paraphrase the JD's own prose back as the opening hook.
- Same strongest packet fact may appear in both documents. Do not drop it or swap to a weaker claim for variety. Resume owns the metric/outcome wording. The letter adds interpretation, decision logic, or narrative, not near-identical resume phrasing.

---

## 6. Attribution Tiers

| Tier | Meaning | Example phrasing |
|---|---|---|
| OWNED | Jason built, designed, or led it | "I led…", "I designed…", "I owned…" |
| CONTRIBUTED | Joint or adjacent work | "I contributed to…", "I partnered on…" |
| INFLUENCED | Informed without direct ownership | "I provided input on…" |

**ACC-120:** CONTRIBUTED at most — joint prompt-engineering research only. Never "I built" or
"I designed" the AI system. `claim_constraints` on a card wins over this table.

---

## 7. Forbidden Formatting

- Em dash (—), semicolons (;), double-hyphen (--): never. Split into two sentences.
- No `word: word` as a prose em-dash substitute ("compelling: building"). Label colons (`**Skills:**`) are fine.
- No bullet points in cover letters.

---

## 8. Forbidden Words and Phrases (core list)

Never use: leverage, passionate, driven, dynamic, innovative, seamless, transformative, synergy,
tapestry, revolutionize, revenue-bearing, proven track record, layoff(s), I am excited to apply,
I am excited about, I am confident that, Furthermore, Moreover, In addition, Additionally.

Never open a sentence with: Furthermore, Moreover, In addition, Additionally, However (as opener),
Here's the thing, Ultimately (as opener), Overall (as opener).

Full list: `scripts/submission_linter.py` LR-009 / LW-006 / LW-007.

---

## 9. Exclusion Zones — What Jason Is NOT

- People management, direct reports, hiring/firing, or managing other PMs
- Titles above Senior IC PM (no Director, Head of, Principal, VP, Staff, Group PM)
- AI/ML model training, fine-tuning, or ML engineering
- Revenue, billing, or payment system ownership
- Tools not in his history unless in the packet excerpt (no Snowflake, Tableau, FHIR, Kubernetes, TensorFlow)
- "Familiar with," "awareness of," or "literacy in" any tool

---

## 10. Collaboration Framing

Influence and alignment, not authority. Use "built alignment across," "brought teams to a shared
order of priorities," "got everyone to commit to," "aligned X and Y on." Never: forced, made,
imposed, or drove other teams "into" a decision. Mention countries, team locations, time zones,
or "global/distributed" only when Original_JD.txt asks for global, international, distributed,
cross-timezone, or multi-region work. Otherwise describe the collaboration itself (who, what
was aligned, what shipped).

---

## 11. Before You Finish — Self-Check

- Every claim_id, excerpt, metric, and company name belongs to THIS packet.
- Employer on the cited claim matches the role section (rule 3).
- Bullets ordered by JD-relevance (required-mapped first).
- Total product management experience: see packet hard_constraints (never invent 4, 5, or 6).
- Zero gap-confession, em dashes, semicolons, double-hyphens, or `word: word` elaboration.
- No countries, time zones, or global/distributed framing unless the JD asks.

---
"""


def contains_pair_restatement_instruction(text: str) -> bool:
    """Return True when text includes the locked CR-112 pair-restatement clauses.

    Requires both operational halves, not incidental 'resume' / 'cover letter'
    wording. Implements FR-319 / AC-417.
    """
    lowered = text.casefold()
    return (
        "do not drop it or swap to a weaker claim for variety" in lowered
        and "not near-identical resume phrasing" in lowered
    )


def _version_from_content(content: str) -> str:
    """Return first 16 hex chars of sha256(utf-8 content)."""
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return digest[:16]


_WE_PATH = _REPO_ROOT / "data" / "workExperience.md"
_SELF_CHECK_YEARS_FALLBACK = (
    "- Total product management experience: see packet hard_constraints "
    "(never invent 4, 5, or 6)."
)


def _years_self_check_line(we_text: str | None = None) -> str:
    from pm_years import years_constraint_from_we

    source = we_text
    if source is None:
        source = _WE_PATH.read_text(encoding="utf-8") if _WE_PATH.exists() else ""
    try:
        return "- " + years_constraint_from_we(source) + "."
    except ValueError:
        return _SELF_CHECK_YEARS_FALLBACK


def generate_digest(we_text: str | None = None) -> tuple[str, str]:
    """Return (content, version_str) without writing any files.

    Raises ValueError if content exceeds _HARD_CHAR_LIMIT.
    """
    years_line = _years_self_check_line(we_text)
    content = _DIGEST_CONTENT.replace(_SELF_CHECK_YEARS_FALLBACK, years_line, 1)
    n = len(content)
    if n > _HARD_CHAR_LIMIT:
        raise ValueError(
            f"Digest content is {n} chars, exceeds hard limit of {_HARD_CHAR_LIMIT}. "
            "Trim the digest before proceeding."
        )
    version = _version_from_content(content)
    return content, version


def write_digest(
    digest_path: Path | None = None,
    version_path: Path | None = None,
) -> tuple[str, str]:
    """Generate and write the digest + version files.

    Returns (content, version_str).
    Raises ValueError if content exceeds hard limit.
    """
    content, version = generate_digest()
    dp = digest_path or _DIGEST_PATH
    vp = version_path or _VERSION_PATH
    dp.parent.mkdir(parents=True, exist_ok=True)
    dp.write_text(content, encoding="utf-8")
    vp.write_text(version, encoding="utf-8")
    return content, version


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the lean authoring rule digest (CR-074 Epic 4.2).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check size only — print char count and version, do not write files.",
    )
    args = parser.parse_args()

    try:
        content, version = generate_digest()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    n = len(content)
    if n > _SOFT_CHAR_TARGET:
        print(
            f"WARNING: digest is {n} chars (over soft target of {_SOFT_CHAR_TARGET}; "
            f"hard limit is {_HARD_CHAR_LIMIT}).",
            file=sys.stderr,
        )

    if args.check:
        print(f"chars={n}  version={version}")
        sys.exit(0)

    content, version = write_digest()
    n = len(content)
    print(f"Written: {_DIGEST_PATH}")
    print(f"Written: {_VERSION_PATH}")
    print(f"chars={n}  approx_tokens={n // 4}  version={version}")
    sys.exit(0)


if __name__ == "__main__":
    _main()
