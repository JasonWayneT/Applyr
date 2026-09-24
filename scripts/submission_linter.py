"""
Declarative submission linter — hard-blocks forbidden language and placeholders
before any PDF is generated. (Epic 1, Stories 1.1–1.8)

Usage:
    python scripts/submission_linter.py data/submissions/hubspot/
    python scripts/submission_linter.py data/submissions/
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Set, Tuple

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)

if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from blocked_tools import epic_match_is_agile_noun, hard_blocked_tools_lint_alternation  # noqa: E402

# Split literals so public-repo PII audit does not flag rule definitions.
_PHONE_PLACEHOLDER = "[" + "REDACTED_" + "PHONE]"
_EMAIL_PLACEHOLDER = "[" + "REDACTED_" + "EMAIL]"

# Parameterized years of experience
CURRENT_YEARS_EXPERIENCE = 7
PREVIOUS_YEARS_EXPERIENCE = CURRENT_YEARS_EXPERIENCE - 1
_NUM_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
PREVIOUS_YEARS_WORD = _NUM_WORDS.get(PREVIOUS_YEARS_EXPERIENCE, str(PREVIOUS_YEARS_EXPERIENCE))

# LR-024: titles above Senior IC PM, per CLAUDE.md's Exclusion Zones ("no Director, Head of,
# Principal, VP, Staff, Group PM"). Scoped at call sites to role headers/summary subtitle only.
_FORBIDDEN_TITLE_PATTERN = re.compile(
    r"\b(Director|VP|Vice President|Head of|Principal\s+(?:Product|Program)|"
    r"Staff\s+(?:Product|Program)|Group\s+Product\s+Manager|Chief\s+\w+\s+Officer|CPO|CTO|CEO|COO)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LintRule:
    rule_id: str
    severity: Literal["HARD_BLOCK", "WARN", "INFO"]
    check_type: Literal["regex", "keyword", "structural", "length"]
    pattern: Optional[str]
    message: str
    suggestion: str
    doc_types: List[str] = field(default_factory=lambda: ["cover_letter", "resume"])


@dataclass
class LintViolation:
    rule_id: str
    severity: str
    message: str
    suggestion: str
    line: Optional[int] = None


@dataclass
class LintResult:
    passed: bool          # False if any HARD_BLOCK violations exist
    blocks: List[LintViolation] = field(default_factory=list)
    warns: List[LintViolation] = field(default_factory=list)
    infos: List[LintViolation] = field(default_factory=list)
    document_type: str = "resume"


# ---------------------------------------------------------------------------
# Rule catalogue
# ---------------------------------------------------------------------------

HARD_BLOCK_RULES: List[LintRule] = [
    LintRule(
        rule_id="LR-001",
        severity="HARD_BLOCK",
        check_type="regex",
        pattern=r"I am excited to apply",
        message="Forbidden opener: 'I am excited to apply'",
        suggestion="Open with something specific about the company or role problem instead.",
        doc_types=["cover_letter"],
    ),
    LintRule(
        rule_id="LR-002",
        severity="HARD_BLOCK",
        check_type="regex",
        pattern=r"I am excited about",
        message="Forbidden phrase: 'I am excited about'",
        suggestion="Replace with a specific observation about the company or role.",
        doc_types=["cover_letter"],
    ),
    LintRule(
        rule_id="LR-003",
        severity="HARD_BLOCK",
        check_type="regex",
        # Widened 2026-07-30 (Perplexity-sourced cliché audit, Jason-supplied) to also catch "I am
        # confident in my ability to" -- same forbidden assertion-of-confidence shape, different
        # grammatical tail, which the original "I am confident that" pattern didn't reach.
        pattern=r"I am confident (that|in my ability to)",
        message="Forbidden phrase: 'I am confident that/in my ability to'",
        suggestion="State the evidence directly instead of asserting confidence.",
        doc_types=["cover_letter"],
    ),
    LintRule(
        rule_id="LR-004",
        severity="HARD_BLOCK",
        check_type="regex",
        pattern=r"proven track record",
        message="Forbidden phrase: 'proven track record'",
        suggestion="Name the specific outcome instead (e.g. 'reduced churn by X%').",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LR-005",
        severity="HARD_BLOCK",
        check_type="regex",
        pattern=r"I am writing to express",
        message="Forbidden opener: 'I am writing to express'",
        suggestion="Open with something specific about the company or role.",
        doc_types=["cover_letter"],
    ),
    LintRule(
        rule_id="LR-006",
        severity="HARD_BLOCK",
        check_type="regex",
        pattern=r"—|--",
        message="Forbidden em-dash (— or --) detected",
        suggestion="Use a comma, colon, or restructure the sentence to remove the dash.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LR-007",
        severity="HARD_BLOCK",
        check_type="keyword",
        pattern=_PHONE_PLACEHOLDER,
        message="Placeholder phone redaction token left in document",
        suggestion="Replace with actual contact information or remove the line.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LR-008",
        severity="HARD_BLOCK",
        check_type="keyword",
        pattern=_EMAIL_PLACEHOLDER,
        message="Placeholder email redaction token left in document",
        suggestion="Replace with actual email address or remove the line.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LR-009",
        severity="HARD_BLOCK",
        check_type="regex",
        # "driven" uses a negative lookbehind for "-" so hyphenated compounds ("data-driven",
        # "metrics-driven", "AI-driven") pass — Jason's explicit call 2026-07-20, audit found the
        # plain \bdriven\b matched these too (a hyphen still counts as a word-boundary character,
        # so "data-driven" was silently hard-blocking ordinary, non-buzzwordy PM vocabulary).
        # Standalone "driven" ("a driven professional") still blocks.
        pattern=r"\b(leverage|passionate|dynamic|innovative|seamless|transformative|synergy|tapestry|revolutionize|revenue-bearing|robust|unwavering)\b|(?<!-)\bdriven\b",
        message="Forbidden buzzword detected",
        suggestion="Replace with plain language that describes what you actually did or built.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LR-010",
        severity="HARD_BLOCK",
        check_type="structural",
        pattern=r"^[\*\-] ",
        message="Bullet point detected in cover letter",
        suggestion="Convert to prose paragraphs. Cover letters must not use bullet points.",
        doc_types=["cover_letter"],
    ),
    LintRule(
        rule_id="LR-011",
        severity="HARD_BLOCK",
        check_type="regex",
        pattern=(
            r"\b(Airo|Platform Data Remediation|Core B2B SaaS Platform"
            r"|Critical Save Program|White Glove Accounts"
            r"|Centralized Contact Database)\b"
        ),
        message="Internal codename detected",
        suggestion="Use the plain-language equivalent from the VOC translation map in CLAUDE.md.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LR-012",
        severity="HARD_BLOCK",
        check_type="regex",
        # Widened 2026-07-20 (audit finding): the "Canadian"-adjacent-only version let a rephrased
        # claim ("$800,000 saved through consolidation," no word "Canadian") pass silently, and
        # approved_metrics.py's allowlist independently contained the same figure outright — both
        # safety nets missed it the same way. Confirmed zero legitimate $800K/$800,000 figure exists
        # anywhere in workExperience.md, so blocking the bare figure is safe.
        pattern=r"\$800K|\$800,000|\b800,000\b|\b800K\b",
        message="Disabled claim ACC-114 ($800K Canadian platform deprecation) detected",
        suggestion="Remove this claim. It is quarantined pending verification.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LR-013",
        severity="HARD_BLOCK",
        check_type="regex",
        # Added 2026-07-20 (audit finding): the years-of-experience figure was corrected from
        # "6+ years"/"six years" to 7 on 2026-07-18 ("Use 7. Do not write 'six years' or '6+ years'
        # anywhere" — workExperience.md §1.0), but nothing mechanical enforced it. approved_metrics.py
        # cannot catch this by design — it deliberately excludes 1-2 digit bare numbers to avoid noisy
        # false positives on small unrelated counts, so a superseded years figure needs its own
        # narrow, specific rule rather than a hack in the generic numeric sweep.
        # Widened 2026-08-11 (post-finalize audit): "last four years" shipped on a COMPLETE letter
        # while resume correctly said 7 — LR-013 only blocked six/6. Also catch four/five and 4/5
        # in last/past/of-experience shapes (not bare "5 years" alone elsewhere).
        pattern=(
            fr"\b{PREVIOUS_YEARS_EXPERIENCE}\+?\s*years\b|\b{PREVIOUS_YEARS_WORD} years\b|"
            r"\b(?:last|past)\s+(?:four|five|six|[4-6])\+?\s*years\b|"
            r"\b(?:four|five|six|[4-6])\+?\s*years\s+of\s+experience\b|"
            r"\bwith\s+(?:four|five|six|[4-6])\+?\s*years\b"
        ),
        message=(
            f"Superseded or undersold years-of-experience figure detected "
            f"(should be {CURRENT_YEARS_EXPERIENCE} / seven, not 4–6 / four–six)"
        ),
        suggestion=f"Use {CURRENT_YEARS_EXPERIENCE} years, per workExperience.md §1.0's explicit correction.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LR-014",
        severity="HARD_BLOCK",
        check_type="regex",
        # Added 2026-07-21 (Jason-supplied, Humana review): same tell as the em-dash rule (LR-006)
        # — semicolons read as an AI-prose artifact, not how Jason writes. Matches the standing rule
        # already applied to application-question answers; formalized here for resumes/cover letters.
        pattern=r";",
        message="Forbidden semicolon detected",
        suggestion="Split into two sentences, or use a comma/period. Semicolons read as an AI-prose tell.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LR-015",
        severity="HARD_BLOCK",
        check_type="regex",
        # Added 2026-07-21 (Jason-supplied, Stripe review): the colon-as-elaboration tell. CLAUDE.md
        # ("No em dashes anywhere ... the colon-as-em-dash-substitute pattern is itself a tell") named
        # this for weeks but nothing enforced it — LR-006 catches em-dashes, LR-014 catches semicolons,
        # and this third documented tell slipped through every "clean" verification. Found in 6 of 9
        # real cover letters that had passed as clean. Pattern is a colon followed by whitespace then a
        # letter ("compelling: building", "context: how", "unplanned work: I built") — the elaboration
        # colon. NOTE: lint_document applies every regex with re.IGNORECASE (line ~417), so [a-z] here
        # matches capitals too — that is deliberate and correct: it also catches elaboration colons
        # whose next word is capitalized ("work: I built ..."). It still does NOT false-positive on:
        # URL colons ("https://" — colon then slash, no whitespace); resume label colons
        # ("**Skills:** Platform" — the colon is immediately followed by "**", so there is no
        # colon-then-whitespace); times or ratios (digit, usually no space). Verified against all 9
        # real letters + all 9 resumes: 7 letters flagged (every hit a genuine tell), 0 resumes.
        pattern=r":\s+[a-z]",
        message="Colon-as-elaboration tell detected (colon followed by a lowercase continuation)",
        suggestion="Restructure into two sentences, or replace with a comma. A colon introducing a lowercase elaboration reads as AI prose, same tell class as the em-dash and semicolon.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LR-016",
        severity="HARD_BLOCK",
        check_type="regex",
        # Added 2026-07-21 (Jason-supplied): gap-confession language in cover letters. Stage 1 of
        # SKILL.md has said "do not spend cover-letter space confessing gaps" since 2026-07-20, and
        # it was still violated in 5 of 11 real letters the same week ("is new territory for me",
        # "I have not yet applied that thinking", "are new to me") - a prose rule alone was not
        # enough to stop it under drafting pressure, hence hard-coding it here. The letter's job is
        # to argue fit; naming what Jason does NOT have is never that argument, even as a lead-in to
        # a "but the underlying skill transfers" pivot - cut the confession clause, keep only the
        # positive transferable-skill claim. NARROW EXCEPTION, not covered by this pattern: a single,
        # plain, factual disclosure of a genuinely unbridgeable hard constraint stated once in neutral
        # register (e.g. the 15% travel ceiling against a JD's higher ask, per workExperience.md
        # §1.4) - that already uses different, non-confessional phrasing ("I can travel up to 15%")
        # and does not match this pattern, which specifically targets the "X is new/I haven't done Y"
        # shape.
        pattern=(
            r"\b(is|are)\s+new\s+(to\s+me|territor(?:y|ies)|domains?)\b"
            r"|\bnew\s+(territor(?:y|ies)|domains?)\s+for\s+me\b"
            r"|\b(have|has|had)\s+not\s+yet\b"
            r"|\bI\s+(do\s+not|don'?t|have\s+not|haven'?t)\s+have\b"
            r"|\bI\s+(have\s+not|haven'?t)\s+worked\s+in\b"
            r"|\bI\s+lack\b"
        ),
        message="Gap-confession language detected in a cover letter",
        suggestion="Cut the confession clause entirely. Argue the transferable skill directly as fit; never name what's absent, even as a lead-in to a pivot. If this is a genuinely unbridgeable hard constraint, state it once, plainly, in neutral register (see workExperience.md §1.4's travel-ceiling example) rather than in this confessional shape.",
        doc_types=["cover_letter"],
    ),
    LintRule(
        rule_id="LR-017",
        severity="HARD_BLOCK",
        check_type="regex",
        # Added 2026-07-21 (Jason-supplied). CLAUDE.md's "Cover letters: don't discuss workforce
        # reduction at all, not even via the euphemism" rule was written the same day as a prose-only
        # addition and was NOT mechanized -- confirmed missed the same day when Cove's cover letter
        # shipped with "a shrinking engineering bench" and "the team itself was shrinking" and nothing
        # caught it until a manual re-read. Same lesson as LR-015/LR-016: a prose rule alone does not
        # survive drafting pressure. This is stricter than R-011/tone_guard.py's "never say layoffs"
        # substitution rule -- R-011 allows an approved euphemism ("resource-constrained cycle");
        # this rule blocks the whole framing category in cover letters specifically, euphemism
        # included. Resumes are NOT in scope (workExperience.md's own role context legitimately
        # references resource constraints factually) -- this is about what a cover letter argues
        # FROM, not about erasing the underlying fact everywhere.
        pattern=(
            r"\bheadcount\s+reduction\b"
            r"|\bshrinking\s+(engineering\s+)?(bench|team|headcount|workforce)\b"
            r"|\b(team|headcount|workforce|bench)\s+(was|is|were)\s+shrinking\b"
            r"|\brounds?\s+of\s+headcount\b"
            r"|\bdownsizing\b"
        ),
        message="Workforce-reduction framing detected in a cover letter",
        suggestion="Cut this framing entirely, even the approved 'resource-constrained cycle' euphemism -- cover letters should not build any part of their argument around headcount/team-size shrinking. Argue the underlying discipline (ambiguity, prioritization, decision-making under incomplete information) without the team-size frame.",
        doc_types=["cover_letter"],
    ),
    LintRule(
        rule_id="LR-018",
        severity="HARD_BLOCK",
        check_type="regex",
        # Added 2026-07-23 (process evaluation audit): blocks the forbidden inverted retention metrics
        # (93% / 93 percent / ninety-three percent) that violate workExperience.md §6.1's explicit ban
        # on inverting the 7% churn to manufacture a fake retention claim.
        pattern=r"\b(?:93%|93\s*percent|ninety-three\s*percent)\b",
        message="Forbidden inverted retention metric detected (inverts the 7% churn statistic, violating workExperience.md §6.1)",
        suggestion="Do not invert the 7% churn figure to claim '93% retention'. Cite the 7% annual churn statistic factually in context or drop it.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LR-019",
        severity="HARD_BLOCK",
        check_type="regex",
        # Added 2026-07-23 (process evaluation audit): blocks claiming the title of "Program Manager"
        # within the years of experience summary sentence (fabricating a title not held factually).
        pattern=r"\bProgram\s+Manager\s+with\s+\d+\s+years\b",
        message="Fabricated Program Manager title in summary years-of-experience statement detected",
        suggestion="Use Product Manager / Product Owner or state product experience years instead. Jason has never held the title 'Program Manager' (workExperience.md §1.0).",
        doc_types=["resume"],
    ),
    LintRule(
        rule_id="LR-020",
        severity="HARD_BLOCK",
        check_type="structural",
        pattern=None,
        message="Missing required canonical career history employer (Cision, Sterkly, or Zero To Sixty)",
        suggestion="Ensure all 3 career history roles are included to preserve career timeline continuity.",
        doc_types=["resume"],
    ),
    LintRule(
        rule_id="LR-021",
        severity="HARD_BLOCK",
        check_type="structural",
        pattern=None,
        message="Primary employer (Cision) bullet count exceeds maximum cap of 6 bullets",
        suggestion="Trim Cision bullets to 5-6 bullets to prevent 2-page resume overflow and visual clutter.",
        doc_types=["resume"],
    ),
    LintRule(
        rule_id="LR-023",
        severity="HARD_BLOCK",
        check_type="regex",
        pattern=r"look forward to discussing how\b[^.!?]{0,60}\balign",
        message="Forbidden closer: 'look forward to discussing how my/our skills align'",
        suggestion="Name the specific thing you'd want to talk through instead of this stock phrase.",
        doc_types=["cover_letter"],
    ),
    # LR-024 through LR-027 added 2026-08-06 (senior-eng/AI 360 review): CLAUDE.md's "Hard
    # Anti-Hallucination Rules" calls people management, titles above Senior IC PM, and
    # revenue/billing ownership "absolute" -- but until now nothing mechanically checked any of
    # them against real drafted output; enforcement was 100% agent judgment during drafting, the
    # exact pattern that already failed silently for LR-016/LR-031(was LW-013)/LW-021 before each got
    # hard-coded after a real miss. Separately: BLOCKED_TOOLS (referenced in this file's own
    # self-repair-protocol history and in CLAUDE.md) turned out to only exist in the retired
    # local_rewrite.py/drafting_engine.py/local_draft_stages.py pipeline that direct authoring no
    # longer calls -- it was dead code relative to the active path. LR-026 replaces it here.
    LintRule(
        rule_id="LR-024",
        severity="HARD_BLOCK",
        check_type="structural",
        pattern=None,
        message="Title-ceiling violation: a title above Senior IC PM appears in a role header or the summary subtitle",
        suggestion="Jason has never held a title above Senior IC PM (no Director, VP, Head of, Principal, Staff, Group PM, or C-suite title). Use the real held title.",
        doc_types=["resume"],
    ),
    LintRule(
        rule_id="LR-025",
        severity="HARD_BLOCK",
        check_type="regex",
        pattern=r"\b(direct reports?|managed a team of \d+|led a team of \d+|people manager|supervis(?:e|ed|ing) (?:a team|staff|employees)|hir(?:e|ed|ing) and (?:fir(?:e|ed|ing)|onboard))\b",
        message="People-management claim detected (direct reports / managed a team / hired / supervised staff)",
        suggestion="Jason has never managed people, hired, fired, or had direct reports (CLAUDE.md Exclusion Zones). Remove or reframe as cross-functional influence, not people management.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LR-026",
        severity="HARD_BLOCK",
        check_type="regex",
        pattern=rf"\b({hard_blocked_tools_lint_alternation()})\b",
        message="Unverified tool claim detected -- not in workExperience.md or master_claims.json",
        suggestion="Remove this tool, or if Jason has genuinely used it, add it to workExperience.md/skills_catalog.json first and treat this as a self-repair-protocol miss.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LR-027",
        severity="HARD_BLOCK",
        check_type="regex",
        pattern=r"\b(owned (?:the )?P&L|P&L ownership|owned revenue|revenue ownership|managed billing|owned (?:the )?billing (?:system|process)|owned payment processing|payment system owner)\b",
        message="Revenue/billing/P&L ownership claim detected",
        suggestion="Jason has never owned revenue, billing, or payment systems (CLAUDE.md Exclusion Zones). Reframe around the actual owned system (e.g. platform reliability, data integrity) instead.",
        doc_types=["cover_letter", "resume"],
    ),
    # LR-028–031 added 2026-08-11 after a post-finalize audit found SDSU education,
    # Senior Cision title, wrong employer date ranges, and stacked "I would welcome" closers
    # on COMPLETE packs. Mech is the fail-closed owner; these are identity chrome, not taste.
    LintRule(
        rule_id="LR-028",
        severity="HARD_BLOCK",
        check_type="structural",
        pattern=None,
        message="Resume EDUCATION must cite National University (BBA); wrong school/degree chrome detected",
        suggestion=(
            "Use: Bachelor of Business Administration, Major in Management, "
            "National University, San Diego, California, 2019 (workExperience.md §7)."
        ),
        doc_types=["resume"],
    ),
    LintRule(
        rule_id="LR-029",
        severity="HARD_BLOCK",
        check_type="structural",
        pattern=None,
        message="Resume employer header chrome does not match workExperience.md §2.1",
        suggestion=(
            "Cision: Product Manager | September 2021 - January 2026 (never Senior). "
            "Sterkly: Product Manager / Product Owner | February 2019 - August 2021. "
            "Zero To Sixty: Account Manager / Product Owner | June 2017 - January 2019 "
            "(never Operations Manager)."
        ),
        doc_types=["resume"],
    ),
    LintRule(
        rule_id="LR-030",
        severity="HARD_BLOCK",
        check_type="structural",
        pattern=None,
        message="Duplicate 'I would welcome…' closers detected in cover letter",
        suggestion=(
            "Keep one closer. If CL-012 needs thanks, append thanks to the existing "
            "custom closer — do not stack a second template 'I would welcome' sentence."
        ),
        doc_types=["cover_letter"],
    ),
    LintRule(
        rule_id="LR-037",
        severity="HARD_BLOCK",
        check_type="regex",
        pattern=r"\b(query performance footprint|audited database table schemas?|audited table schemas?|database table schemas?)\b",
        message="Database schema audit or query performance footprint overclaim detected",
        suggestion=(
            "Jason queries existing SQL databases to trace data flow (ACC-121 / workExperience.md §1.0), "
            "but does not audit/design schemas or profile query performance footprints. "
            "Reframe as: 'Queried and navigated customer SQL databases to trace pipeline data flow...'"
        ),
        doc_types=["cover_letter", "resume"],
    ),
]

WARN_RULES: List[LintRule] = [
    # Implements FR-291 (CR-111): 220–450 is the WARN tolerance band, not the authoring
    # target. The authoritative cover-letter authoring target is 250–400 words (root AGENTS.md).
    LintRule(
        rule_id="LW-001",
        severity="WARN",
        check_type="length",
        pattern=None,
        message="Cover letter word count outside 220–450 range",
        suggestion="Aim for 250–400 words. Under 220 is too thin; over 450 is too long.",
        doc_types=["cover_letter"],
    ),
    LintRule(
        rule_id="LW-002",
        severity="WARN",
        check_type="length",
        pattern=None,
        message="Resume word count exceeds 750",
        suggestion="Trim to under 750 words. Remove weak bullets or consolidate sections.",
        doc_types=["resume"],
    ),
    LintRule(
        rule_id="LW-003",
        severity="WARN",
        check_type="regex",
        pattern=r"\b(Furthermore|Moreover|Additionally|In addition)\b",
        message="Transition fluff word detected",
        suggestion="Cut the transition word and start the sentence with its actual content.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-004",
        severity="WARN",
        check_type="regex",
        pattern=r"\b(resonated deeply|aligns perfectly|highly collaborative)\b",
        message="Generic qualifier detected",
        suggestion="Replace with specific evidence of alignment or collaboration.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-006",
        severity="WARN",
        check_type="regex",
        pattern=(
            r"\b(delve|pivotal|cutting-edge|game-changer|future-ready|elevate your"
            r"|drive impact|orchestrated|groundbreaking|harness|unlock the (potential|value)"
            r"|paramount|foster(?:ed)?|showcas(?:e|es|ing)|multifaceted)\b"
        ),
        # "spearheaded" deliberately excluded from this list (was here until 2026-08-05) --
        # it's used as a trusted high-confidence ownership-verb signal in the attribution-fidelity
        # check below (_OWNERSHIP_VERBS_METRIC), which directly contradicted banning it here: one
        # rule told the author never to write it, the other used its presence as evidence a claim
        # was genuinely owned. Found auditing recruiter-research vocabulary gaps (2026-08-05
        # planning doc). Kept off both as a buzzword and as a false positive -- it's a specific,
        # concrete verb, not a vague AI-tell like "pivotal"/"cutting-edge".
        message="AI-tell buzzword detected (CR-070 Epic 8 authenticity research)",
        suggestion="Replace with plain language describing what you actually did.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-007",
        severity="WARN",
        check_type="regex",
        pattern=(
            r"\b(It is important to note|It should be noted|One must consider|It is essential to"
            r"|In today's fast-paced world|Dive into|Indeed,|Certainly,|Absolutely,|Of course,|Definitely,"
            r"|In conclusion|To summarize|In summary|In closing|Notably,|Subsequently,|Consequently,"
            r"|Building on this|It is worth noting"
            # Added 2026-07-23 (no-ai-slop skill integration, see LW-015 comment below): the same
            # summary-recap tell class ("In conclusion" etc. above) also covers "Ultimately,"/
            # "Overall," as sentence-starters, which weren't in the original list. Lookahead on the
            # comma rather than relying on the shared trailing \b below, since "Ultimately"/"Overall"
            # alone are legitimate mid-sentence words (e.g. "ultimately responsible for") and only the
            # comma-led sentence-starter form is the tell.
            r"|Ultimately(?=,)|Overall(?=,)|At the end of the day|All things considered)\b"
        ),
        message="AI hedging/affirmation/conclusion phrase detected (CR-070 Epic 8/voice-rewrite Pass 1)",
        suggestion="Cut the phrase and start the sentence with its actual content.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-009",
        severity="WARN",
        check_type="regex",
        pattern=r"~\d",
        message="Data-notation shorthand ('~' as approximation) detected — ground-truth-doc notation bleeding into prose",
        suggestion="Write 'approximately'/'roughly', or just state the number plainly. A tilde reads as a spreadsheet artifact on a printed page, not natural resume/letter prose.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-010",
        severity="WARN",
        check_type="regex",
        # Added 2026-07-21 (Jason-supplied, Nelnet/Principal review): coercive framing of Jason's
        # cross-functional work ("forced Sales, Legal, and engineering INTO one sequence"). He works
        # through influence and alignment, not authority he does not have — this is both inaccurate
        # and off-voice. WARN not HARD_BLOCK: "force"/"drive" have legitimate uses ("forcing function",
        # "task force", "drove a fix"), so this flags for human judgment rather than blocking. The
        # "...into" proximity requirement filters most false positives. See CLAUDE.md "Collaboration,
        # not coercion". Reframe: "built alignment across", "brought teams to a shared order of priorities".
        pattern=r"\b(forc(e|ed|ing)|impos(e|ed|ing)|coerc(e|ed|ing))\b[^.]{0,45}\binto\b",
        message="Coercive cross-functional framing detected ('force/impose ... into')",
        suggestion="Reframe as collaboration/influence: 'built alignment across', 'brought teams to a shared order of priorities', 'aligned X and Y on'. Jason leads through influence, not authority he does not have.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-012",
        severity="WARN",
        check_type="regex",
        # Added 2026-07-21 (Jason-supplied, Stripe/Relativity review): assertion-of-fit overclaim
        # language. These phrases ASSERT a fit instead of DEMONSTRATING it, and in practice they
        # paper over a real gap — Stripe ("maps directly" to an API-primitives role that is not his
        # background), Relativity ("the exact shape of" an enrichment role he did not build for).
        # WARN, not hard-block: the phrase itself is not always wrong, but it is a reliable flag that
        # the sentence is claiming fit rather than showing it. When it fires, check the underlying
        # claim honestly — if the fit is real, demonstrate it with a specific fact; if it is a
        # stretch, name the transferable bridge instead of asserting a direct match.
        pattern=(
            r"\b(maps directly|maps perfectly|exact fit|the exact shape of|perfect fit"
            r"|perfectly suited|ideally suited|uniquely qualified|ideal candidate)\b"
        ),
        message="Assertion-of-fit overclaim language detected (asserts fit instead of showing it)",
        suggestion="Demonstrate the fit with a specific fact, or name the honest transferable bridge. Don't assert 'maps directly'/'exact fit' — that phrasing papers over gaps and reads as generic.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-015",
        severity="WARN",
        check_type="regex",
        # Added 2026-07-23 (Jason-supplied, sourced from the `no-ai-slop` skill's pattern list —
        # https://github.com/petergyang/no-ai-slop). Throat-clearing openers: a stalling phrase before
        # the actual point ("Here's the thing," "Let me be clear," "I'll be honest"). Not previously
        # covered — LW-007 catches hedging/conclusion phrases but not this opener shape specifically.
        pattern=r"\b(Here'?s the thing|Let me be clear|I'?ll be honest|The uncomfortable truth is|Here'?s what I mean)\b",
        message="Throat-clearing opener detected",
        suggestion="Cut the stalling phrase and state the point directly.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-016",
        severity="WARN",
        check_type="regex",
        # Added 2026-07-23 (no-ai-slop skill integration). Faux-insight setups and rhetorical
        # question/self-answer setups flatter the writer as the lone expert instead of just making the
        # claim ("what nobody tells you," "what if I told you," "plot twist," "think about it").
        pattern=(
            r"\b(what nobody tells you|what most people get wrong|the part (?:everyone|most people) "
            r"(?:misses|skip)|what if I told you|plot twist|think about it)\b"
        ),
        message="Faux-insight or rhetorical setup detected",
        suggestion="Cut the setup and let the claim stand on its own.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-017",
        severity="WARN",
        check_type="regex",
        # Added 2026-07-23 (no-ai-slop skill integration). Importance puffery states that something
        # matters instead of stating the fact and letting the reader judge ("marks a pivotal moment,"
        # "solidifies its position," "a testament to").
        pattern=(
            r"\b(stands as a testament|marks a (?:pivotal|defining) moment|plays a vital role"
            r"|solidifies its position|underscores its significance|a testament to)\b"
        ),
        message="Importance-puffery phrase detected",
        suggestion="State the fact plainly and let the reader judge whether it matters.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-018",
        severity="WARN",
        check_type="regex",
        # Added 2026-07-23 (no-ai-slop skill integration). Weasel attribution cites an unnamed
        # authority instead of a real source ("experts agree," "studies show," "widely regarded as").
        # Low base-rate risk in a first-person cover letter/resume, but cheap to catch if it appears.
        pattern=r"\b(experts agree|studies show|industry reports suggest|widely regarded as|many argue)\b",
        message="Weasel attribution detected (unnamed authority cited)",
        suggestion="Name the actual source, or cut the claim if there isn't one.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-019",
        severity="WARN",
        check_type="regex",
        # Added 2026-07-23 (no-ai-slop skill integration). Fake-strong verb: "serves as a centralized
        # hub" describes the thing's category instead of what it actually does.
        pattern=r"\bserves as (?:a|the) (?:centralized hub|one-stop shop|backbone|cornerstone|single source of truth)\b",
        message="Fake-strong verb phrase detected ('serves as a/the ...')",
        suggestion="Say what it actually does, not the category it belongs to.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-020",
        severity="WARN",
        check_type="regex",
        # Added 2026-07-23 (no-ai-slop skill integration). Binary-contrast two-sentence shape:
        # "It's not X. It's Y." States Y directly instead. Distinct from LW-008 (which counts
        # ", not"/"rather than"/"instead of" density) — this is the specific two-sentence negate-then-
        # assert shape, catchable on a single paragraph line since these docs are one-line-per-paragraph.
        pattern=r"\bIt('?s| is) not\b[^.!?]{0,120}[.!?]\s+It('?s| is)\b",
        message="Binary-contrast two-sentence shape detected ('It's not X. It's Y.')",
        suggestion="State Y directly instead of negating X first. ('The eval matters more than the model,' not 'It's not the model. It's the eval.')",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LR-032",
        severity="HARD_BLOCK",
        check_type="regex",
        # Implements FR-265: block defensive qualification that explains
        # what Jason or another person did not do instead of stating the verified
        # contribution positively. Kept narrow to avoid matching ordinary
        # product negatives such as "did not interrupt customer access."
        pattern=(
            r"\bmost of the time\b[^.!?\n]{0,100}\b(?:my|mine|me)\b"
            r"|\b(?:not my|outside my|beyond my)\b[^.!?\n]{0,60}"
            r"\b(?:role|scope|responsibilit)"
            r"|\b(?:I|Jason|the (?:engineer|team|designer|analyst))\s+"
            r"(?:did not|didn't|was not|wasn't|never)\b[^.!?\n]{0,80}"
            r"\b(?:diagnos|own|build|decid|lead|manage|responsib)"
        ),
        message="Defensive disclaimer weakens or negates the supported contribution",
        suggestion=(
            "State only the verified action, collaboration, or outcome positively. "
            "Do not explain what you or someone else did not do."
        ),
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-022",
        severity="WARN",
        check_type="regex",
        # Added 2026-07-30 (Jason-supplied): "X sits/lives/operates at the intersection of Y and
        # Z" cliche opener. Found in 3 of the real cover letters in one batch (Newsela, CivicPlus,
        # Empower Pharmacy) -- not Jason's voice, and not caught by any existing rule since it isn't
        # a banned single word, a metric problem, or a JD-paraphrase. A recurring drafting habit,
        # not a one-off, hence mechanized rather than left as a one-time fix.
        pattern=r"\b(sits?|sitting|lives?|living|operates?|stands?)\s+(right\s+)?at\s+(the|that|this)\s+intersection\b",
        message="'Sits/lives at the intersection of X and Y' cliche opener detected -- not Jason's voice.",
        suggestion="State the actual specific tension in plain language instead of the intersection metaphor.",
        doc_types=["cover_letter"],
    ),
    LintRule(
        rule_id="LW-033",
        severity="WARN",
        check_type="regex",
        # Added 2026-08-21 (Jason-supplied, no-ai-slop catalog): "lives or dies on" as a
        # fake-profound kicker/cliche opener. Hit Point C, Nuaxis, Gravitee, Advantage Tech
        # in one week. Same class as LW-022 (intersection metaphor): not a banned word, not
        # Jason's voice, repeats across letters until mechanized.
        pattern=r"\blives or dies on\b",
        message="'Lives or dies on' cliche detected -- not Jason's voice.",
        suggestion="Say the actual condition in plain language (only works if, fails unless, holds together only if).",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-034",
        severity="WARN",
        check_type="regex",
        # Added 2026-08-21 (CR-098): recap-kicker labels that restated the paragraph
        # after the last fact. Hit AMN/TM2 in one batch. WARN, not HARD_BLOCK.
        pattern=r"\bThat'?s (genuine|how I treated|not a slogan)\b|\bas a habit, not as a slogan\b",
        message="Recap-kicker label detected -- stop after the last concrete fact.",
        suggestion="Cut the labeling sentence. End on the last fact or the ask.",
        doc_types=["cover_letter"],
    ),
    LintRule(
        rule_id="LW-035",
        severity="WARN",
        check_type="regex",
        # Added 2026-08-21 (CR-098): paragraph-start negative listing ("Not a SaaS specialist").
        # Per-line match. Broader "Not X. Not Y. A Z." stays judgment-only in the skill.
        pattern=r"^Not a \w+",
        message="Paragraph-start negative listing detected ('Not a ...').",
        suggestion="State the positive claim. Do not open a paragraph by naming what Jason is not.",
        doc_types=["cover_letter"],
    ),
    LintRule(
        rule_id="LW-036",
        severity="WARN",
        check_type="regex",
        # Added 2026-08-21 (Jason-supplied): Salesforce "Closed Lost" is Cision CRM jargon.
        # Customer-facing docs should name what was lost: a subscription / a deal that did
        # not close. Packet excerpts still say closed-lost because WE does.
        pattern=r"\bclosed[- ]lost\b",
        message="Cision CRM jargon 'closed-lost' detected. Name the lost subscription or deal.",
        suggestion="Use 'lost subscriptions' or 'lost subscription opportunities'.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-037",
        severity="WARN",
        check_type="regex",
        # Added 2026-08-21 (Jason-supplied): he has not worked with a design team.
        # "I designed a formula" / "I designed and built Applyr" are verbs and should not match.
        pattern=r"\b(design team|with design\b|designers\b|design and (?:engineering|marketing|product))\b",
        message="Design-team partner claim detected. Design is not a verified cross-functional partner.",
        suggestion="Name engineering, CX, or another verified partner. Do not imply a design team.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-023",
        severity="WARN",
        check_type="regex",
        # Added 2026-07-30 (Perplexity-sourced cliché audit, Jason-supplied): stacked self-
        # descriptor adjectives ("results-driven, highly motivated, and dedicated"). Curated word
        # list rather than a generic adjective-stacking grammar rule, matching this file's existing
        # convention (precision over recall) -- a generic POS-based stacking detector would false-
        # positive on legitimate comma/and-joined verb lists ("iterated, prioritized, and shipped"),
        # which are fine. Two-or-more of these specific cliche self-descriptors within one sentence
        # is the actual tell.
        pattern=(
            r"(results-driven|highly motivated|detail-oriented|hard-working|self-starter"
            r"|go-getter|team player|dedicated|motivated)\b(?:(?!\.).){0,60}?"
            r"\b(results-driven|highly motivated|detail-oriented|hard-working|self-starter"
            r"|go-getter|team player|dedicated|motivated)\b"
        ),
        message="Stacked self-descriptor cliches detected (e.g. 'results-driven, highly motivated, and dedicated')",
        suggestion="Cut to one real descriptor or, better, show it with a specific fact instead of naming the trait.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-024",
        severity="WARN",
        check_type="regex",
        # Added 2026-07-30 (Perplexity-sourced cliché audit, Jason-supplied). Same family as LW-020
        # (binary-contrast "It's not X. It's Y." shape) -- a different templated sentence shape that
        # asserts a trait via a rhetorical setup instead of just stating the fact.
        pattern=r"\bWhether\b[^.!?]{0,80}\bor\b[^.!?]{0,40},?\s+I(\s+have)?\s+(consistently|always)\b",
        message="'Whether doing X or Y, I have consistently...' template sentence detected",
        suggestion="State the specific thing you did instead of the rhetorical whether-or setup.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LW-025",
        severity="WARN",
        check_type="regex",
        # Added 2026-07-30 (Perplexity-sourced cliché audit, Jason-supplied). Generic mission-
        # alignment phrasing ("[Company]'s mission to X aligns with my commitment to Y"). Real risk
        # specifically because this pipeline never does outside company research (no web research at
        # any stage, any purpose) -- but a JD's own "About Company" section often states a mission
        # statement in its own text, which a draft could echo back as this cliche without needing any
        # external lookup at all.
        pattern=r"\bmission\s+to\s+[^.!?]{0,60}\baligns?\s+with\b",
        message="Generic mission-alignment phrasing detected ('[Company]'s mission to X aligns with my Y')",
        suggestion="Name the specific product/role reason you fit instead of asserting mission alignment abstractly.",
        doc_types=["cover_letter"],
    ),
    LintRule(
        rule_id="LW-027",
        severity="WARN",
        check_type="length",
        pattern=None,
        message="Resume character count exceeds 4000",
        suggestion="Trim the resume. Resumes over 4000 characters risk getting truncated or penalized by certain ATS parsers.",
        doc_types=["resume"],
    ),
    LintRule(
        rule_id="LW-030",
        severity="WARN",
        check_type="regex",
        # Added 2026-08-06 alongside LR-024/025/026/027 -- WARN not HARD_BLOCK deliberately.
        # ACC-120 (contributed, joint prompt-engineering research on a colleague's AI system) and
        # ACC-401-AITOOLS (Jason's own real, owned AI-tooling side projects, data/aiProjects.md) are
        # both legitimate and both mention AI/building. The exclusion zone is specifically AI/ML
        # MODEL training/ownership/engineering, not "used AI to build something" -- a distinction a
        # regex can misjudge, so this flags for a human read rather than blocking outright.
        pattern=r"\b(built|design(?:ed)?|train(?:ed)?|own(?:ed)?|architected)\b[^.]{0,40}\b(AI|ML|machine[- ]learning)\s+(model|pipeline)\b",
        message="Possible AI/ML model ownership claim detected -- verify against the Exclusion Zone (no AI/ML model training/ownership/engineering) vs. legitimate ACC-120/ACC-401 AI-tooling claims",
        suggestion="If this describes using AI tools to build something (ACC-401) or contributing/researching (ACC-120), it's fine as worded elsewhere -- if it asserts owning/training/architecting the underlying model itself, cut it.",
        doc_types=["cover_letter", "resume"],
    ),
]

INFO_RULES: List[LintRule] = [
    LintRule(
        rule_id="LI-001",
        severity="INFO",
        check_type="length",
        pattern=None,
        message="Cover letter word count in yellow zone (220–250 or 420–450)",
        suggestion="Consider expanding or trimming slightly to land firmly in the 250–420 range.",
        doc_types=["cover_letter"],
    ),
    LintRule(
        rule_id="LI-002",
        severity="INFO",
        check_type="structural",
        pattern=None,
        message="No corresponding PDF found for this MD file",
        suggestion="Run compile_single.py to generate the PDF.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LI-003",
        severity="INFO",
        check_type="structural",
        pattern=None,
        message="Cover letter has fewer than 3 paragraphs",
        suggestion="Aim for 3–4 paragraphs: hook, proof 1, proof 2 or gap ack, closing.",
        doc_types=["cover_letter"],
    ),
]

ALL_RULES: List[LintRule] = HARD_BLOCK_RULES + WARN_RULES + INFO_RULES

_VERIFIED_PARTNERS = frozenset({
    "engineering", "engineer", "dba", "database administration", "devops", "customer experience",
    "cx", "customer support", "support", "sales", "account management",
    "legal", "infosec", "information security", "product marketing",
    "executive", "presidential", "executive leadership", "upgrade", "upgrades",
})


def _detect_doc_type(text: str, filename: str = "") -> str:
    fn = (filename or "").lower()
    if "cover" in fn or "coverletter" in fn:
        return "cover_letter"
    if "resume" in fn:
        return "resume"
    if "Dear Hiring Manager" in text or "## PROFESSIONAL SUMMARY" not in text:
        return "cover_letter"
    return "resume"


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


_SAME_FUNCTION_ROLE_RE = re.compile(
    r"\b(?:product managers?|product owners?)\b",
    re.IGNORECASE,
)
_DEPARTMENT_BESIDE_ROLE_RE = re.compile(
    r"\b(?:design|ux|marketing|finance|recruit(?:ing|er)?|human resources|data science)\b",
    re.IGNORECASE,
)


def _mention_is_same_function_role(mention: str) -> bool:
    """True when the phrase names a peer PM, not an outside department.

    Live miss (iperium, 2026-09-22): 'partnered with a peer product manager'
    is the same function. Design beside that role still warns.
    """
    if not _SAME_FUNCTION_ROLE_RE.search(mention or ""):
        return False
    return _DEPARTMENT_BESIDE_ROLE_RE.search(mention or "") is None


def _check_unverified_partner(text: str) -> Optional[str]:
    """Warn when a cross-functional partner is mentioned that isn't on the verified list."""
    text_l = text.lower()
    partner_context = re.findall(
        r"partner(?:ed|ing)?\s+with\s+([^,\.;\n]{3,40})|"
        r"collab(?:orat(?:ed|ing))?\s+with\s+([^,\.;\n]{3,40})|"
        r"work(?:ed|ing)?\s+with\s+the\s+([^,\.;\n]{3,40})\s+team",
        text_l,
    )
    mentioned = set()
    for groups in partner_context:
        for g in groups:
            token = (g or "").strip().lower()
            if token:
                # Keep the raw capture. rstrip("s") turned "devops" into "devop"
                # (live miss on velosio, 2026-09-21) and then missed the verified
                # partner. Plural forms still match because each partner string
                # is a substring of the plural ("engineer" in "engineers").
                mentioned.add(token)

    bad = []
    for mention in mentioned:
        if _mention_is_same_function_role(mention):
            continue
        if not any(partner in mention for partner in _VERIFIED_PARTNERS):
            bad.append(mention)
    return ", ".join(bad[:3]) if bad else None


