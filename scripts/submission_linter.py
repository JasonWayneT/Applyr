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
        pattern=fr"\b{PREVIOUS_YEARS_EXPERIENCE}\+?\s*years\b|\b{PREVIOUS_YEARS_WORD} years\b",
        message=f"Superseded years-of-experience figure detected (should be {CURRENT_YEARS_EXPERIENCE}, not {PREVIOUS_YEARS_EXPERIENCE}/{PREVIOUS_YEARS_EXPERIENCE}+/{PREVIOUS_YEARS_WORD})",
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
    # exact pattern that already failed silently for LR-016/LW-013/LW-021 before each got
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
        pattern=r"\b(Snowflake|Tableau|FHIR|Docker|Kubernetes|Looker|Amplitude|Mixpanel|Power BI|Databricks)\b",
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
]

WARN_RULES: List[LintRule] = [
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
            r"|paramount|foster(?:ed)?|showcas(?:e|es|ing))\b"
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
            if g.strip():
                mentioned.add(g.strip().rstrip("s").lower())

    bad = []
    for mention in mentioned:
        if not any(partner in mention for partner in _VERIFIED_PARTNERS):
            bad.append(mention)
    return ", ".join(bad[:3]) if bad else None


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
                if re.search(rule.pattern, line, flags):
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
    for phrase in sorted(set(candidates), key=len, reverse=True):
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


def _extract_summary(resume_text: str) -> str:
    """Return the PROFESSIONAL SUMMARY section body (between its heading and the next ## heading)."""
    m = re.search(r"##\s*PROFESSIONAL SUMMARY\s*\n(.*?)(?=\n##\s|\Z)", resume_text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def check_b2b_saas_positioning(resume_text: str, jd_text: str) -> List[LintViolation]:
    """LW-013: flag a resume summary that defaults to 'B2B SaaS' framing the JD itself never uses.

    CLAUDE.md's "Required Document Structure" section already states this as a prose rule (added
    2026-07-21): the optional positioning subtitle "must mirror the specific JD's own framing --
    never default to 'B2B SaaS Platform Product Manager'". Found violated on all 9 real summaries
    in the 2026-07-21 batch review despite the rule already being written down -- a prose instruction
    alone did not survive drafting pressure, same failure mode as LR-016/LR-015 before this was
    mechanized. WARN, not HARD_BLOCK: a JD can genuinely be B2B SaaS without using the literal term
    (an enterprise software JD, for instance) -- this forces a check, not an automatic rewrite.
    """
    summary = _extract_summary(resume_text)
    if not summary or not jd_text.strip():
        return []
    if not re.search(r"b2b\s*saas", summary, re.IGNORECASE):
        return []
    if re.search(r"\bsaas\b", jd_text, re.IGNORECASE):
        return []
    return [LintViolation(
        rule_id="LW-013",
        severity="WARN",
        message=(
            "Resume summary frames the role as 'B2B SaaS' but Original_JD.txt never uses the term "
            "'SaaS' anywhere -- likely default positioning rather than positioning drawn from this JD."
        ),
        suggestion=(
            "Re-read the JD's own framing of what it is (vertical software, marketplace, platform, "
            "etc.) and match the summary to that instead, or drop the positioning language entirely "
            "if no crisp honest framing fits."
        ),
    )]


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
    "operational", "organization", "owner", "owners", "planning", "prioritize",
    "prioritized", "prioritization", "programs", "regulated", "release",
    "sales", "streamline", "support", "supporting", "trade-offs", "validate",
    "validation", "ai-assisted", "go-to-market", "cross-functional",
}

_PAST_EMPLOYER_NAMES = ("cision", "sterkly", "zero to sixty")

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
    distinctive = _jd_distinctive_words(jd_text, company_name=company_name)
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
            if not para or not any(emp in para.lower() for emp in _PAST_EMPLOYER_NAMES):
                continue
            hit_words = _find_hits(para, distinctive)
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


def check_jd_specificity_floor(cover_letter_text: str, jd_text: str, company_name: str = "") -> List[LintViolation]:
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
    if not cover_letter_text.strip() or not jd_text.strip():
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
                if not any(a in unit_lower for a in anchors):
                    continue
                verb_hits = [
                    v for v in _OWNERSHIP_VERBS_ANCHOR
                    if re.search(rf"\b{re.escape(v)}\b", unit_lower)
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
                    if re.search(rf"\b{re.escape(v)}\b", unit_lower)
                ]

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


def lint_folder(folder: str) -> List[dict]:
    """Lint all .md files in a submission folder. Returns list of summary dicts."""
    results = []
    texts_by_doc_type = {}
    for fname in os.listdir(folder):
        if not fname.endswith(".md"):
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

    # LW-013: resume summary vs JD B2B SaaS positioning check (needs Original_JD.txt).
    if "resume" in texts_by_doc_type and os.path.exists(jd_path):
        try:
            with open(jd_path, encoding="utf-8") as f:
                jd_text = f.read()
        except OSError:
            jd_text = ""
        positioning_warns = check_b2b_saas_positioning(texts_by_doc_type["resume"], jd_text)
        if positioning_warns:
            results.append({
                "submission": os.path.basename(folder),
                "document": "resume summary vs JD",
                "doc_type": "positioning",
                "status": "WARN",
                "blocks": 0,
                "warns": len(positioning_warns),
                "infos": 0,
                "result": LintResult(passed=True, warns=positioning_warns, document_type="positioning"),
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
    args = sys.argv[1:]
    if not args:
        print("Usage: python submission_linter.py <path> [<path> ...]", file=sys.stderr)
        sys.exit(1)
    sys.exit(_run_cli(args))