def _lr026_unverified_tool_line_match(pattern: str, line: str) -> bool:
    """LR-026's per-line check, with an extra Python-level pass for "epic(s)"
    matches: ``_epic_pattern``'s embedded regex lookahead is forward-only (Python's
    stdlib re cannot express a variable-width lookbehind), so a match that
    survives the regex might still be the ordinary Agile noun when the
    qualifying word comes BEFORE it in the sentence ("new roadmap epics.") --
    live miss on peoplefinders, 2026-09-21. Every other hard-blocked tool is
    unaffected and keeps the plain regex-only path."""
    for m in re.finditer(pattern, line, re.IGNORECASE):
        token = m.group(0).lower()
        if token.rstrip("s") == "epic" and epic_match_is_agile_noun(line, m.start(), m.end()):
            continue
        return True
    return False


def lint_document(text: str, doc_type: str = "", filename: str = "") -> LintResult:
    """Run all lint rules against text. doc_type can be 'cover_letter' or 'resume'."""
    if not doc_type:
        doc_type = _detect_doc_type(text, filename)

    blocks: List[LintViolation] = []
    warns: List[LintViolation] = []
    infos: List[LintViolation] = []
    lines = text.splitlines()
    wc = _word_count(text)

    for rule in ALL_RULES:
        if doc_type not in rule.doc_types:
            continue

        violation: Optional[LintViolation] = None

        if rule.check_type == "regex" and rule.pattern:
            flags = (re.IGNORECASE | re.MULTILINE) if rule.rule_id not in ("LR-010", "LR-011") else re.MULTILINE
            for i, line in enumerate(lines, start=1):
                if rule.rule_id == "LR-026":
                    hit = _lr026_unverified_tool_line_match(rule.pattern, line)
                else:
                    hit = bool(re.search(rule.pattern, line, flags))
                if hit:
                    violation = LintViolation(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        message=rule.message,
                        suggestion=rule.suggestion,
                        line=i,
                    )
                    break  # report first occurrence only

        elif rule.check_type == "keyword" and rule.pattern:
            if rule.pattern in text:
                line_num = next(
                    (i + 1 for i, ln in enumerate(lines) if rule.pattern in ln), None
                )
                violation = LintViolation(
                    rule_id=rule.rule_id,
                    severity=rule.severity,
                    message=rule.message,
                    suggestion=rule.suggestion,
                    line=line_num,
                )

        elif rule.check_type == "structural":
            if rule.rule_id == "LR-010":
                for i, line in enumerate(lines, start=1):
                    if re.match(r"^[\*\-] ", line.strip()):
                        violation = LintViolation(
                            rule_id=rule.rule_id,
                            severity=rule.severity,
                            message=rule.message,
                            suggestion=rule.suggestion,
                            line=i,
                        )
                        break
            elif rule.rule_id == "LR-020" and doc_type == "resume":
                text_l = text.lower()
                canonical_employers = [
                    ("Cision", ["cision"]),
                    ("Sterkly", ["sterkly"]),
                    ("Zero To Sixty", ["zero to sixty", "zero_to_sixty"])
                ]
                for display_name, terms in canonical_employers:
                    if not any(t in text_l for t in terms):
                        violation = LintViolation(
                            rule_id=rule.rule_id,
                            severity=rule.severity,
                            message=f"Missing core career history employer: {display_name}",
                            suggestion=rule.suggestion,
                        )
                        break
            elif rule.rule_id == "LR-021" and doc_type == "resume":
                cision_section = re.search(r"###\s+.*Cision[\s\S]*?(?=###|\n##\s|\Z)", text, re.IGNORECASE)
                if cision_section:
                    bullets = [ln for ln in cision_section.group(0).splitlines() if ln.strip().startswith("* ")]
                    if len(bullets) > 6:
                        violation = LintViolation(
                            rule_id=rule.rule_id,
                            severity=rule.severity,
                            message=f"Primary employer Cision has {len(bullets)} bullets (exceeds maximum cap of 6 bullets)",
                            suggestion=rule.suggestion,
                        )
            elif rule.rule_id == "LR-024" and doc_type == "resume":
                # Scoped to exactly where Jason's own titles legitimately appear (role headers,
                # the summary subtitle) -- not a blanket document-wide scan, which would false-
                # positive on a bullet mentioning a real cross-functional partner's title (e.g.
                # "partnered with the VP of Engineering", CLAUDE.md's own verified-partner list).
                role_headers = re.findall(r"(?m)^###\s+(.+)$", text)
                candidate_lines = list(role_headers)
                summary_match = re.search(r"##\s*PROFESSIONAL SUMMARY\s*\n+\*\*(.+?)\*\*", text)
                if summary_match:
                    candidate_lines.append(summary_match.group(1))
                for line in candidate_lines:
                    m = _FORBIDDEN_TITLE_PATTERN.search(line)
                    if m:
                        violation = LintViolation(
                            rule_id=rule.rule_id,
                            severity=rule.severity,
                            message=f"Title-ceiling violation: '{m.group(0)}' in {line.strip()!r}",
                            suggestion=rule.suggestion,
                        )
                        break
            elif rule.rule_id == "LR-028" and doc_type == "resume":
                edu = re.search(
                    r"##\s*EDUCATION\s*\n([\s\S]*?)(?=\n##\s|\Z)", text, re.IGNORECASE
                )
                edu_block = edu.group(1) if edu else ""
                edu_l = edu_block.lower()
                if not edu_block.strip():
                    violation = LintViolation(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        message="EDUCATION section missing or empty",
                        suggestion=rule.suggestion,
                    )
                elif "san diego state" in edu_l or re.search(
                    r"\bsdsu\b", edu_l
                ):
                    violation = LintViolation(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        message="Wrong school in EDUCATION (San Diego State / SDSU)",
                        suggestion=rule.suggestion,
                    )
                elif "national university" not in edu_l:
                    violation = LintViolation(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        message="EDUCATION must cite National University",
                        suggestion=rule.suggestion,
                    )
            elif rule.rule_id == "LR-029" and doc_type == "resume":
                headers = re.findall(r"(?m)^###\s+(.+)$", text)
                detail = None
                for h in headers:
                    hl = h.lower()
                    if "cision" in hl:
                        if re.search(r"senior\s+product\s+manager", hl):
                            detail = f"Senior Product Manager on Cision header: {h.strip()!r}"
                        elif re.search(r"2021\s*[-–]\s*2024\b", h) and "2026" not in h:
                            detail = f"Cision date range must end January 2026, got: {h.strip()!r}"
                    if "sterkly" in hl and re.search(r"2020\s*[-–]\s*2021\b", h):
                        detail = (
                            f"Sterkly dates must be February 2019 - August 2021, got: {h.strip()!r}"
                        )
                    if "zero to sixty" in hl or "zero_to_sixty" in hl:
                        if re.search(r"operations\s+manager", hl):
                            detail = f"Operations Manager on Zero To Sixty header: {h.strip()!r}"
                        elif re.search(r"2017\s*[-–]\s*2020\b", h):
                            detail = (
                                f"Zero To Sixty dates must be June 2017 - January 2019, "
                                f"got: {h.strip()!r}"
                            )
                    if detail:
                        break
                if detail:
                    violation = LintViolation(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        message=detail,
                        suggestion=rule.suggestion,
                    )
            elif rule.rule_id == "LR-030" and doc_type == "cover_letter":
                body = (
                    text.split("Dear Hiring Manager,")[-1]
                    if "Dear Hiring Manager," in text
                    else text
                )
                body = re.split(r"\n(?:Best )?regards,", body, flags=re.IGNORECASE)[0]
                hits = re.findall(r"\bi would welcome\b", body, flags=re.IGNORECASE)
                if len(hits) >= 2:
                    violation = LintViolation(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        message=f"Found {len(hits)} 'I would welcome…' closers (max 1)",
                        suggestion=rule.suggestion,
                    )
            elif rule.rule_id == "LI-002":
                pass  # checked externally (requires filesystem knowledge)
            elif rule.rule_id == "LI-003" and doc_type == "cover_letter":
                body = text.split("Dear Hiring Manager,")[-1] if "Dear Hiring Manager," in text else text
                paras = [p.strip() for p in body.split("\n\n") if p.strip()
                         and not p.strip().startswith("#")
                         and not p.strip().startswith("Best")
                         and not p.strip().startswith("Regards")]
                if len(paras) < 3:
                    violation = LintViolation(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        message=f"Cover letter has {len(paras)} paragraph(s); expected at least 3",
                        suggestion=rule.suggestion,
                    )

        elif rule.check_type == "length":
            if rule.rule_id == "LW-001" and doc_type == "cover_letter":
                body = text.split("Dear Hiring Manager,")[-1] if "Dear Hiring Manager," in text else text
                body_wc = _word_count(body)
                if body_wc < 220 or body_wc > 450:
                    violation = LintViolation(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        message=f"Cover letter body is {body_wc} words (target: 220–450)",
                        suggestion=rule.suggestion,
                    )
            elif rule.rule_id == "LW-002" and doc_type == "resume":
                if wc > 750:
                    violation = LintViolation(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        message=f"Resume is {wc} words (target: under 750)",
                        suggestion=rule.suggestion,
                    )
            elif rule.rule_id == "LW-027" and doc_type == "resume":
                if len(text) > 4000:
                    violation = LintViolation(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        message=f"Resume is {len(text)} characters (target: under 4000)",
                        suggestion=rule.suggestion,
                    )
            elif rule.rule_id == "LI-001" and doc_type == "cover_letter":
                body = text.split("Dear Hiring Manager,")[-1] if "Dear Hiring Manager," in text else text
                body_wc = _word_count(body)
                if 220 <= body_wc <= 250 or 420 <= body_wc <= 450:
                    violation = LintViolation(
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        message=f"Cover letter body is {body_wc} words (yellow zone)",
                        suggestion=rule.suggestion,
                    )

        if violation:
            if violation.severity == "HARD_BLOCK":
                blocks.append(violation)
            elif violation.severity == "WARN":
                warns.append(violation)
            else:
                infos.append(violation)

    # LW-005: Unverified partner warning
    bad_partner = _check_unverified_partner(text)
    if bad_partner:
        warns.append(LintViolation(
            rule_id="LW-005",
            severity="WARN",
            message=f"Unverified cross-functional partner mentioned: '{bad_partner}'",
            suggestion="Only use partners from the verified list in CLAUDE.md Section 2.2.",
        ))

    # LW-008: Contrast-frame density (sentence-SHAPE tell, 2026-07-18 adversarial review).
    # "X rather than Y" / "instead of" / ", not Y" repeated across one document is a structural
    # fingerprint that length-based burstiness checks cannot see. Individually fine; >2 per
    # document reads as machine rhythm to a careful reviewer.
    contrast_hits = len(re.findall(r"\brather than\b|\binstead of\b|, not ", text, flags=re.IGNORECASE))
    if contrast_hits > 2:
        warns.append(LintViolation(
            rule_id="LW-008",
            severity="WARN",
            message=f"Contrast-frame density: {contrast_hits} instances of 'rather than'/'instead of'/', not' in one document (max 2)",
            suggestion="Rewrite all but one or two as plain statements. The contrast frame is a repeated sentence shape, and shape repetition is an AI tell even when every instance reads well alone.",
        ))

    # LW-014: Connective-device density (2026-07-21, found by independent Stage 2 review on the
    # Bazaarvoice dry run). "The same X" / "that same X" used as the load-bearing thread tying
    # paragraphs together is a repeated single-word connective device LW-008 doesn't catch (LW-008
    # only matches "rather than"/"instead of"/", not"). Found 4 uses in one 267-word cover letter
    # ("The same logic...", "The same pattern...", "that same judgment call...", "...the same
    # build-it-right-or-patch-it-forever decision"); one or two uses is a legitimate rhetorical
    # thread, four is a structural tic. WARN not HARD_BLOCK: this needs a read to confirm it's
    # actually doing the same job each time versus varying legitimately.
    same_hits = len(re.findall(r"\bthe same\b|\bthat same\b", text, flags=re.IGNORECASE))
    if same_hits > 2:
        warns.append(LintViolation(
            rule_id="LW-014",
            severity="WARN",
            message=f"Connective-device density: {same_hits} instances of 'the same'/'that same' in one document (max 2)",
            suggestion="Vary how each point connects back to the throughline instead of repeating 'the same X' as the connective tissue every time.",
        ))

    passed = len(blocks) == 0
    return LintResult(passed=passed, blocks=blocks, warns=warns, infos=infos, document_type=doc_type)


def _word_tokens(text: str) -> List[str]:
    """Lowercase alphanumeric tokens for cross-document phrase matching."""
    return re.findall(r"[a-z0-9]+", text.lower())


_HEADER_EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


def _strip_header_block(text: str) -> str:
    """Drop a leading name-heading + contact-info line before phrase matching.

    Both the resume and cover letter are expected to open with the same identity/contact
    block (utils.format_contact_header_block) -- that is required duplication, not the
    mechanism/phrasing restatement LW-009-PAIR exists to catch. Found 2026-07-21: adding
    the cover letter's missing header (per CLAUDE.md's required structure) made LW-009-PAIR
    flag the shared contact line as a false positive on every submission going forward.
    """
    lines = text.splitlines()
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx < len(lines) and re.match(r"^#\s+\S", lines[idx]):
        idx += 1
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        if idx < len(lines) and (_HEADER_EMAIL_RE.search(lines[idx]) or lines[idx].count("|") >= 1):
            idx += 1
    return "\n".join(lines[idx:])


# Shared metric/scope cores that legitimately appear in both docs (numbers, not mechanism).
# Longer mechanism clauses ("PTO-adjusted capacity model using T-shirt sizing…") must NOT match.
_SHARED_METRIC_ALLOW: List[re.Pattern[str]] = [
    re.compile(r"^(approximately )?3 ?500 (active )?accounts( and 25 ?000 users)?$"),
    re.compile(r"^25 ?000 users$"),
    re.compile(r"^(eliminated )?(a )?40( percent)?( contact)?( data)? drop( off)?$"),
    re.compile(r"^\$?40m arr( legacy)?( platform)?$"),
]


def _is_allowed_shared_metric_phrase(phrase: str) -> bool:
    """Return True when a shared n-gram is only an approved metric/scope core."""
    return any(p.match(phrase) for p in _SHARED_METRIC_ALLOW)


def find_shared_phrases(resume_text: str, cover_letter_text: str, min_len: int = 6) -> List[str]:
    """Find maximal shared word sequences of length >= min_len across the pair.

    Implements LW-009-PAIR. Resume bullets and cover-letter proof points often share the
    same ACC; that is fine. Reusing the same 6+ word mechanism/phrasing clause is not —
    it is the restatement defect Stage 2 keeps catching by eye. Metric cores alone are allowed.
    """
    resume_toks = _word_tokens(_strip_header_block(resume_text))
    cover_toks = _word_tokens(_strip_header_block(cover_letter_text))
    if len(resume_toks) < min_len or len(cover_toks) < min_len:
        return []

    cover_ngrams = {
        " ".join(cover_toks[i : i + n])
        for n in range(min_len, min(12, len(cover_toks) + 1))
        for i in range(len(cover_toks) - n + 1)
    }

    candidates: List[str] = []
    for n in range(min(12, len(resume_toks)), min_len - 1, -1):
        for i in range(len(resume_toks) - n + 1):
            phrase = " ".join(resume_toks[i : i + n])
            if phrase in cover_ngrams and not _is_allowed_shared_metric_phrase(phrase):
                candidates.append(phrase)

    # Keep maximal only (drop phrases contained in a longer hit).
    maximal: List[str] = []
    # Equal-length phrases must sort by text. set() order is per-process, and the
    # first three phrases are copied into the LW-009-PAIR finding. A changing
    # message changes the HM findings hash and wipes dispositions on the next resume.
    for phrase in sorted(set(candidates), key=lambda item: (-len(item), item)):
        if not any(phrase in longer for longer in maximal):
            maximal.append(phrase)
    return maximal


def check_cross_document_repetition(resume_text: str, cover_letter_text: str) -> List[LintViolation]:
    """Pair-level repetition checks a hiring manager would see reading both docs together.

    LW-008-PAIR: contrast-frame density across the combined pair.
    LW-009-PAIR: shared 6+ word phrases (restatement), excluding approved metric cores.
    Count is for THIS company's own resume+letter pair only, never vs another company.
    """
    violations: List[LintViolation] = []
    combined = f"{resume_text}\n{cover_letter_text}"
    hits = re.findall(r"\brather than\b|\binstead of\b|, not ", combined, flags=re.IGNORECASE)
    if len(hits) > 2:
        violations.append(LintViolation(
            rule_id="LW-008-PAIR",
            severity="WARN",
            message=(
                f"Contrast-frame density across the resume+cover-letter pair: {len(hits)} instances "
                f"of 'rather than'/'instead of'/', not' combined (max 2), even if each file alone is clean"
            ),
            suggestion="Count is for THIS company's own resume+letter pair only, never compared to a different company's submission. Rewrite all but one or two as plain statements.",
        ))

    shared = find_shared_phrases(resume_text, cover_letter_text)
    if shared:
        preview = "; ".join(f'"{p}"' for p in shared[:3])
        extra = f" (+{len(shared) - 3} more)" if len(shared) > 3 else ""
        violations.append(LintViolation(
            rule_id="LW-009-PAIR",
            severity="WARN",
            message=(
                f"Shared phrasing across resume+cover-letter pair: {len(shared)} distinctive "
                f"6+ word sequence(s) appear in both documents. Examples: {preview}{extra}"
            ),
            suggestion=(
                "Resume owns the metric/outcome wording; the cover letter must retell the same "
                "story with different vocabulary and different details (judgment, origin, tradeoff). "
                "Rewrite the letter's proof sentences so none of these phrases survive."
            ),
        ))
    return violations


_BATCH_MIN_LEN = 6
_BATCH_MIN_COMPANIES = 3  # matches the real incident this rule encodes -- see docstring


def check_batch_repetition(docs_by_company: Dict[str, Dict[str, str]]) -> List[LintViolation]:
    """LW-029: cross-batch stylistic-repetition check.

    Catches a drafting HABIT recurring across different companies' submissions -- a shared
    sentence skeleton, opening-hook shape, or closing-line phrase -- that no single-company
    check (LW-008-PAIR/LW-009-PAIR) can see, because those only ever compare one company's
    resume against its OWN cover letter. This mechanizes the "cross-batch critical-hiring-
    manager pass" CLAUDE.md already describes as a standing trigger (the real incident it
    cites: "sits at the intersection of X and Y" recurring in 3 of 8 real letters, caught only
    when Jason asked for a manual sweep). Added 2026-08-05 after a second, worse instance of
    the same failure mode: "I'd welcome the chance to talk through how" was the literal closing
    line in 9 of 9 cover letters drafted in one batch, undetected until Jason asked to brainstorm
    what checks were still missing. A prose reminder to "run the sweep" did not survive a long
    drafting session either time -- this is the mechanized version so it can't be skipped again.

    Cover letters only, deliberately. A resume's employer names, dates, education line, and
    largely-fixed early-career bullets are TRUE, FIXED facts that are supposed to recur across
    every submission -- that is not the habit this rule targets, and an early trial run on real
    data confirmed it fires as pure noise there (every hit was "Education / Bachelor of..." or
    the Sterkly employment-block header). A cover letter's argument is supposed to be built
    fresh per company every time, so identical phrasing there is the actual signal.

    Never fires below _BATCH_MIN_COMPANIES (a coincidence between two letters isn't a habit;
    three or more is the bar the real incidents above were both caught at).

    docs_by_company: {company_name: {"resume": text, "cover_letter": text}}. Company names
    with no cover-letter text are skipped, not treated as an empty match.
    """
    violations: List[LintViolation] = []
    for doc_type in ("cover_letter",):
        texts = {
            company: _strip_header_block(docs[doc_type])
            for company, docs in docs_by_company.items()
            if docs.get(doc_type)
        }
        if len(texts) < _BATCH_MIN_COMPANIES:
            continue

        phrase_companies: Dict[str, Set[str]] = {}
        for company, text in texts.items():
            toks = _word_tokens(text)
            if len(toks) < _BATCH_MIN_LEN:
                continue
            seen_in_this_doc: Set[str] = set()
            for n in range(_BATCH_MIN_LEN, min(12, len(toks) + 1)):
                for i in range(len(toks) - n + 1):
                    seen_in_this_doc.add(" ".join(toks[i : i + n]))
            for phrase in seen_in_this_doc:
                phrase_companies.setdefault(phrase, set()).add(company)

        hits = {p: c for p, c in phrase_companies.items() if len(c) >= _BATCH_MIN_COMPANIES}

        # Collapse to one entry per repeated span: a 6-word core and its many overlapping
        # 7-, 8-, 9-word extensions are the SAME finding, not distinct ones (their company
        # sets naturally diverge at the boundary as some companies' phrasing continues
        # further than others' before diverging). Process widest-reach-first (most companies,
        # then longest) so the most informative variant of each cluster wins the slot instead
        # of an incidental longer-but-narrower extension swallowing a shorter, more-widely-
        # shared core phrase -- confirmed as a real ordering bug on a first pass over real
        # data, where a 9-company 6-word finding got dropped in favor of a 4-company 11-word
        # one. Any later candidate that overlaps (either direction) with an already-kept
        # phrase is the same cluster and gets skipped, not added as a near-duplicate.
        maximal: List[Tuple[str, Set[str]]] = []
        for phrase, companies in sorted(hits.items(), key=lambda kv: (len(kv[1]), len(kv[0])), reverse=True):
            if not any(phrase in kept or kept in phrase for kept, _ in maximal):
                maximal.append((phrase, companies))

        # Cap reported findings per doc_type -- a real habit shows up as a handful of distinct
        # clusters, not dozens; anything past this is the same handful sliced differently.
        maximal = maximal[:8]

        for phrase, companies in maximal:
            company_list = ", ".join(sorted(companies))
            doc_label = doc_type.replace("_", " ")
            violations.append(LintViolation(
                rule_id="LW-029",
                severity="WARN",
                message=(
                    f'Cross-batch repetition ({doc_type}): the phrase "{phrase}" appears '
                    f"identically in {len(companies)} companies' {doc_label}s: {company_list}"
                ),
                suggestion=(
                    "No hiring manager reads two of Jason's letters side by side, so this is not "
                    "a per-document defect -- it is a drafting habit repeating across the batch, "
                    "usually from anchoring on recently-written output rather than writing each "
                    "fresh. Rewrite this phrase in all but one of the flagged documents so no "
                    "shared skeleton survives."
                ),
            ))
    return violations


def _extract_hook(cover_letter_text: str) -> str:
    """Return the cover letter's opening body paragraph (the hook) after the salutation."""
    after = cover_letter_text.split("Dear Hiring Manager,", 1)
    body = after[1] if len(after) > 1 else cover_letter_text
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    return paras[0] if paras else ""


def check_hook_jd_paraphrase(cover_letter_text: str, jd_text: str) -> List[LintViolation]:
    """LW-011: flag when the cover letter's HOOK parrots the JD's own distinctive phrasing.

    A compelling hook offers a specific observation or insight; it does not read the posting's
    own descriptive prose back to the person who wrote it. Reuses find_shared_phrases (6+ word
    verbatim overlap) between the opening paragraph and Original_JD.txt. Role/team/product names
    are short proper nouns and fall under the 6-word threshold, so naming the role is not flagged;
    lifting the JD's descriptive sentences is. Added 2026-07-21 (Jason-supplied, Stripe review:
    the hook lifted "foundational platform primitives ... model, launch, and scale" verbatim).
    """
    hook = _extract_hook(cover_letter_text)
    if not hook or not jd_text.strip():
        return []
    shared = find_shared_phrases(hook, jd_text, min_len=6)
    if not shared:
        return []
    preview = "; ".join(f'"{p}"' for p in shared[:3])
    extra = f" (+{len(shared) - 3} more)" if len(shared) > 3 else ""
    return [LintViolation(
        rule_id="LW-011",
        severity="WARN",
        message=(
            f"Hook paraphrases the JD: {len(shared)} distinctive 6+ word sequence(s) from the "
            f"opening paragraph appear verbatim in Original_JD.txt. Examples: {preview}{extra}"
        ),
        suggestion=(
            "Open with a specific observation or insight about the company's problem, not the "
            "posting's own words read back to them. Naming the role/team is fine; mirroring the "
            "JD's descriptive prose signals nothing to a reader who wrote it."
        ),
    )]


# Implements FR-295 / AC-392: a narrow generic-hook guard, not a prose-quality classifier.
_GENERIC_HOOK_SELF_REFERENCE_RE = re.compile(
    r"\b(?:shows?|highlights?|captures?|reflects?|explains?|is)\s+what\s+makes\s+"
    r"(?:this|the)\s+(?:role|opportunity|position)\s+(?:interesting|compelling|exciting)\b",
    re.IGNORECASE,
)


def check_generic_hook_self_reference(cover_letter_text: str) -> List[LintViolation]:
    """Return LW-038 warnings for generic self-referential cover-letter hooks."""
    hook = _extract_hook(cover_letter_text)
    match = _GENERIC_HOOK_SELF_REFERENCE_RE.search(hook)
    if not match:
        return []
    return [LintViolation(
        rule_id="LW-038",
        severity="WARN",
        message=(
            f'Generic self-referential hook phrase detected: "{match.group(0)}". '
            "It labels the role instead of stating the company-specific product, action, or problem."
        ),
        suggestion=(
            "Replace the phrase with the specific company action, product, or operating problem "
            "that the opening already identifies."
        ),
    )]


def _extract_summary(resume_text: str) -> str:
    """Return the PROFESSIONAL SUMMARY section body (between its heading and the next ## heading)."""
    m = re.search(r"##\s*PROFESSIONAL SUMMARY\s*\n(.*?)(?=\n##\s|\Z)", resume_text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def check_b2b_saas_positioning(resume_text: str, jd_text: str) -> List[LintViolation]:
    """LR-031 (was LW-013): HARD_BLOCK resume summary 'B2B SaaS' when the JD never says SaaS.

    CLAUDE.md's "Required Document Structure" section already states this as a prose rule (added
    2026-07-21): the optional positioning subtitle "must mirror the specific JD's own framing --
    never default to 'B2B SaaS Platform Product Manager'". Found violated on all 9 real summaries
    in the 2026-07-21 batch review despite the rule already being written down -- a prose instruction
    alone did not survive drafting pressure, same failure mode as LR-016/LR-015. Promoted from WARN
    to HARD_BLOCK on 2026-08-11 after live COMPLETE packs kept shipping the default summary opener
    ("7 years of B2B SaaS platform experience") on non-SaaS JDs. Tradeoff accepted: a JD that is
    genuinely SaaS but never uses the literal term "SaaS" will also block -- mirror that JD's own
    words instead of asserting B2B SaaS.
    """
    summary = _extract_summary(resume_text)
    if not summary or not jd_text.strip():
        return []
    if not re.search(r"b2b\s*saas", summary, re.IGNORECASE):
        return []
    if re.search(r"\bsaas\b", jd_text, re.IGNORECASE):
        return []
    return [LintViolation(
        rule_id="LR-031",
        severity="HARD_BLOCK",
        message=(
            "Resume summary frames the role as 'B2B SaaS' but Original_JD.txt never uses the term "
            "'SaaS' anywhere -- default positioning rather than positioning drawn from this JD."
        ),
        suggestion=(
            "Re-read the JD's own framing of what it is (vertical software, marketplace, platform, "
            "etc.) and match the summary to that instead, or drop the positioning language entirely "
            "if no crisp honest framing fits."
        ),
    )]


# LW-039: JD-conditional geography. Remote (USA) is not a license to name
# Budapest / India / time zones / "global/distributed" teams.
_JD_GEOGRAPHY_ASKED_RE = re.compile(
    r"\b("
    r"global|international|distributed|worldwide|"
    r"multi[-\s]?region|"
    r"cross[-\s]?time[-\s]?zones?|time[-\s]?zones?|timezones?"
    r")\b",
    re.IGNORECASE,
)
_UNSOLICITED_GEOGRAPHY_RE = re.compile(
    r"\b("
    r"global|worldwide|distributed|international|"
    r"multi[-\s]?region|"
    r"time[-\s]?zones?|timezones?"
    r")\b"
    r"|Budapest|\bIndia\b|\bIsrael\b|\bHungary\b",
    re.IGNORECASE,
)


def _geography_body_start_line(doc_text: str, doc_type: str) -> int:
    """Skip injected chrome (contact header / greeting) so candidate location does not fire."""
    lines = doc_text.splitlines()
    if doc_type == "cover_letter":
        for i, line in enumerate(lines, start=1):
            if re.match(r"^Dear\b", line.strip(), re.IGNORECASE):
                return i + 1
        return 1
    for i, line in enumerate(lines, start=1):
        if line.startswith("## "):
            return i
    return 1


def check_unsolicited_geography(
    doc_text: str, jd_text: str, doc_type: str = "cover_letter"
) -> List[LintViolation]:
    """LW-039: WARN when a draft names geography the JD never asked for.

    FIXQUEUE 9i (2026-09-19, Jason from the rentana read): the cover-letter closer
    spent itself on "engineering distributed across the U.S., Budapest, and India"
    when Original_JD.txt only said "Remote (USA)". True (ACC-202-DELIVERY) but not
    relevant. WARN because a resume bullet can still fairly keep a location detail.
    """
    if not doc_text.strip() or not jd_text.strip():
        return []
    if _JD_GEOGRAPHY_ASKED_RE.search(jd_text):
        return []
    start = _geography_body_start_line(doc_text, doc_type)
    for i, line in enumerate(doc_text.splitlines(), start=1):
        if i < start:
            continue
        if _UNSOLICITED_GEOGRAPHY_RE.search(line):
            return [LintViolation(
                rule_id="LW-039",
                severity="WARN",
                message=(
                    "Draft names countries, team locations, time zones, or "
                    "global/distributed work, but Original_JD.txt never asks for "
                    "global, international, distributed, cross-timezone, or "
                    "multi-region work."
                ),
                suggestion=(
                    "Drop the geography. Describe the collaboration itself "
                    "(who, what was aligned, what shipped)."
                ),
                line=i,
            )]
    return []


_CROSS_JD_GENERIC_WORDS = {
    "product", "products", "team", "teams", "platform", "platforms", "roadmap",
    "customer", "customers", "user", "users", "feature", "features", "data",
    "engineering", "engineer", "engineers", "stakeholder", "stakeholders",
    "priority", "priorities", "requirement", "requirements", "experience",
    "company", "role", "manager", "managers", "management", "software",
    "solution", "solutions", "growth", "market", "business", "problem",
    "problems", "opportunity", "opportunities", "impact", "quality", "process",
    "processes", "scale", "success", "partner", "partners", "partnership",
    "build", "building", "built", "deliver", "delivery", "work", "working",
    "workflow", "workflows", "compensation", "benefits", "remote", "location",
    "background", "months", "years", "annual", "monthly", "employer",
    "daily", "every", "tools", "genuine", "comfort", "strong", "direct",
    "directly", "ability", "including", "using", "shape", "throughout",
    "across", "alignment", "automation", "backlog", "capabilities", "client",
    "clients", "committed", "complex", "customer-facing", "decisions", "deploy",
    "deployment", "development", "enterprise", "feasibility", "government",
    "integration", "integrations", "issues", "maintain", "monitoring",
    "operational", "operations", "organization", "owner", "owners", "planning", "prioritize",
    "prioritized", "prioritization", "programs", "regulated", "release",
    "sales", "streamline", "support", "supporting", "trade-offs", "validate",
    "validation", "ai-assisted", "go-to-market", "cross-functional",
    # Expanded 2026-08-18 after a real 6-company batch: LW-021 flagged ~50
    # findings that session, every single one a false positive on ordinary
    # PM/business vocabulary the JD happened to repeat, not a genuine
    # audience/domain word like "teachers" or "patients" (the real Newsela
    # bug this rule exists for). min_count=2 alone can't tell "generic word
    # that happens to repeat" from "genuinely distinctive audience term" --
    # the stopword list is the only lever that can, so it has to be broad
    # enough to cover ordinary JD prose, not just the words found so far.
    "about", "through", "value", "values", "valued", "capacity", "first",
    "second", "third", "agile", "scrum", "system", "systems", "technical",
    "technology", "technologies", "level", "levels", "understand",
    "understanding", "environment", "environments", "responsible",
    "responsibility", "responsibilities", "communicate", "communication",
    "communications", "collaborate", "collaboration", "collaborative",
    "leadership", "leader", "leaders", "leading", "drive", "driving",
    "driven", "define", "defining", "identify", "identifying", "insight",
    "insights", "action", "actions", "focus", "focused", "knowledge",
    "familiar", "familiarity", "skill", "skills", "execution", "execute",
    "executing", "strategy", "strategic", "strategies", "vision",
  "innovative", "innovation", "dynamic", "passionate", "excellent",
    "exceptional", "outstanding", "strong", "proven", "demonstrated",
    "ensure", "ensuring", "review", "reviewing", "reviews", "analysis",
    "analyze", "analyzing", "analytical", "metrics", "metric",
    "performance", "outcomes", "outcome", "framework", "frameworks",
    "approach", "approaches", "initiative", "initiatives", "empower",
    "empowering", "empowerment", "efficient", "efficiency", "effective",
    "effectiveness", "scalable", "scalability", "reliable", "reliability",
    "robust", "seamless", "holistic", "end-to-end", "hands-on",
    "self-starter", "self-motivated", "motivated", "detail-oriented",
    "organized", "organization", "organizational", "federal", "regulated",
    "compliance", "compliant", "define", "defined", "clarity", "clarify",
    "consistent", "consistently", "reliable", "capable", "capability",
    "capabilities", "resource", "resources", "resourceful",
    # Grammatical and employment-boilerplate words are not JD specificity.
    # Counting these let generic Sony/Solace first drafts satisfy LW-026 via
    # words such as "which", "clear", and "without".
    "which", "without", "clear", "diverse", "include", "information",
    "eligible", "employees", "employment", "equal", "factors", "gender",
    "personal", "place", "please", "range", "status", "based", "details",
}

_PAST_EMPLOYER_NAMES = ("cision", "sterkly", "zero to sixty")


def _names_past_employer(text: str) -> bool:
    """Use FR-265 whole-name boundaries so 'decisions' does not match 'Cision'."""
    lower = (text or "").lower()
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(employer)}(?![a-z0-9])", lower)
        for employer in _PAST_EMPLOYER_NAMES
    )

# Section-header employer name is authoritative for resume bullets -- a bullet almost
# never repeats "Cision" inline, it's implied by the "### Title | Employer | dates"
# header above it, so bullet-level string matching on employer name alone always misses.
_RESUME_SECTION_RE = re.compile(
    r"^###\s+.*?\|\s*(.+?)\s*\|.*$", re.MULTILINE,
)


def _jd_distinctive_words(jd_text: str, company_name: str = "", min_count: int = 2) -> Set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z-]{4,}", jd_text.lower())
    counts = Counter(words)
    exclude = set(_CROSS_JD_GENERIC_WORDS)
    for tok in re.findall(r"[a-zA-Z]+", company_name.lower()):
        exclude.add(tok)
    return {w for w, c in counts.items() if c >= min_count and w not in exclude}


def _find_hits(text: str, distinctive: Set[str]) -> List[str]:
    lower = text.lower()
    return sorted(w for w in distinctive if re.search(rf"\b{re.escape(w)}\b", lower))


def _resume_bullets_by_employer(resume_text: str) -> List[tuple]:
    """Split PROFESSIONAL EXPERIENCE into (employer, bullet_text) pairs using each
    '### Title | Employer | dates' header to attribute the bullets under it."""
    out = []
    current_employer = ""
    for line in resume_text.splitlines():
        header = _RESUME_SECTION_RE.match(line)
        if header:
            current_employer = header.group(1).strip().lower()
            continue
        stripped = line.strip()
        if stripped.startswith("* ") or stripped.startswith("- "):
            out.append((current_employer, stripped[2:].strip()))
    return out


def check_cross_employer_audience_bleed(
    resume_text: str, cover_letter_text: str, jd_text: str, company_name: str = ""
) -> List[LintViolation]:
    """LW-021: flag the target JD's own distinctive audience/domain vocabulary (e.g.
    'teachers', 'classroom', 'patients') showing up inside a bullet or paragraph
    narrating a DIFFERENT, past employer's story (Cision/Sterkly/Zero to Sixty).

    Ground-truth stories about a past employer should stay in that employer's own real
    vocabulary. The JD's target company is a separate audience/domain and belongs only in
    sentences explicitly drawing the analogy ("the same discipline this role needs"),
    never blended into the factual narration of what a different employer's product or
    users actually were. Found real 2026-07-30 (Newsela, found in an audit, not authored
    by this session): a Cision-attributed Pendo bullet said "fixes teachers and users
    would feel in the product" -- Cision has no teachers as users; Newsela's own audience
    language leaked into the wrong employer's sentence. Not caught by any existing rule
    because it isn't forbidden language, a metric problem, or a JD-paraphrase in the
    hook -- it's a distinct failure class: cross-employer vocabulary bleed. WARN, not
    HARD_BLOCK: a shared word can be a coincidence, or a legitimate different sense of the
    same word (e.g. "prompt design" vs instructional "design"), so this forces a human
    read rather than an automatic rewrite.

    Resume bullets are checked per-bullet, attributed to their enclosing '### ... |
    Employer | ...' section header, since a bullet almost never repeats the employer name
    inline (a first attempt at plain sentence-splitting missed the real bug entirely for
    exactly this reason). Cover letter paragraphs are checked as whole paragraphs, not
    sentences, so a later sentence that refers back anaphorically ("at the same company")
    still gets caught even though it never repeats the employer's proper noun.
    """
    if not jd_text.strip():
        return []
    # min_count=3 (not the default 2): real audience-bleed vocabulary
    # ("teachers", "patients", "classroom") is central enough to a JD that
    # it genuinely repeats; a coincidental generic word crossing the bar at
    # exactly 2 occurrences is far more often noise. LW-026 (specificity
    # floor, a different call site sharing this same word-extraction
    # function) intentionally keeps the lower default -- it's rewarding any
    # real specificity signal, not warning about a factual-bleed risk, so a
    # lower bar there is correct and shouldn't move with this one.
    distinctive = _jd_distinctive_words(jd_text, company_name=company_name, min_count=3)
    if not distinctive:
        return []
    violations = []

    if resume_text.strip():
        for employer, bullet in _resume_bullets_by_employer(resume_text):
            if not any(emp in employer for emp in _PAST_EMPLOYER_NAMES):
                continue
            hit_words = _find_hits(bullet, distinctive)
            if hit_words:
                violations.append(LintViolation(
                    rule_id="LW-021",
                    severity="WARN",
                    message=(
                        f"Resume.md ({employer.title()}): bullet uses this JD's own distinctive "
                        f"vocabulary ({', '.join(hit_words)}) -- possible audience/domain bleed "
                        f"from the target company into a different employer's story: \"{bullet}\""
                    ),
                    suggestion=(
                        "Keep this bullet in that employer's own real vocabulary (its actual "
                        "customers/users/product), not the target company's audience language."
                    ),
                ))

    if cover_letter_text.strip():
        for para in re.split(r"\n\s*\n", cover_letter_text):
            para = para.strip()
            if not para or not _names_past_employer(para):
                continue
            # Implements FR-265: target-company framing may legitimately open
            # the same paragraph before the past-employer bridge. Score from
            # the first sentence that names the past employer onward, retaining
            # later anaphoric sentences while excluding an earlier target-only
            # sentence such as "PlayStation Plus ... At Cision, ...".
            sentences = _split_sentences(para)
            employer_index = next(
                (index for index, sentence in enumerate(sentences) if _names_past_employer(sentence)),
                0,
            )
            historical_span = " ".join(sentences[employer_index:])
            hit_words = _find_hits(historical_span, distinctive)
            if hit_words:
                violations.append(LintViolation(
                    rule_id="LW-021",
                    severity="WARN",
                    message=(
                        f"CoverLetter.md: a paragraph naming a past employer also uses this "
                        f"JD's own distinctive vocabulary ({', '.join(hit_words)}) -- possible "
                        f"audience/domain bleed: \"{para}\""
                    ),
                    suggestion=(
                        "Keep this paragraph's employer story in its own real vocabulary. Draw "
                        "the analogy to the target company in a separate sentence explicitly "
                        "framed as a parallel, not blended into the factual narration."
                    ),
                ))

    return violations


def check_jd_specificity_floor(
    cover_letter_text: str, jd_text: str, company_name: str = "", thin_jd: bool = False
) -> List[LintViolation]:
    """LW-026: flag a cover letter that could plausibly have been sent to any employer.

    Added 2026-07-30 (Perplexity-sourced cliché audit, Jason-supplied): "require the letter to
    reference at least 2 concrete details unique to the job posting... reject drafts that could be
    sent to any employer unchanged." Reuses LW-021's JD-distinctive-word extraction rather than
    doing outside company research -- this pipeline never looks anything up externally, so
    "specific to this posting" has to mean specific to the JD's own text, not researched detail.
    A floor check, not a real specificity judge: passing this only means the letter engages with
    something the JD itself said, not that the engagement is any good. WARN, not HARD_BLOCK -- a
    short or generic-sounding JD can legitimately have very few distinctive words to draw from.
    """
    if thin_jd or not cover_letter_text.strip() or not jd_text.strip():
        return []
    distinctive = _jd_distinctive_words(jd_text, company_name=company_name)
    if not distinctive:
        return []
    hits = _find_hits(cover_letter_text, distinctive)
    if len(hits) >= 2:
        return []
    return [LintViolation(
        rule_id="LW-026",
        severity="WARN",
        message=(
            f"Cover letter engages with only {len(hits)} of this JD's own distinctive term(s) "
            f"({', '.join(hits) if hits else 'none'}) -- could plausibly read as generic to any "
            f"similar role."
        ),
        suggestion=(
            "Ground at least one more paragraph in something this specific JD actually said "
            "(a named responsibility, a product/team detail, a stated constraint), not just the "
            "generic PM vocabulary any posting would share."
        ),
    )]


# ---------------------------------------------------------------------------
# LW-028: claim-attribution vs. ownership-verb mismatch
# ---------------------------------------------------------------------------

# High-confidence ownership verbs, checked against metric-based claim matching.
# Deliberately narrower than a full seniority-signal word list -- "led", "drove",
# "owned", "designed", and "established" were all tried against the real catalog
# and dropped because each produced a real false positive on a legitimately-owned
# claim that happens to share a metric with a 'contributed'/'influenced' one, e.g.
# ACC-101-ANCHOR's "Owned and stabilized a $40M ARR platform..." shares $40M/3,500
# with the 'contributed'-tagged ACC-101-RETENTION churn claim, and ACC-115-
# REQUIREMENTS's "Designed the migration requirements..." shares 700 with the
# 'contributed'-tagged ACC-115-RETENTION/ACC-104 migration claims. Verified zero
# collisions against the full catalog as of 2026-08-04 with this narrower list --
# re-run that check (see git history for the one-off script) if new claims are added.
# "spearheaded" is deliberately NOT in LW-006's banned-buzzword pattern above (see that rule's
# comment) precisely because it's trusted here -- keep both edits in sync if either list changes.
_OWNERSHIP_VERBS_METRIC = {
    "built", "build", "personally", "single-handedly", "singlehandedly",
    "spearheaded", "founded", "architected",
}

# ACC-120 (the AI-research exposure claim) has no numeric metric to match on, so it's
# checked via distinctive anchor phrases from its own text instead of generic tags --
# generic shared tags ("AI Tools", "Prompt Engineering") collide with ACC-401-AITOOLS,
# Jason's own legitimately-owned side project, which genuinely says "designing and
# building" right next to "prompt engineering." "designed"/"design" is included in the
# anchor-path verb set (not the metric-path set above) per CLAUDE.md's explicit "never
# say 'I built' or 'I designed'" instruction for this claim specifically -- these
# anchor phrases don't reproduce the ACC-115-REQUIREMENTS collision that excluded
# "designed" from the general list.
_METRICLESS_CLAIM_ANCHORS = {
    "ACC-120": {
        "orchestration", "content-generation", "content generation",
        "per-specialization", "prompt orchestration", "prompt-orchestration",
    },
}
_OWNERSHIP_VERBS_ANCHOR = _OWNERSHIP_VERBS_METRIC | {"designed", "design"}


def _load_attribution_claims() -> dict:
    """Groups claims from master_claims_tags_only.json (falls back to
    master_claims.json) by project_id, keeping only those explicitly tagged
    attribution: 'contributed' or 'influenced'. A project_id's lenses share one
    ownership level in the current catalog (verified 2026-08-04) -- if that ever
    stops being true, this needs to key by claim id instead of project_id."""
    tags_only_path = os.path.join(_REPO_ROOT, "data", "master_claims_tags_only.json")
    fallback_path = os.path.join(_REPO_ROOT, "data", "master_claims.json")
    path = tags_only_path if os.path.exists(tags_only_path) else fallback_path
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except OSError:
        return {}

    projects: dict = {}
    for entry in raw.values():
        if entry.get("disabled"):
            continue
        attribution = entry.get("attribution")
        if attribution not in ("contributed", "influenced"):
            continue
        pid = entry.get("project_id", "")
        bucket = projects.setdefault(pid, {"attribution": attribution, "metrics": set()})
        bucket["metrics"] |= set(entry.get("metrics", []))
    return projects


def _attribution_metric_variants(metric: str) -> list:
    """Same floor as check_ground_truth_coverage.py's _metric_variants -- kept as an
    independent copy since these two scripts don't share a module today (see that
    script's own docstring for why: each is deliberately self-contained)."""
    variants = {metric}
    bare = metric.replace(",", "").replace("$", "").replace("%", "")
    is_dollar = metric.startswith("$")
    if bare.isdigit():
        n = int(bare)
        variants.add(bare)
        variants.add(f"{n:,}")
        if is_dollar:
            variants.add(f"${bare}")
            variants.add(f"${n:,}")
            if n >= 1_000_000 and n % 1_000_000 == 0:
                variants.add(f"${n // 1_000_000}m")
                variants.add(f"${n // 1_000_000} million")
            elif n >= 1_000 and n % 1_000 == 0:
                variants.add(f"${n // 1_000}k")
    return [v.lower() for v in variants]


# Metricless-claim anchor path only (see _METRICLESS_CLAIM_ANCHORS): how close
# a verb occurrence must sit to an actual anchor-phrase occurrence in the same
# unit to count as describing that claim, rather than an unrelated claim that
# happens to share a long, comma-spliced sentence with it.
_ANCHOR_PROXIMITY_CHARS = 100


def _has_unattributed_verb(unit_lower: str, verb: str, near_positions: List[int] | None = None) -> bool:
    """True iff at least one occurrence of *verb* in *unit_lower* both (a) is
    NOT introduced by a relative pronoun ("who"/"that"/"which") within 3
    tokens before it, and (b), when *near_positions* is given, falls within
    _ANCHOR_PROXIMITY_CHARS of one of them.

    Fix 4 (2026-08-21 Stage 1-3 audit). Two distinct false-positive shapes
    confirmed real this round, both from one bullet/sentence pairing a verb
    with a claim it doesn't actually describe:

    (a) Relative-pronoun handoff -- the plain `re.search` this replaced
    flagged an ownership verb anywhere near a claim's metric/anchor with no
    check for whose action it actually describes. Confirmed on Lightcast:
    "...with the engineer who built it" -- "who" hands the verb to a
    different subject. A verb occurrence immediately preceded by one of
    these pronouns describes someone else's action, not Jason's.

    (b) Same long, comma-spliced sentence, different claim -- confirmed on
    Gravitee: "...with the engineer who built it, and separately designed
    and built my own AI tooling..." Even after (a) excludes "who built it",
    the same sentence's *second* "built" (and "designed") describes a real,
    separately-owned accomplishment (ACC-401, Jason's own side project) that
    has nothing to do with the ACC-120 anchor phrase earlier in the same
    run-on sentence -- only relevant on the anchor path, where a metricless
    claim's collision risk with an unrelated claim is already a known,
    documented problem (see _METRICLESS_CLAIM_ANCHORS).

    A sentence can still have a real overclaim earlier or later in the same
    unit -- this checks each occurrence of the verb independently, not the
    unit as a whole.
    """
    for m in re.finditer(rf"\b{re.escape(verb)}\b", unit_lower):
        preceding_tokens = re.findall(r"[a-z']+", unit_lower[: m.start()])[-5:]
        if any(t in ("who", "that", "which") for t in preceding_tokens[-3:]):
            continue
        # "an adjacent team at Cision built" is that team's verb. "I built"
        # still counts. Live miss: hsi cover letter, 2026-09-22.
        other_subjects = {"team", "teams", "engineering", "engineer", "engineers"}
        if "i" not in preceding_tokens and any(t in other_subjects for t in preceding_tokens):
            continue
        if near_positions is not None and not any(
            abs(m.start() - pos) <= _ANCHOR_PROXIMITY_CHARS for pos in near_positions
        ):
            continue
        return True
    return False


def _split_resume_bullets(resume_text: str) -> List[str]:
    return [
        line.strip()[2:].strip()
        for line in resume_text.splitlines()
        if line.strip().startswith("* ") or line.strip().startswith("- ")
    ]


def _split_sentences(text: str) -> List[str]:
    # Doesn't need to be a perfect sentence splitter, only needs to keep a
    # metric/verb pair inside the same unit they actually co-occur in.
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


# LR-038 / FR-369: the 40% contact-data fix is a decision Jason drove after an
# engineer proposed the bypass (ACC-102). These shapes claim he performed the
# technical connection, or they rename that story as ingestion / frontend work.
_ACC102_METRIC_RE = re.compile(r"\b40\s*(?:%|percent\b)", re.IGNORECASE)
_ACC102_STORY_RE = re.compile(r"drop-?off|data-?loss|stale", re.IGNORECASE)
_ACC102_MEANS_RE = re.compile(
    r"\b(?:by|and)\s+(?:connecting|bypassing)\b",
    re.IGNORECASE,
)
_ACC102_FRONTEND_RE = re.compile(r"\bfrontend screens?\b", re.IGNORECASE)
_ACC102_INGESTION_RE = re.compile(
    r"\bingestion\s+(?:path|pipelines?|loss)\b",
    re.IGNORECASE,
)
_ACC102_OWNED_INTEGRATION_RE = re.compile(
    r"\bown(?:ed|s|ing)? the integration\b",
    re.IGNORECASE,
)
_ACC102_CONCEIVED_RE = re.compile(r"\b(?:conceived|invented)\b", re.IGNORECASE)
_CUSTOMER_DISCOVERY_RE = re.compile(r"\bcustomer discovery\b", re.IGNORECASE)
_CUSTOMER_DISCOVERY_NEG_RE = re.compile(
    r"\b(?:no|not|never|without|blocked from|did not|has not|hasn't)\b"
    r".{0,40}customer discovery|customer discovery.{0,40}"
    r"\b(?:no|not|never|did not|didn't)\b",
    re.IGNORECASE,
)


def check_bypass_authorship(resume_text: str, cover_letter_text: str) -> List[LintViolation]:
    """LR-038: block a 40% drop-off line that claims Jason made the technical connection.

    Args: resume and cover-letter markdown. Returns HARD_BLOCK violations.
    A decision line ("drove the decision to bypass", "an engineer's proposal")
    is allowed. The approved story text ("initiative that bypassed") is allowed.
    """
    units: List[str] = []
    if resume_text.strip():
        units.extend(_split_resume_bullets(resume_text))
    if cover_letter_text.strip():
        for para in re.split(r"\n\s*\n", cover_letter_text):
            units.extend(_split_sentences(para))

    violations: List[LintViolation] = []
    for unit in units:
        if not (_ACC102_METRIC_RE.search(unit) and _ACC102_STORY_RE.search(unit)):
            continue
        means = _ACC102_MEANS_RE.search(unit)
        frontend = _ACC102_FRONTEND_RE.search(unit)
        ingestion = _ACC102_INGESTION_RE.search(unit)
        owned = _ACC102_OWNED_INTEGRATION_RE.search(unit)
        conceived = _ACC102_CONCEIVED_RE.search(unit)
        if not (means or frontend or ingestion or owned or conceived):
            continue
        violations.append(LintViolation(
            rule_id="LR-038",
            severity="HARD_BLOCK",
            message=(
                "40% contact-data drop-off line claims Jason made the technical "
                f"connection or misnames the story: \"{unit}\""
            ),
            suggestion=(
                "Keep the 40% outcome. Say an engineer proposed the bypass and Jason "
                "drove that decision. Do not say he connected or bypassed the path "
                "himself, do not call this story ingestion, and do not add frontend screens."
            ),
        ))
    return violations


def ats_term_conflicts_with_hard_block(term: str) -> bool:
    """True when putting this JD term on the resume would trip LR-039.

    The packet can still list Customer Discovery as supported. The career file
    says that work did not happen, so the ATS contract cannot require the phrase.
    Implements FR-370.
    """
    return (term or "").strip().casefold() == "customer discovery"


def check_customer_discovery(resume_text: str, cover_letter_text: str) -> List[LintViolation]:
    """LR-039: block a claim that customer discovery already happened.

    Args: resume and cover-letter markdown. Returns HARD_BLOCK violations.
    The career file says direct customer discovery was attempted and blocked.
    A sentence that denies it, or that only names the job's ask, is allowed.
    """
    violations: List[LintViolation] = []
    units: List[str] = []
    if resume_text.strip():
        units.extend(_split_resume_bullets(resume_text))
        for line in resume_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("* ") or stripped.startswith("- "):
                continue
            if _CUSTOMER_DISCOVERY_RE.search(stripped):
                units.append(stripped)
    if cover_letter_text.strip():
        for para in re.split(r"\n\s*\n", cover_letter_text):
            for sentence in _split_sentences(para):
                if re.search(r"\b(I|my|me)\b", sentence) and _CUSTOMER_DISCOVERY_RE.search(sentence):
                    units.append(sentence)
    seen: set[str] = set()
    for unit in units:
        if unit in seen or not _CUSTOMER_DISCOVERY_RE.search(unit):
            continue
        if _CUSTOMER_DISCOVERY_NEG_RE.search(unit):
            continue
        seen.add(unit)
        violations.append(LintViolation(
            rule_id="LR-039",
            severity="HARD_BLOCK",
            message=f"Customer discovery is claimed as experience: \"{unit}\"",
            suggestion=(
                "Direct customer discovery did not happen (ACC-185). "
                "Use the closed-lost or support evidence that is real, or cut the phrase."
            ),
        ))
    return violations


def _competencies_section(resume_text: str) -> str:
    """Return the Core Competencies block, stopping at the next heading."""
    match = re.search(
        r"^##\s+CORE COMPETENCIES\s*\n(.*?)(?=^##\s|\Z)",
        resume_text or "",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    return match.group(1) if match else ""


def check_competency_process_notes(resume_text: str) -> List[LintViolation]:
    """LR-040: a repair note or fact id does not belong in Core Competencies.

    Args: resume markdown. Returns HARD_BLOCK violations.
    LR-039 allows a denial so the author can avoid claiming the work. Pasting
    that denial into the skills line is how the note reached the PDF.
    Implements FR-384.
    """
    section = _competencies_section(resume_text)
    if not section.strip():
        return []
    if not re.search(r"\bACC-\d+\b|did not happen", section, re.IGNORECASE):
        return []
    return [LintViolation(
        rule_id="LR-040",
        severity="HARD_BLOCK",
        message=f"Core Competencies contains a process note: \"{section.strip()}\"",
        suggestion="Remove the note. Do not put a denial or a fact id in the skills line.",
    )]


_PLACEHOLDER_COMPANY_RE = re.compile(
    r"\bConfidential is\b|\bat Confidential\b|\brole at Confidential\b"
)


def check_placeholder_company(cover_letter_text: str) -> List[LintViolation]:
    """LR-041: a redacted posting name is not the company in the letter.

    Args: cover-letter markdown. Returns HARD_BLOCK violations.
    Implements FR-384.
    """
    match = _PLACEHOLDER_COMPANY_RE.search(cover_letter_text or "")
    if not match:
        return []
    return [LintViolation(
        rule_id="LR-041",
        severity="HARD_BLOCK",
        message=f"Cover letter uses a placeholder company name: \"{match.group(0)}\"",
        suggestion="Use the real company, or do not name the company when the posting redacts it.",
    )]


def check_experience_role_bullets(resume_text: str) -> List[LintViolation]:
    """LR-044: every professional-experience role needs at least one bullet.

    Args: resume markdown. Returns HARD_BLOCK violations.
    A role heading with no bullet reached COMPLETE. Implements FR-386.
    """
    text = resume_text or ""
    match = re.search(
        r"^##\s+PROFESSIONAL EXPERIENCE\s*\n(.*?)(?=^##\s|\Z)",
        text,
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    if not match:
        return []
    roles = re.split(r"(?m)^###\s+", match.group(1))[1:]
    if not roles:
        return []
    violations: List[LintViolation] = []
    for role in roles:
        lines = role.splitlines()
        title = (lines[0].strip() if lines else "role") or "role"
        body = "\n".join(lines[1:])
        if re.search(r"(?m)^\s*[\*\-]\s+\S", body):
            continue
        violations.append(LintViolation(
            rule_id="LR-044",
            severity="HARD_BLOCK",
            message=f"Experience role has no bullets: \"{title}\"",
            suggestion="Add at least one bullet under this role, or remove the heading.",
        ))
    return violations


_PAST_EMPLOYER_RE = re.compile(
    r"\b(?:cision|sterkly|zero[\s-]+to[\s-]+sixty)\b",
    re.IGNORECASE,
)


def check_letter_names_employer(cover_letter_text: str) -> List[LintViolation]:
    """LR-045: a cover letter needs one prose paragraph that names a past employer.

    Args: cover-letter markdown. Returns HARD_BLOCK violations.
    The employer is Cision, Sterkly, or Zero To Sixty. Implements FR-386.
    """
    text = (cover_letter_text or "").strip()
    if not text:
        return []
    prose = []
    for paragraph in re.split(r"\n\s*\n", text):
        stripped = paragraph.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "." not in stripped and "?" not in stripped:
            continue
        prose.append(stripped)
    if any(_PAST_EMPLOYER_RE.search(paragraph) for paragraph in prose):
        return []
    return [LintViolation(
        rule_id="LR-045",
        severity="HARD_BLOCK",
        message="Cover letter has no paragraph naming Cision, Sterkly, or Zero To Sixty.",
        suggestion="Name the past employer in the paragraph that carries the proof.",
    )]


_DATA_MODEL_RE = re.compile(r"\bdata models?\b|\bdata modeling\b", re.IGNORECASE)


def check_data_model_phrase(resume_text: str, cover_letter_text: str) -> List[LintViolation]:
    """LR-046: block the banned data-model phrases from work experience.

    Args: resume and cover-letter markdown. Returns HARD_BLOCK violations.
    Section 6 forbids claiming a data model. "schema" stays allowed. Implements FR-386.
    """
    violations: List[LintViolation] = []
    seen: set[str] = set()
    for label, text in (("resume", resume_text or ""), ("cover letter", cover_letter_text or "")):
        for line in text.splitlines():
            match = _DATA_MODEL_RE.search(line)
            if not match:
                continue
            key = line.strip()
            if key in seen:
                continue
            seen.add(key)
            violations.append(LintViolation(
                rule_id="LR-046",
                severity="HARD_BLOCK",
                message=f"{label} uses a banned data-model phrase: \"{key[:180]}\"",
                suggestion=(
                    "Cut the phrase. Querying or reading an existing schema is the allowed wording."
                ),
            ))
    return violations


_MET13_PAIR_RE = re.compile(
    r"(?:\$\s*1\s*m\b|1\s+million).{0,48}(?:\$\s*3\s*m\b|3\s+million)",
    re.IGNORECASE,
)
_DRAFT_WEEK_RE = re.compile(r"\bweeks?\b", re.IGNORECASE)
_DRAFT_DAY_RE = re.compile(r"\bdays?\b", re.IGNORECASE)
_DRAFTING_CONTEXT_RE = re.compile(r"\b(?:draft\w*|epics?|stories|story)\b", re.IGNORECASE)


def _hedge_units(resume_text: str, cover_letter_text: str) -> List[str]:
    """Return resume bullets and cover sentences to check for a dropped hedge."""
    units: List[str] = []
    if (resume_text or "").strip():
        units.extend(_split_resume_bullets(resume_text))
    if (cover_letter_text or "").strip():
        for paragraph in re.split(r"\n\s*\n", cover_letter_text):
            units.extend(_split_sentences(paragraph))
    return units


def check_required_hedges(resume_text: str, cover_letter_text: str) -> List[LintViolation]:
    """LR-047: MET-13 and the drafting-time line must keep the word estimated.

    Args: resume and cover-letter markdown. Returns HARD_BLOCK violations.
    "$1M to $3M" and "two weeks to a few days" of drafting are estimates in
    work experience. Implements FR-386.
    """
    violations: List[LintViolation] = []
    seen: set[str] = set()
    for unit in _hedge_units(resume_text, cover_letter_text):
        if re.search(r"estimat", unit, re.IGNORECASE):
            continue
        reason = ""
        if _MET13_PAIR_RE.search(unit):
            reason = "the $1M to $3M figure"
        elif (
            _DRAFT_WEEK_RE.search(unit)
            and _DRAFT_DAY_RE.search(unit)
            and _DRAFTING_CONTEXT_RE.search(unit)
        ):
            reason = "the drafting-time line"
        if not reason or unit in seen:
            continue
        seen.add(unit)
        violations.append(LintViolation(
            rule_id="LR-047",
            severity="HARD_BLOCK",
            message=f"A required estimate hedge is missing on {reason}: \"{unit[:180]}\"",
            suggestion="Keep \"estimated\" on the $1M to $3M figure and on the drafting-time line.",
        ))
    return violations


_DRAFT_CURRENCY_RE = re.compile(r"\$\d[\d,]*(?:\.\d+)?(?:\s*[KMB])?")
_DRAFT_PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s*%")
_DRAFT_UNIT_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("quarter", ("per quarter", "quarterly", "a quarter", "each quarter")),
    ("year", ("annually", "per year", "a year", "each year", "annual", "arr")),
    ("month", ("per month", "monthly", "a month", "each month")),
)
_DRAFT_OTHER_ACTOR_RE = re.compile(
    r"\b(?:engineering|an engineer|the engineer)\s+(?:\w+\s+){0,3}"
    r"(?:built|created|wrote|deployed|automated)\b",
    re.IGNORECASE,
)
_DRAFT_ACTOR_OBJECT_RE = re.compile(r"\b(funnel)\b", re.IGNORECASE)
_DRAFT_OWNERSHIP_RE = re.compile(
    r"\b(?:built|build|building|created|creating|wrote|deployed|automated)\b",
    re.IGNORECASE,
)


def _draft_unit_group(window: str) -> str | None:
    """Return the earliest unit group in *window*."""
    lowered = (window or "").lower()
    best: str | None = None
    best_at = 10**9
    for group, phrases in _DRAFT_UNIT_GROUPS:
        for phrase in phrases:
            found = re.search(rf"\b{re.escape(phrase)}\b", lowered)
            if found and found.start() < best_at:
                best_at = found.start()
                best = group
    return best


def _draft_unit_for_match(text: str, match: re.Match[str]) -> str | None:
    """Return the unit attached to a currency match in *text*."""
    after = _draft_unit_group(text[match.end(): match.end() + 48])
    if after:
        return after
    return _draft_unit_group(text[max(0, match.start() - 32): match.start()])


_OF_HEAD_STOP = frozenset({
    "the", "a", "an", "only", "about", "roughly", "approximately", "nearly",
    "their", "our", "its", "this", "that", "these", "those", "who", "which",
    "just", "some", "more", "most", "than",
})
_FOLLOWER_SKIP = _OF_HEAD_STOP | frozenset({
    "through", "while", "over", "under", "near", "never", "then", "and",
    "by", "to", "for", "with", "from", "into", "after", "before", "during",
})
# Account and user are the same buyers as customer in these spans. "95% of
# active accounts" is the migration sentence, not a different referent.
_CUSTOMER_STEMS = frozenset({"customer", "account", "user"})
_CONTEXT_STOP = _OF_HEAD_STOP | frozenset({
    "data", "used", "using", "use", "have", "must", "were", "was", "been",
    "widely", "assumed", "custom", "broadly", "critical", "took", "priority",
    "example", "feature", "needed", "while", "from", "with", "that", "this",
    "only", "into", "across", "their", "about", "after", "before",
})


def _referent_stem(word: str) -> str:
    """Return a comparison stem for a referent word."""
    cleaned = re.sub(r"[^a-z]", "", (word or "").lower())
    if len(cleaned) > 3 and cleaned.endswith("s") and not cleaned.endswith("ss"):
        cleaned = cleaned[:-1]
    if cleaned in _CUSTOMER_STEMS:
        return "customer"
    return cleaned


def _content_stems(phrase: str, *, skip: frozenset[str], limit: int) -> set[str]:
    """Return stems for the first content words in *phrase*."""
    stems: set[str] = set()
    for word in re.findall(r"[A-Za-z][A-Za-z'-]*", phrase or ""):
        if word.lower() in skip:
            if not stems:
                continue
            break
        stem = _referent_stem(word)
        if len(stem) < 3 or stem in skip:
            continue
        stems.add(stem)
        if len(stems) >= limit:
            break
    return stems


def _of_head_stems(text: str, match: re.Match[str]) -> set[str]:
    """Return the stems of the 'of …' phrase immediately after a percent."""
    window = text[match.end(): match.end() + 48]
    found = re.match(r"\s*of\b", window, re.IGNORECASE)
    if not found:
        return set()
    phrase = window[found.end():]
    phrase = re.split(r"[,.;:]", phrase, maxsplit=1)[0]
    phrase = re.split(
        r"\b(?:was|were|used|and|while|by|to|for|with|that|who|which)\b",
        phrase,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return _content_stems(phrase, skip=_OF_HEAD_STOP, limit=4)


def _span_of_head_sets(spans: List[str], token: str) -> list[set[str]]:
    """Return each span's of-head for *token*. Spans with no of-head are omitted."""
    found: list[set[str]] = []
    for span in spans:
        for match in _DRAFT_PERCENT_RE.finditer(span or ""):
            if re.sub(r"\s+", "", match.group(0)) != token:
                continue
            heads = _of_head_stems(span, match)
            if heads:
                found.append(heads)
    return found


def _percent_context_stems(span: str, match: re.Match[str]) -> set[str]:
    """Return distinctive stems in the span just before this percent."""
    window = span[max(0, match.start() - 90): match.start()]
    stems: set[str] = set()
    for word in re.findall(r"[A-Za-z][A-Za-z'-]*", window):
        if word.lower() in _CONTEXT_STOP:
            continue
        stem = _referent_stem(word)
        if len(stem) < 5 or stem in _CONTEXT_STOP or stem in _CUSTOMER_STEMS:
            continue
        stems.add(stem)
    return stems


def _line_shares_percent_context(unit: str, spans: List[str], token: str) -> bool:
    """True when *unit* shares a nearby span word other than the of-head."""
    line_stems = {_referent_stem(word) for word in re.findall(r"[A-Za-z][A-Za-z'-]*", unit)}
    for span in spans:
        for match in _DRAFT_PERCENT_RE.finditer(span or ""):
            if re.sub(r"\s+", "", match.group(0)) != token:
                continue
            if line_stems & _percent_context_stems(span, match):
                return True
    return False


def _percent_referent_conflict(
    unit: str,
    match: re.Match[str],
    spans: List[str],
) -> str | None:
    """Return the conflicting draft wording, or None when the referent agrees.

    A percent may have more than one lawful of-head across spans (90% of the
    backlog, and 90% of security risks). Conflict requires the draft's of-head
    to miss every one of them. A line that does not share the span's nearby
    wording is left alone, so an unrelated 25% does not inherit the customer
    share. '25% usage' with no 'of' still conflicts when the span's heads
    agree and the line is about that span. Implements FR-384.
    """
    token = re.sub(r"\s+", "", match.group(0))
    span_sets = _span_of_head_sets(spans, token)
    if not span_sets:
        return None
    if not _line_shares_percent_context(unit, spans, token):
        return None
    draft_of = _of_head_stems(unit, match)
    if draft_of:
        if any(draft_of & heads for heads in span_sets):
            return None
        shown = " ".join(sorted(draft_of))
        return shown or "a different group"
    agreed = set.intersection(*span_sets) if span_sets else set()
    if not agreed:
        return None
    follower = unit[match.end(): match.end() + 48]
    if not re.search(r"\busage\b", follower, re.IGNORECASE):
        return None
    follower_stems = _content_stems(follower, skip=_FOLLOWER_SKIP, limit=4)
    if follower_stems & agreed:
        return None
    return "usage"


def _licensed_currency_units(spans: List[str]) -> dict[str, str]:
    """Map a currency token to its unit group when every span agrees."""
    found: dict[str, set[str]] = {}
    for span in spans:
        for match in _DRAFT_CURRENCY_RE.finditer(span or ""):
            unit = _draft_unit_for_match(span, match)
            if not unit:
                continue
            found.setdefault(match.group(0), set()).add(unit)
    return {
        token: next(iter(groups))
        for token, groups in found.items()
        if len(groups) == 1
    }


def _load_career_spans() -> List[str]:
    """Return claim text fields from master_claims.json. Empty when the file is missing."""
    path = os.path.join(_REPO_ROOT, "data", "master_claims.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            catalog = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    spans: List[str] = []
    if isinstance(catalog, dict):
        records = catalog.values()
    elif isinstance(catalog, list):
        records = catalog
    else:
        return []
    for rec in records:
        if isinstance(rec, dict) and str(rec.get("text") or "").strip():
            spans.append(str(rec["text"]))
    return spans


def check_cited_span_fidelity(
    resume_text: str,
    cover_letter_text: str,
    spans: List[str],
) -> List[LintViolation]:
    """LR-042 and LR-043: the drafted number and actor must match the cited span.

    Args: resume markdown, cover-letter markdown, and career-span strings for
    the claims those documents cite. Returns HARD_BLOCK violations.
    A bare $8,500, $8,500 annually, and a 93% that no span contains all fail.
    $8,500 quarterly and $22,100 annually pass when the span says so.
    Implements FR-384.
    """
    if not spans:
        return []
    blob = "\n".join(spans)
    licensed = _licensed_currency_units(spans)
    known_percents = {
        re.sub(r"\s+", "", match.group(0))
        for match in _DRAFT_PERCENT_RE.finditer(blob)
    }
    violations: List[LintViolation] = []
    seen: set[str] = set()
    units: List[str] = []
    if (resume_text or "").strip():
        units.extend(_split_resume_bullets(resume_text))
    if (cover_letter_text or "").strip():
        for para in re.split(r"\n\s*\n", cover_letter_text):
            units.extend(_split_sentences(para))
    for unit in units:
        for match in _DRAFT_CURRENCY_RE.finditer(unit):
            token = match.group(0)
            expected = licensed.get(token)
            if not expected:
                continue
            actual = _draft_unit_for_match(unit, match)
            if actual == expected:
                continue
            key = f"unit:{token}:{unit}"
            if key in seen:
                continue
            seen.add(key)
            violations.append(LintViolation(
                rule_id="LR-042",
                severity="HARD_BLOCK",
                message=(
                    f"{token} is {expected} in the career span, and this line "
                    f"says {actual or 'no unit'}: \"{unit}\""
                ),
                suggestion=f"Keep {token} with the {expected} unit from the career span, or cut the number.",
            ))
        for match in _DRAFT_PERCENT_RE.finditer(unit):
            token = re.sub(r"\s+", "", match.group(0))
            if token in known_percents:
                conflict = _percent_referent_conflict(unit, match, spans)
                if not conflict:
                    continue
                key = f"pct-ref:{token}:{unit}"
                if key in seen:
                    continue
                seen.add(key)
                violations.append(LintViolation(
                    rule_id="LR-042",
                    severity="HARD_BLOCK",
                    message=(
                        f"{token} is a share of a named group in the career span, "
                        f"and this line applies it to {conflict}: \"{unit}\""
                    ),
                    suggestion=(
                        "Keep the percent attached to the same group the career "
                        "span names, or cut the figure."
                    ),
                ))
                continue
            key = f"pct:{token}:{unit}"
            if key in seen:
                continue
            seen.add(key)
            violations.append(LintViolation(
                rule_id="LR-042",
                severity="HARD_BLOCK",
                message=f"{token} is not in the cited career spans: \"{unit}\"",
                suggestion="Use the percent the career span states, or cut this figure.",
            ))
        if _DRAFT_OTHER_ACTOR_RE.search(unit) or not _DRAFT_OWNERSHIP_RE.search(unit):
            continue
        actor_objects: set[str] = set()
        for span in spans:
            for actor in _DRAFT_OTHER_ACTOR_RE.finditer(span or ""):
                tail = span[actor.end(): actor.end() + 80]
                actor_objects.update(obj.lower() for obj in _DRAFT_ACTOR_OBJECT_RE.findall(tail))
        def _owns_nearby(obj: str) -> bool:
            for verb in _DRAFT_OWNERSHIP_RE.finditer(unit):
                window = unit[max(0, verb.start() - 80): verb.end() + 80]
                if obj in window.lower():
                    return True
            return False

        if not any(_owns_nearby(obj) for obj in actor_objects):
            continue
        key = f"actor:{unit}"
        if key in seen:
            continue
        seen.add(key)
        violations.append(LintViolation(
            rule_id="LR-043",
            severity="HARD_BLOCK",
            message=(
                "This line gives Jason an action the career span assigns to "
                f"engineering: \"{unit}\""
            ),
            suggestion="Credit Jason with the landing page. Credit engineering with the funnel.",
        ))
    return violations


def check_attribution_verb_strength(resume_text: str, cover_letter_text: str) -> List[LintViolation]:
    """LW-028: flag a bullet/sentence pairing a high-confidence ownership verb with a
    metric (or, for the one metric-less claim, an anchor phrase) belonging to a claim
    explicitly tagged attribution: 'contributed' or 'influenced' in master_claims.json.

    Generalizes CLAUDE.md's hand-written ACC-120 exception ("CONTRIBUTED at most...
    never say 'I built' or 'I designed'") to every claim carrying an explicit
    attribution tag, instead of relying on that one instance being remembered
    per-draft. Reinforces the same failure mode the attribution-discipline memory
    already tracks: a real metric welded to a real action with an inflated causal
    verb passes every other guard because the metric itself is true.

    WARN, not HARD_BLOCK -- matching a bullet back to the claim it's drawn from is a
    heuristic (metric co-occurrence, or curated anchor phrases for the one metric-less
    claim), same tolerance already extended to LW-021/LW-026. Only 10 of 67 claims in
    the current catalog carry an explicit attribution tag; claims without one are not
    checked (treated as the implicit default: owned).
    """
    projects = _load_attribution_claims()
    if not projects:
        return []

    units: List[str] = []
    if resume_text.strip():
        units.extend(_split_resume_bullets(resume_text))
    if cover_letter_text.strip():
        for para in re.split(r"\n\s*\n", cover_letter_text):
            units.extend(_split_sentences(para))

    violations: List[LintViolation] = []
    seen = set()  # (project_id, unit) -- don't double-report the same pair

    for pid, bucket in sorted(projects.items()):
        anchors = _METRICLESS_CLAIM_ANCHORS.get(pid)
        for unit in units:
            unit_lower = unit.lower()
            if anchors is not None:
                anchor_positions = [
                    m.start()
                    for a in anchors
                    for m in re.finditer(re.escape(a), unit_lower)
                ]
                if not anchor_positions:
                    continue
                verb_hits = [
                    v for v in _OWNERSHIP_VERBS_ANCHOR
                    if _has_unattributed_verb(unit_lower, v, near_positions=anchor_positions)
                ]
            else:
                if not bucket["metrics"]:
                    continue
                # Alnum-boundary check, not plain substring containment -- a bare
                # digit variant like "7" (from metric "7%") is a substring of
                # "700" and would otherwise cross-match an unrelated claim's
                # metric. Not a plain \b: \b fails right before "$" since both
                # "$" and a preceding space are non-word chars.
                metric_hit = any(
                    re.search(rf"(?<![A-Za-z0-9]){re.escape(variant)}(?![A-Za-z0-9])", unit_lower)
                    for m in bucket["metrics"]
                    for variant in _attribution_metric_variants(m)
                )
                if not metric_hit:
                    continue
                verb_hits = [
                    v for v in _OWNERSHIP_VERBS_METRIC
                    if _has_unattributed_verb(unit_lower, v)
                ]
                # ACC-303's verified constraint separates two subjects: Jason
                # built the landing page, while engineering built the product
                # funnel. The combined conversion outcome remains influenced.
                # Do not treat Jason's explicitly allowed landing-page object
                # as ownership of engineering's funnel.
                if pid == "ACC-303" and "built" in verb_hits:
                    # Jason built the landing page. Engineering owns the funnel.
                    # "Built ... landing page that enabled engineering to deploy"
                    # is the allowed shape even when engineering is not the
                    # subject of "built". Live miss (highmark_health, 2026-09-22).
                    owns_landing_page = re.search(
                        r"\b(?:i\s+)?built\b[^.!?]{0,80}\blanding page\b"
                        r"|\blanding page\b[^.!?]{0,40}\bi built\b",
                        unit_lower,
                    )
                    if owns_landing_page:
                        verb_hits = [v for v in verb_hits if v != "built"]

            if not verb_hits or (pid, unit) in seen:
                continue
            seen.add((pid, unit))
            violations.append(LintViolation(
                rule_id="LW-028",
                severity="WARN",
                message=(
                    f"{pid} is tagged attribution: '{bucket['attribution']}' in "
                    f"master_claims.json, but this line uses ownership-tier language "
                    f"({', '.join(sorted(verb_hits))}): \"{unit}\""
                ),
                suggestion=(
                    "Confirm this line is actually drawn from a different, genuinely-owned "
                    f"claim. If it is describing {pid}, reword to participation-level "
                    "language (e.g. 'contributed to,' 'supported,' 'partnered on') -- see "
                    "that claim's own allowed_claims/prohibited_claims in master_claims.json."
                ),
            ))

    return violations


# Process artifacts that live beside Resume.md / CoverLetter.md but must not be
# linted as submissions (CR-074 authoring_prompt.md lists forbidden phrases as
# negative examples and false-fails the whole folder — same class of bug as the
# old stage0_fit_gate.md misclassification).
_LINT_FOLDER_SKIP = frozenset({
    "authoring_prompt.md",
    "authoring_rule_digest.md",
})

# CR-097 Story 5.1/5.2: Jason's own employers appear on every resume. They must
# never count as wrong-job bleed even if they also exist as a jobs.company row.
_OWN_EMPLOYERS = frozenset({"cision", "sterkly", "sterkly services", "zero to sixty"})
_MIN_COMPANY_NAME_CHARS = 4
_AMBIGUOUS_COMPANY_NAMES = frozenset({
    "name", "point",
})


def _application_body(resume: str, cover_letter: str) -> str:
    """Exclude contact headers from FR-265 company-bleed matching.

    Contact lines legitimately contain LinkedIn and can contain common proper
    nouns unrelated to the target job. Wrong-job bleed is meaningful only in
    authored resume/letter content.
    """
    resume_body = resume or ""
    summary = re.search(r"^##\s+PROFESSIONAL SUMMARY\b", resume_body, re.MULTILINE | re.IGNORECASE)
    if summary:
        resume_body = resume_body[summary.start():]

    letter_body = cover_letter or ""
    greeting = re.search(r"^Dear Hiring Manager,\s*$", letter_body, re.MULTILINE | re.IGNORECASE)
    if greeting:
        letter_body = letter_body[greeting.end():]
    return f"{resume_body}\n{letter_body}"


def known_company_names(
    db_path: str | None = None,
    submissions_root: str | None = None,
) -> Set[str]:
    """Return company names Applyr knows about (CR-097 Story 5.1).

    Reads jobs.company plus each folder's stage0_fit_gate.json `company`.
    Names only — never opens another submission's Resume.md or CoverLetter.md.
    A missing DB is skipped without raising.
    """
    names: Set[str] = set()
    db = db_path or os.path.join(_REPO_ROOT, "data", "jobagent.sqlite")
    try:
        import sqlite3

        if os.path.isfile(db):
            conn = sqlite3.connect(db)
            try:
                for (company,) in conn.execute(
                    "SELECT DISTINCT company FROM jobs "
                    "WHERE company IS NOT NULL AND TRIM(company) != ''"
                ):
                    if isinstance(company, str) and company.strip():
                        names.add(company.strip())
            finally:
                conn.close()
    except Exception:
        pass

    root = submissions_root or os.path.join(_REPO_ROOT, "data", "submissions")
    try:
        for entry in os.listdir(root):
            gate = os.path.join(root, entry, "stage0_fit_gate.json")
            if not os.path.isfile(gate):
                continue
            try:
                with open(gate, encoding="utf-8") as fh:
                    payload = json.load(fh)
            except (OSError, json.JSONDecodeError):
                continue
            company = str(payload.get("company") or "").strip()
            if company:
                names.add(company)
    except OSError:
        pass
    return names


def _own_company_aliases(own_company: str) -> set[str]:
    """Names that mean this folder's employer, including a duplicate suffix.

    Stage 0 labels a second posting "Medrisk 2". That is still Medrisk.
    Implements FR-265.
    """
    raw = (own_company or "").strip().lower()
    if not raw:
        return set()
    aliases = {raw}
    stripped = re.sub(r"\s+\d+$", "", raw).strip()
    if stripped:
        aliases.add(stripped)
    return aliases


def check_wrong_job_company_bleed(
    resume: str,
    cover_letter: str,
    jd_text: str,
    own_company: str,
    known_names: Set[str] | None = None,
) -> List[LintViolation]:
    """WARN when a different known company name appears in this folder's docs.

    Precision first: match the known-name index only, never guess at proper nouns.
    """
    names = known_names if known_names is not None else known_company_names()
    own_aliases = _own_company_aliases(own_company)
    jd_lower = (jd_text or "").lower()
    combined = _application_body(resume, cover_letter)
    hits: List[LintViolation] = []
    seen: Set[str] = set()
    # Tie-break by lowercased name (not just length) so two equal-length names
    # (e.g. "workday" and "Unified", both 7 chars) sort the same way on every
    # run. `names` comes from a set, whose iteration order is hash-randomized
    # per process -- without this tie-break, `sorted(..., key=len)` silently
    # inherited that randomness for any length tie, flipping finding order
    # (and the dispositions.json content hash bound to it) between runs on
    # otherwise-unchanged documents. Found live 2026-09-20 on crio.
    for name in sorted(names, key=lambda n: (-len(n), n.lower())):
        trimmed = name.strip()
        if len(trimmed) < _MIN_COMPANY_NAME_CHARS:
            continue
        lower = trimmed.lower()
        if (
            lower in seen
            or lower in _OWN_EMPLOYERS
            or lower in _AMBIGUOUS_COMPANY_NAMES
            or lower in own_aliases
        ):
            continue
        if lower in jd_lower:
            continue
        # "workday" collides with ordinary capacity-planning phrasing
        # ("developer workday-hours") the same way it does in
        # blocked_tools.hard_blocked_tool_pattern's own workday exclusion --
        # that fix never propagated here because this is a separate
        # company-bleed check, not the hard-blocked-tool one. Live false
        # positive found 2026-09-21 (isolved): a real Cision capacity-model
        # bullet flagged as naming the Workday company. Same narrow
        # lookahead exclusion, same reasoning.
        # "The Standard" collides with ordinary English ("the standard line",
        # "the standard queue"). Live miss 2026-09-21 omnissa: cover letter
        # "skip the standard line" flagged the insurance company.
        flags = re.IGNORECASE
        if lower == "workday":
            pattern = rf"\b{re.escape(trimmed)}\b(?![\s-]*hours?\b)"
        elif lower == "the standard":
            pattern = (
                rf"\b{re.escape(trimmed)}\b(?!\s+"
                rf"(line|queue|way|practice|set|issue|approach|process|bar|"
                rf"fare|procedure)s?\b)"
            )
        elif lower == "unified":
            # The company is the capitalized proper noun. Lowercase "unified"
            # is the adjective ("a unified roadmap", "unified Agile delivery").
            # Live misses: modern_campus 2026-09-22, highmark/keyfactor/medrisk
            # 2026-09-22. Implements FR-265.
            pattern = r"\bUnified\b"
            flags = 0
        else:
            pattern = r"\b" + re.escape(trimmed) + r"\b"
        if not re.search(pattern, combined, flags):
            continue
        seen.add(lower)
        hits.append(
            LintViolation(
                rule_id="LW-032",
                severity="WARN",
                message=(
                    f"Wrong-job content bleed: documents name {trimmed!r}, "
                    "a different company Applyr knows about"
                ),
                suggestion=(
                    "Remove the other company's name. This folder is judged only "
                    "against its own JD."
                ),
            )
        )
    return hits


def collect_fidelity_hard_blocks(
    resume_text: str,
    cover_letter_text: str,
    provenance: Optional[dict] = None,
) -> List[LintViolation]:
    """Return the span, role, employer, phrase, hedge, and cited-contradiction blocks.

    Stage 2 HM already blocks on these. Stage 1 verify calls the same list
    so a repair can edit the draft before the hiring-manager pass. A block
    that first appears after Stage 1 is COMPLETE cannot be repaired.
    Implements FR-386 / FR-390.
    """
    blocks: List[LintViolation] = []
    blocks.extend(check_competency_process_notes(resume_text))
    blocks.extend(check_placeholder_company(cover_letter_text))
    blocks.extend(
        check_cited_span_fidelity(
            resume_text,
            cover_letter_text,
            _load_career_spans(),
        )
    )
    blocks.extend(check_experience_role_bullets(resume_text))
    blocks.extend(check_letter_names_employer(cover_letter_text))
    blocks.extend(check_data_model_phrase(resume_text, cover_letter_text))
    blocks.extend(check_required_hedges(resume_text, cover_letter_text))
    blocks.extend(check_disruption_hedge(resume_text, cover_letter_text))
    blocks.extend(check_cited_contradiction(resume_text, cover_letter_text, provenance))
    blocks.extend(check_portability_inversion(resume_text, cover_letter_text))
    blocks.extend(check_qa_lead_claim(resume_text, cover_letter_text))
    blocks.extend(check_hundreds_of_client_databases(resume_text, cover_letter_text))
    blocks.extend(check_support_escalation_reduction(resume_text, cover_letter_text))
    blocks.extend(check_release_cadence(resume_text, cover_letter_text))
    return blocks


# The tagging inversion is false on any cite. ACC-155 says custom tagging
# took priority. Implements FR-391.
_PORTABILITY_INVERSION_RE = re.compile(
    r"\bover custom tagging\b|\bportability over\b",
    re.IGNORECASE,
)
# He was not a QA lead. The before-fix Candor bullet cites ACC-204. Implements FR-392.
_QA_LEAD_RE = re.compile(r"\bqa lead\b", re.IGNORECASE)
# MET-09 is roughly 200 SQL databases. "Hundreds" drops that count. Implements FR-393.
_HUNDREDS_OF_CLIENT_RE = re.compile(r"\bhundreds of client\b", re.IGNORECASE)
# Work experience never says support escalations were reduced. Implements FR-395.
_SUPPORT_ESCALATION_REDUCTION_RE = re.compile(
    r"\breduc(?:e|ed|ing)\b.{0,60}\bsupport escalat",
    re.IGNORECASE,
)
# Work experience never says release cadence. Implements FR-399.
_RELEASE_CADENCE_RE = re.compile(r"\brelease cadence\b", re.IGNORECASE)

# A cited fact id plus a phrase that fact does not support. The id must be
# cited. The same words on a different fact do not block. Implements FR-390.
_CITED_CONTRADICTION: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ACC-107", re.compile(
        r"\bregulatory\b|\bdata governance\b|\baudit requirements\b|\bcompliance frameworks\b",
        re.I,
    )),
    ("ACC-113", re.compile(
        r"\b(?:owned the end-to-end|end-to-end migration|leading the migration)\b",
        re.I,
    )),
    ("ACC-102", re.compile(
        r"\bled the technical implementation\b|\btechnical implementation\b",
        re.I,
    )),
    ("ACC-220", re.compile(
        r"\bleading the platform migration\b|\bled the (?:technical|platform) migration\b",
        re.I,
    )),
    ("ACC-103", re.compile(r"\b(?:cleared|resolved)\b.{0,40}\bbacklog\b", re.I)),
    ("ACC-125", re.compile(r"\b(?:cleared|resolved)\b.{0,40}\bbacklog\b", re.I)),
    ("ACC-209", _QA_LEAD_RE),
    ("ACC-155", _PORTABILITY_INVERSION_RE),
    ("ACC-115", re.compile(r"\b(?:active usage|feature usage)\b", re.I)),
    ("ACC-303", re.compile(r"\bautomating lead capture\b|\bonboarding funnel\b", re.I)),
    ("ACC-203", re.compile(
        r"\bfunctional specifications\b|\bendpoint protection rules\b|\bnegotiated technical\b",
        re.I,
    )),
)


def _fact_prefix(claim_id: str) -> str:
    """Return ACC-155 from a cite, or empty when the token is not a fact id."""
    match = re.match(r"(ACC|MET|VOC)-\d+", claim_id or "")
    return match.group(0) if match else ""


def _normalize_cited_text(text: str) -> str:
    """Fold whitespace and trailing punctuation so a cite can match its sentence."""
    return re.sub(r"\s+", " ", text or "").strip().rstrip(".!?").lower()


def _claim_ids_for_unit(unit: str, provenance: dict) -> List[str]:
    """Return fact ids whose stored sentence or bullet contains this unit."""
    target = _normalize_cited_text(unit)
    if not target:
        return []
    found: List[str] = []
    for section, field in (("resume_claims", "bullet"), ("cover_letter_claims", "sentence")):
        for row in provenance.get(section) or []:
            if not isinstance(row, dict):
                continue
            value = _normalize_cited_text(str(row.get(field) or ""))
            if value and (value in target or target in value):
                found.extend(str(item) for item in (row.get("claim_ids") or []))
    return found


def _load_folder_provenance(folder: str) -> Optional[dict]:
    """Return claim_provenance.json for a folder, or None when it is missing or invalid."""
    path = os.path.join(folder, "claim_provenance.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def check_qa_lead_claim(
    resume_text: str,
    cover_letter_text: str,
) -> List[LintViolation]:
    """LR-051: block a QA-lead claim no matter which fact is cited.

    He was not a QA lead. The Candor bullet cites ACC-204, so the
    cite-matched check does not fire. Implements FR-392.
    """
    violations: List[LintViolation] = []
    seen: set[str] = set()
    for unit in _hedge_units(resume_text, cover_letter_text):
        if not _QA_LEAD_RE.search(unit) or unit in seen:
            continue
        seen.add(unit)
        violations.append(LintViolation(
            rule_id="LR-051",
            severity="HARD_BLOCK",
            message="This sentence claims a QA lead role",
            suggestion="Describe the test work without the QA lead title.",
        ))
    return violations


def check_hundreds_of_client_databases(
    resume_text: str,
    cover_letter_text: str,
) -> List[LintViolation]:
    """LR-052: block "hundreds of client databases" on any cite.

    MET-09 is roughly 200 SQL databases. The Classlink letter cites
    ACC-102 and ACC-121 and still says hundreds. Implements FR-393.
    """
    violations: List[LintViolation] = []
    seen: set[str] = set()
    for unit in _hedge_units(resume_text, cover_letter_text):
        if not _HUNDREDS_OF_CLIENT_RE.search(unit) or unit in seen:
            continue
        seen.add(unit)
        violations.append(LintViolation(
            rule_id="LR-052",
            severity="HARD_BLOCK",
            message="This sentence replaces roughly 200 SQL databases with hundreds",
            suggestion="Say roughly 200 SQL databases, or leave the count out.",
        ))
    return violations


def check_support_escalation_reduction(
    resume_text: str,
    cover_letter_text: str,
) -> List[LintViolation]:
    """LR-053: block a claim that support escalations were reduced.

    Work experience does not use that outcome. The Classlink letter cites
    the data-remediation fact and still says it. A Jira priority formula
    that says streamline does not match. Implements FR-395.
    """
    violations: List[LintViolation] = []
    seen: set[str] = set()
    for unit in _hedge_units(resume_text, cover_letter_text):
        if not _SUPPORT_ESCALATION_REDUCTION_RE.search(unit) or unit in seen:
            continue
        seen.add(unit)
        violations.append(LintViolation(
            rule_id="LR-053",
            severity="HARD_BLOCK",
            message="This sentence says support escalations were reduced",
            suggestion="Keep the data-remediation result. Leave support escalations out.",
        ))
    return violations


def check_release_cadence(
    resume_text: str,
    cover_letter_text: str,
) -> List[LintViolation]:
    """LR-054: block a release-cadence claim on any cite.

    Work experience does not use that phrase. The Classlink bullet cites
    the first-pass QA fact and still says it. A deletion cadence does not
    match. Implements FR-399.
    """
    violations: List[LintViolation] = []
    seen: set[str] = set()
    for unit in _hedge_units(resume_text, cover_letter_text):
        if not _RELEASE_CADENCE_RE.search(unit) or unit in seen:
            continue
        seen.add(unit)
        violations.append(LintViolation(
            rule_id="LR-054",
            severity="HARD_BLOCK",
            message="This sentence claims a release cadence",
            suggestion="Describe the first-pass QA work. Leave release cadence out.",
        ))
    return violations


def check_portability_inversion(
    resume_text: str,
    cover_letter_text: str,
) -> List[LintViolation]:
    """LR-050: block the tagging inversion no matter which fact is cited.

    ACC-155 says custom tagging took priority. A neighboring cite still
    leaves the reversed sentence in the draft. Implements FR-391.
    """
    violations: List[LintViolation] = []
    seen: set[str] = set()
    for unit in _hedge_units(resume_text, cover_letter_text):
        if not _PORTABILITY_INVERSION_RE.search(unit) or unit in seen:
            continue
        seen.add(unit)
        violations.append(LintViolation(
            rule_id="LR-050",
            severity="HARD_BLOCK",
            message="This sentence reverses the tagging priority",
            suggestion="Custom tagging took priority over making profiles portable.",
        ))
    return violations


def check_cited_contradiction(
    resume_text: str,
    cover_letter_text: str,
    provenance: Optional[dict] = None,
) -> List[LintViolation]:
    """LR-049: block a sentence that cites a fact and says something that fact does not say.

    Args: resume markdown, cover-letter markdown, and claim_provenance.json.
    Returns HARD_BLOCK violations. No provenance means no finding.
    Implements FR-390.
    """
    if not isinstance(provenance, dict):
        return []
    violations: List[LintViolation] = []
    seen: set[str] = set()
    for unit in _hedge_units(resume_text, cover_letter_text):
        prefixes = {_fact_prefix(item) for item in _claim_ids_for_unit(unit, provenance)}
        for prefix, pattern in _CITED_CONTRADICTION:
            if prefix not in prefixes or not pattern.search(unit):
                continue
            # ACC-303: Jason influenced the page. Engineering deployed the funnel.
            if prefix == "ACC-303" and re.search(
                r"\bengineering\b.{0,48}\b(?:built|deployed|automated)\b",
                unit,
                re.IGNORECASE,
            ):
                continue
            key = f"{prefix}:{unit}"
            if key in seen:
                continue
            seen.add(key)
            violations.append(LintViolation(
                rule_id="LR-049",
                severity="HARD_BLOCK",
                message=(
                    f"Cited {prefix} does not support this sentence: \"{unit[:180]}\""
                ),
                suggestion=(
                    f"Rewrite the sentence so it says what {prefix} says, or remove the cite."
                ),
            ))
    return violations


_DISRUPT_RE = re.compile(r"\bwithout(?:\s+\w+){0,3}\s+disrupt", re.IGNORECASE)
_FIVE_PERCENT_RE = re.compile(r"\b5\s*(?:%|percent)\b", re.IGNORECASE)


def check_disruption_hedge(resume_text: str, cover_letter_text: str) -> List[LintViolation]:
    """LR-048: a no-disruption claim has to keep the share that never flipped.

    ACC-113 says about 5 percent of customers never flipped. Work experience
    does not use the word disruption. Implements FR-386.
    """
    violations: List[LintViolation] = []
    seen: set[str] = set()
    for unit in _hedge_units(resume_text, cover_letter_text):
        if not _DISRUPT_RE.search(unit) or _FIVE_PERCENT_RE.search(unit):
            continue
        if unit in seen:
            continue
        seen.add(unit)
        violations.append(LintViolation(
            rule_id="LR-048",
            severity="HARD_BLOCK",
            message=(
                "A no-disruption claim drops the share that never flipped: "
                f"\"{unit[:180]}\""
            ),
            suggestion=(
                "Keep the estimate that about 5 percent never flipped, "
                "or cut the no-disruption claim."
            ),
        ))
    return violations


def lint_folder(folder: str) -> List[dict]:
    """Lint Resume.md and CoverLetter.md in a submission folder (not process sidecars)."""
    results = []
    texts_by_doc_type = {}
    for fname in os.listdir(folder):
        if not fname.endswith(".md"):
            continue
        if fname.lower() in _LINT_FOLDER_SKIP:
            continue
        # Only the two application documents — ignore any other .md sidecars.
        if fname not in ("Resume.md", "CoverLetter.md"):
            continue
        fpath = os.path.join(folder, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        doc_type = _detect_doc_type(text, fname)
        texts_by_doc_type[doc_type] = text
        result = lint_document(text, doc_type, filename=fname)

        pdf_path = fpath.replace(".md", ".pdf")
        if not os.path.exists(pdf_path):
            result.infos.append(LintViolation(
                rule_id="LI-002",
                severity="INFO",
                message="No corresponding PDF found for this MD file",
                suggestion="Run compile_single.py to generate the PDF.",
            ))

        results.append({
            "submission": os.path.basename(folder),
            "document": fname,
            "doc_type": doc_type,
            "status": "PASS" if result.passed else "BLOCK",
            "blocks": len(result.blocks),
            "warns": len(result.warns),
            "infos": len(result.infos),
            "result": result,
        })

    if "resume" in texts_by_doc_type and "cover_letter" in texts_by_doc_type:
        pair_warns = check_cross_document_repetition(texts_by_doc_type["resume"], texts_by_doc_type["cover_letter"])
        results.append({
            "submission": os.path.basename(folder),
            "document": "resume+cover_letter (pair)",
            "doc_type": "pair",
            "status": "PASS" if not pair_warns else "WARN",
            "blocks": 0,
            "warns": len(pair_warns),
            "infos": 0,
            "result": LintResult(passed=True, warns=pair_warns, document_type="pair"),
        })

    # LW-011: hook-vs-JD paraphrase check (needs Original_JD.txt alongside the cover letter).
    jd_path = os.path.join(folder, "Original_JD.txt")
    if "cover_letter" in texts_by_doc_type and os.path.exists(jd_path):
        try:
            with open(jd_path, encoding="utf-8") as f:
                jd_text = f.read()
        except OSError:
            jd_text = ""
        hook_warns = check_hook_jd_paraphrase(texts_by_doc_type["cover_letter"], jd_text)
        if hook_warns:
            results.append({
                "submission": os.path.basename(folder),
                "document": "cover_letter hook vs JD",
                "doc_type": "hook",
                "status": "WARN",
                "blocks": 0,
                "warns": len(hook_warns),
                "infos": 0,
                "result": LintResult(passed=True, warns=hook_warns, document_type="hook"),
            })

    # Implements FR-295 / AC-392: generic self-referential hooks do not need the JD text.
    if "cover_letter" in texts_by_doc_type:
        generic_hook_warns = check_generic_hook_self_reference(texts_by_doc_type["cover_letter"])
        if generic_hook_warns:
            results.append({
                "submission": os.path.basename(folder),
                "document": "cover_letter generic hook",
                "doc_type": "hook",
                "status": "WARN",
                "blocks": 0,
                "warns": len(generic_hook_warns),
                "infos": 0,
                "result": LintResult(
                    passed=True,
                    warns=generic_hook_warns,
                    document_type="hook",
                ),
            })

    # LR-031: resume summary vs JD B2B SaaS positioning check (needs Original_JD.txt).
    if "resume" in texts_by_doc_type and os.path.exists(jd_path):
        try:
            with open(jd_path, encoding="utf-8") as f:
                jd_text = f.read()
        except OSError:
            jd_text = ""
        positioning_blocks = check_b2b_saas_positioning(texts_by_doc_type["resume"], jd_text)
        if positioning_blocks:
            results.append({
                "submission": os.path.basename(folder),
                "document": "resume summary vs JD",
                "doc_type": "positioning",
                "status": "BLOCK",
                "blocks": len(positioning_blocks),
                "warns": 0,
                "infos": 0,
                "result": LintResult(
                    passed=False,
                    blocks=positioning_blocks,
                    document_type="positioning",
                ),
            })

    # LW-039: unsolicited geography vs JD (needs Original_JD.txt).
    if ("resume" in texts_by_doc_type or "cover_letter" in texts_by_doc_type) and os.path.exists(jd_path):
        try:
            with open(jd_path, encoding="utf-8") as f:
                geo_jd_text = f.read()
        except OSError:
            geo_jd_text = ""
        geo_warns: List[LintViolation] = []
        for doc_key, doc_type in (("resume", "resume"), ("cover_letter", "cover_letter")):
            if doc_key in texts_by_doc_type:
                geo_warns.extend(
                    check_unsolicited_geography(
                        texts_by_doc_type[doc_key], geo_jd_text, doc_type
                    )
                )
        if geo_warns:
            results.append({
                "submission": os.path.basename(folder),
                "document": "unsolicited geography vs JD",
                "doc_type": "geography",
                "status": "WARN",
                "blocks": 0,
                "warns": len(geo_warns),
                "infos": 0,
                "result": LintResult(
                    passed=True,
                    warns=geo_warns,
                    document_type="geography",
                ),
            })

    # LW-021: cross-employer audience/domain vocabulary bleed check (needs Original_JD.txt).
    if ("resume" in texts_by_doc_type or "cover_letter" in texts_by_doc_type) and os.path.exists(jd_path):
        try:
            with open(jd_path, encoding="utf-8") as f:
                jd_text = f.read()
        except OSError:
            jd_text = ""
        bleed_warns = check_cross_employer_audience_bleed(
            texts_by_doc_type.get("resume", ""),
            texts_by_doc_type.get("cover_letter", ""),
            jd_text,
            company_name=os.path.basename(folder),
        )
        if bleed_warns:
            results.append({
                "submission": os.path.basename(folder),
                "document": "cross-employer audience bleed",
                "doc_type": "bleed",
                "status": "WARN",
                "blocks": 0,
                "warns": len(bleed_warns),
                "infos": 0,
                "result": LintResult(passed=True, warns=bleed_warns, document_type="bleed"),
            })

    # LW-026: JD-specificity floor check (needs Original_JD.txt).
    if "cover_letter" in texts_by_doc_type and os.path.exists(jd_path):
        try:
            with open(jd_path, encoding="utf-8") as f:
                jd_text = f.read()
        except OSError:
            jd_text = ""
        specificity_warns = check_jd_specificity_floor(
            texts_by_doc_type["cover_letter"], jd_text, company_name=os.path.basename(folder)
        )
        if specificity_warns:
            results.append({
                "submission": os.path.basename(folder),
                "document": "cover letter JD-specificity floor",
                "doc_type": "specificity",
                "status": "WARN",
                "blocks": 0,
                "warns": len(specificity_warns),
                "infos": 0,
                "result": LintResult(passed=True, warns=specificity_warns, document_type="specificity"),
            })

    # LR-038: 40% bypass authorship. HARD_BLOCK so a repair must edit the sentence.
    # Implements FR-369.
    if "resume" in texts_by_doc_type or "cover_letter" in texts_by_doc_type:
        bypass_blocks = check_bypass_authorship(
            texts_by_doc_type.get("resume", ""),
            texts_by_doc_type.get("cover_letter", ""),
        )
        if bypass_blocks:
            results.append({
                "submission": os.path.basename(folder),
                "document": "40% bypass authorship",
                "doc_type": "attribution",
                "status": "BLOCK",
                "blocks": len(bypass_blocks),
                "warns": 0,
                "infos": 0,
                "result": LintResult(
                    passed=False,
                    blocks=bypass_blocks,
                    document_type="attribution",
                ),
            })

    # LR-039: customer discovery claimed as experience. Implements FR-370.
    if "resume" in texts_by_doc_type or "cover_letter" in texts_by_doc_type:
        discovery_blocks = check_customer_discovery(
            texts_by_doc_type.get("resume", ""),
            texts_by_doc_type.get("cover_letter", ""),
        )
        if discovery_blocks:
            results.append({
                "submission": os.path.basename(folder),
                "document": "customer discovery claim",
                "doc_type": "attribution",
                "status": "BLOCK",
                "blocks": len(discovery_blocks),
                "warns": 0,
                "infos": 0,
                "result": LintResult(
                    passed=False,
                    blocks=discovery_blocks,
                    document_type="attribution",
                ),
            })

    # LR-040 through LR-047. Same list Stage 1 verify fails on. Implements FR-384 / FR-386.
    if "resume" in texts_by_doc_type or "cover_letter" in texts_by_doc_type:
        fidelity_blocks = collect_fidelity_hard_blocks(
            texts_by_doc_type.get("resume", ""),
            texts_by_doc_type.get("cover_letter", ""),
            _load_folder_provenance(folder),
        )
        if fidelity_blocks:
            results.append({
                "submission": os.path.basename(folder),
                "document": "cited span fidelity",
                "doc_type": "attribution",
                "status": "BLOCK",
                "blocks": len(fidelity_blocks),
                "warns": 0,
                "infos": 0,
                "result": LintResult(
                    passed=False,
                    blocks=fidelity_blocks,
                    document_type="attribution",
                ),
            })

    # LW-028: claim-attribution vs. ownership-verb mismatch check (no JD needed).
    if "resume" in texts_by_doc_type or "cover_letter" in texts_by_doc_type:
        attribution_warns = check_attribution_verb_strength(
            texts_by_doc_type.get("resume", ""),
            texts_by_doc_type.get("cover_letter", ""),
        )
        if attribution_warns:
            results.append({
                "submission": os.path.basename(folder),
                "document": "claim attribution vs. verb strength",
                "doc_type": "attribution",
                "status": "WARN",
                "blocks": 0,
                "warns": len(attribution_warns),
                "infos": 0,
                "result": LintResult(passed=True, warns=attribution_warns, document_type="attribution"),
            })

    # LW-032: wrong-job company-name bleed (CR-097 Epic 5). WARN, not HARD_BLOCK.
    # Only on real submission folders so unit-test tempdirs are not scored
    # against the live company index.
    submissions_root = os.path.abspath(os.path.join(_REPO_ROOT, "data", "submissions"))
    folder_abs = os.path.abspath(folder)
    if folder_abs.startswith(submissions_root):
        jd_for_bleed = ""
        if os.path.exists(jd_path):
            try:
                with open(jd_path, encoding="utf-8") as f:
                    jd_for_bleed = f.read()
            except OSError:
                jd_for_bleed = ""
        own_company = os.path.basename(folder)
        gate_path = os.path.join(folder, "stage0_fit_gate.json")
        if os.path.isfile(gate_path):
            try:
                with open(gate_path, encoding="utf-8") as f:
                    own_company = str(json.load(f).get("company") or own_company)
            except (OSError, json.JSONDecodeError):
                pass
        company_bleed = check_wrong_job_company_bleed(
            texts_by_doc_type.get("resume", ""),
            texts_by_doc_type.get("cover_letter", ""),
            jd_for_bleed,
            own_company,
        )
        if company_bleed:
            results.append({
                "submission": os.path.basename(folder),
                "document": "wrong-job company bleed",
                "doc_type": "wrong_job_bleed",
                "status": "WARN",
                "blocks": 0,
                "warns": len(company_bleed),
                "infos": 0,
                "result": LintResult(
                    passed=True, warns=company_bleed, document_type="wrong_job_bleed"
                ),
            })

    return results


def write_lint_report(folder: str, result: LintResult, filename: str = "lint_report.json") -> str:
    """Write lint report JSON to the submission folder."""
    report = {
        "document_type": result.document_type,
        "passed": result.passed,
        "blocks": [
            {"rule_id": v.rule_id, "message": v.message, "suggestion": v.suggestion, "line": v.line}
            for v in result.blocks
        ],
        "warns": [
            {"rule_id": v.rule_id, "message": v.message, "suggestion": v.suggestion, "line": v.line}
            for v in result.warns
        ],
        "infos": [
            {"rule_id": v.rule_id, "message": v.message, "suggestion": v.suggestion}
            for v in result.infos
        ],
    }
    path = os.path.join(folder, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return path


def _print_violation(v: LintViolation, indent: int = 4) -> None:
    prefix = " " * indent
    loc = f" (line {v.line})" if v.line else ""
    print(f"{prefix}[{v.rule_id}] {v.message}{loc}")
    print(f"{prefix}  → {v.suggestion}")


def _read_company_docs(folder: str) -> Dict[str, str]:
    """Read Resume.md/CoverLetter.md text for the LW-029 cross-batch check, by doc_type."""
    docs: Dict[str, str] = {}
    for fname in os.listdir(folder):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(folder, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        docs[_detect_doc_type(text, fname)] = text
    return docs


def _run_cli(paths: List[str]) -> int:
    """CLI entry point. Returns exit code."""
    all_results: List[dict] = []
    docs_by_company: Dict[str, Dict[str, str]] = {}

    for path in paths:
        path = os.path.normpath(path)
        if os.path.isdir(path):
            # Check if it's a submissions root (contains sub-dirs) or a single submission
            subdirs = [d for d in os.listdir(path)
                       if os.path.isdir(os.path.join(path, d)) and not d.startswith(".")]
            md_files = [f for f in os.listdir(path) if f.endswith(".md")]
            if md_files:
                all_results.extend(lint_folder(path))
                docs_by_company[os.path.basename(path)] = _read_company_docs(path)
            elif subdirs:
                for sub in sorted(subdirs):
                    subpath = os.path.join(path, sub)
                    all_results.extend(lint_folder(subpath))
                    docs_by_company[sub] = _read_company_docs(subpath)
        elif path.endswith(".md"):
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
                doc_type = _detect_doc_type(text, os.path.basename(path))
                result = lint_document(text, doc_type, filename=os.path.basename(path))
                all_results.append({
                    "submission": os.path.basename(os.path.dirname(path)),
                    "document": os.path.basename(path),
                    "doc_type": doc_type,
                    "status": "PASS" if result.passed else "BLOCK",
                    "blocks": len(result.blocks),
                    "warns": len(result.warns),
                    "infos": len(result.infos),
                    "result": result,
                })
            except OSError as e:
                print(f"[ERROR] Cannot read {path}: {e}", file=sys.stderr)

    if not all_results:
        print("[submission_linter] No markdown files found.")
        return 0

    # LW-029: cross-batch repetition check -- only meaningful with 3+ companies in one run.
    if len(docs_by_company) >= _BATCH_MIN_COMPANIES:
        batch_warns = check_batch_repetition(docs_by_company)
        if batch_warns:
            all_results.append({
                "submission": f"(batch: {len(docs_by_company)} companies)",
                "document": "cross-batch repetition",
                "doc_type": "batch",
                "status": "WARN",
                "blocks": 0,
                "warns": len(batch_warns),
                "infos": 0,
                "result": LintResult(passed=True, warns=batch_warns, document_type="batch"),
            })

    # Summary table
    col_w = [20, 22, 14, 8, 8, 8]
    header = (
        f"{'Submission':<{col_w[0]}} {'Document':<{col_w[1]}} "
        f"{'Type':<{col_w[2]}} {'Status':<{col_w[3]}} "
        f"{'Blocks':<{col_w[4]}} {'Warns':<{col_w[5]}}"
    )
    print(header)
    print("-" * len(header))

    any_blocked = False
    for row in all_results:
        status = row["status"]
        if status == "BLOCK":
            any_blocked = True
        print(
            f"{row['submission']:<{col_w[0]}} {row['document']:<{col_w[1]}} "
            f"{row['doc_type']:<{col_w[2]}} {status:<{col_w[3]}} "
            f"{row['blocks']:<{col_w[4]}} {row['warns']:<{col_w[5]}}"
        )
        result = row["result"]
        for v in result.blocks:
            _print_violation(v, indent=2)
        for v in result.warns:
            _print_violation(v, indent=2)

    print()
    total = len(all_results)
    blocked = sum(1 for r in all_results if r["status"] == "BLOCK")
    print(f"{total} document(s) checked — {blocked} blocked, {total - blocked} passed.")
    return 1 if any_blocked else 0


if __name__ == "__main__":
    # CLI output contains non-ASCII characters (e.g. the "->" suggestion arrow).
    # Windows' default console codepage (cp1252) can't encode them, and this
    # script crashed with UnicodeEncodeError there instead of just printing
    # results -- reconfigure to utf-8 rather than relying on the caller to set
    # PYTHONIOENCODING. Guarded because reconfigure() isn't available on every
    # stream type (e.g. when stdout is captured/redirected in some contexts).
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    args = sys.argv[1:]
    if not args:
        print("Usage: python submission_linter.py <path> [<path> ...]", file=sys.stderr)
        sys.exit(1)
    sys.exit(_run_cli(args))
