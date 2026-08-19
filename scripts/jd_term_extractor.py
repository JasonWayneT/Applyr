"""
CR-073 Epic 2: JD-specific literal hard-skill/tool coverage gate.

Diffs Jason's own known-true skill/tool vocabulary (data/skills_catalog.json's flat
tool list + data/master_claims_tags_only.json's claim tags) against a target JD's
text, then against the drafted resume/cover letter, to surface only terms that are:

  (a) genuinely true of Jason -- drawn ONLY from those two ground-truth sources.
      This is what makes fabrication impossible by construction, not a filter
      bolted on after free-text NLP extraction from arbitrary JD prose (which
      would risk surfacing terms Jason doesn't actually have).
  (b) present in the JD text (so genuinely requested/relevant to this posting), AND
  (c) absent from the RESUME specifically (a real coverage gap).

Deliberately resume-scoped, not resume-or-cover-letter pooled (corrected 2026-08-04,
Jason-prompted). The ATS/ranking mechanisms this check targets -- Jobscan's match-rate
algorithm, SAP SuccessFactors' Boolean recruiter search -- parse and score the resume,
not the cover letter. An earlier version treated a term as "covered" if it appeared in
either document, which could mask a real resume-side gap by crediting a mention that
only exists in cover-letter prose. Cover letters are also not a keyword-coverage target
in their own right: cramming JD vocabulary into 250-400 words of prose collides directly
with this project's own hard-blocked authenticity rules (LW-011 JD-paraphrase hook,
LW-012 assertion-of-fit overclaim). So the fix is not "run the same check on the cover
letter too" -- it's "stop letting the cover letter dilute the resume's own signal."
`cover_letter_only_mentions` below is kept purely as an FYI, never as coverage credit.

Distinct from two existing checks:
  - verify_submission.py's `jd_keyword_coverage`: a static 14-word list
    (saas/b2b/platform/agile/...) applied identically to every JD -- a generic
    domain-signal check, not a per-JD extraction.
  - check_ground_truth_coverage.py: flags unused *true claims* by claim ID/tag
    relevance to the JD. This script flags unmatched *literal JD terms* instead --
    the mirror-image failure mode (JD says it, nothing in the doc says it back),
    per Jobscan's published methodology (hard skills / job title / other keywords
    as the primary drivers of rule-based ATS filters).

WARN-level / informational only. Does not replace rubric scoring.

Wired into generate-submission/SKILL.md's Stage 1 pre-handoff gate (2026-08-04) alongside
check_ground_truth_coverage.py -- until this change it only ever surfaced inside
verify_submission.py's post-hoc receipt (Stage 2/finalization), which meant a real JD-term
gap could sit unresolved through the entire authoring pass and only get noticed after the
document was already "done." Same posture as ground-truth coverage: a required step the
author must resolve during Stage 1, not a passive audit trail.

Usage:
    python scripts/jd_term_extractor.py data/submissions/{company}
    python scripts/jd_term_extractor.py data/submissions/{c1} data/submissions/{c2} ...
"""
from __future__ import annotations

import json
import os
import re
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)

_WORD_BOUNDARY_CACHE: dict = {}

# Tuned 2026-08-04 against real submissions (Story 2.4): master_claims_tags_only.json's
# tags mix genuine hard-skill/domain nouns (SLA, Product Lifecycle, Vulnerability
# Management, Go-to-Market -- kept) with generic soft-skill/process adjectives
# (Collaboration, Leadership, Velocity -- excluded) that appear in nearly every PM JD
# regardless of actual overlap, diluting the signal. Mirrors Jobscan's own published
# hard-skill-vs-soft-skill split rather than treating every claim tag as equally
# JD-specific. Small and reviewable by design -- extend by hand if a future spot-check
# finds another generic term slipping through, don't over-engineer this into NLP.
_GENERIC_SOFT_SKILL_TERMS = {
    "collaboration",
    "communication",
    "leadership",
    "delivery",
    "velocity",
    "cross-functional",
    "enterprise",
    "enterprise clients",
}


def _load_true_vocabulary() -> dict:
    """Returns {lowercased_term: canonical_display_form}, sourced only from
    data/skills_catalog.json (flat tool list) and data/master_claims_tags_only.json
    (claim tags) -- the two structured ground-truth sources named in CR-073's
    Decision. Skips any tag/tool containing ':' or '/' (compound labels like
    "Technical Literacy: HTML/CSS/JavaScript") since those don't match as a single
    literal phrase against resume prose -- not worth the false-negative noise.
    """
    vocab: dict = {}

    catalog_path = os.path.join(_REPO_ROOT, "data", "skills_catalog.json")
    try:
        with open(catalog_path, encoding="utf-8") as f:
            catalog = json.load(f)
        for terms in catalog.values():
            for t in terms:
                if ":" in t or "/" in t:
                    continue
                vocab.setdefault(t.lower(), t)
    except (OSError, json.JSONDecodeError):
        pass

    tags_path = os.path.join(_REPO_ROOT, "data", "master_claims_tags_only.json")
    try:
        with open(tags_path, encoding="utf-8") as f:
            claims = json.load(f)
        for claim in claims.values():
            for tag in claim.get("tags", []):
                if ":" in tag or "/" in tag or tag.lower() in _GENERIC_SOFT_SKILL_TERMS:
                    continue
                vocab.setdefault(tag.lower(), tag)
    except (OSError, json.JSONDecodeError):
        pass

    return vocab


def _term_present(term_lower: str, text_lower: str) -> bool:
    """Whole-phrase, case-insensitive, word-boundary-aware match (so e.g. "AI"
    doesn't match inside "said", and "SQL" doesn't match inside a longer token)."""
    pattern = _WORD_BOUNDARY_CACHE.get(term_lower)
    if pattern is None:
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(term_lower) + r"(?![a-z0-9])")
        _WORD_BOUNDARY_CACHE[term_lower] = pattern
    return bool(pattern.search(text_lower))


# Added 2026-08-18: exact-literal matching produced real false "missing" flags
# whenever the resume used a different word form of the same term ("Support"
# vs "Supported", "Reliability" vs "reliable") -- found in a real 6-company
# batch the same day. A hand-rolled suffix-stripper, not a stemming library:
# consistent with this repo's deliberate no-NLTK/spaCy local-first posture
# (confirmed nothing similar exists anywhere in scripts/). Longest suffix
# first so e.g. "-ations" strips before the shorter "-s" would. The min stem
# length of 4 guards short/important terms (SQL, AI, API, UX) from ever
# reaching the strip loop with a false match.
_STEM_SUFFIXES = ("ations", "ation", "ibility", "ability", "ities",
                   "ings", "ing", "edly", "ed", "ers", "er", "ably", "ibly",
                   "able", "ible", "ily", "es", "s")
_STEM_TOKEN_RE = re.compile(r"[a-z][a-z-]*")


def _stem(word: str) -> str:
    w = word.lower()
    for suf in _STEM_SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def _term_present_stemmed(term_lower: str, text_lower: str) -> bool:
    """Single-word terms only (multi-word phrases keep the exact literal
    match in _term_present -- stemming a phrase's word order/components is a
    different, riskier problem this fix doesn't attempt). Stems both the
    term and every word in the text, so "Support" matches "supported" and
    "Reliability" matches "reliable" without a hand-maintained variant list
    per term."""
    if " " in term_lower:
        return _term_present(term_lower, text_lower)
    term_stem = _stem(term_lower)
    return any(_stem(tok) == term_stem for tok in _STEM_TOKEN_RE.findall(text_lower))


def find_jd_term_gaps(jd_text: str, resume_text: str, cover_letter_text: str = "") -> dict:
    """Core CR-073 Epic 2 check.

    Primary signal is resume-only coverage -- the document the ATS mechanisms this
    check targets actually parse and rank. Cover-letter presence is reported
    separately, informational only, and never counts as "covered."
    """
    vocab = _load_true_vocabulary()
    jd_lower = jd_text.lower()
    resume_lower = resume_text.lower()
    cover_lower = cover_letter_text.lower()

    # JD-side detection stays exact-literal (_term_present) -- the question there
    # is only "does the catalog term's own spelling appear in the JD," not a word-
    # form question. Resume/cover-letter-side detection uses the stemmed matcher
    # (_term_present_stemmed) so a genuine word-form variant ("Supported" for
    # "Support", "reliable" for "Reliability") counts as covered instead of
    # manufacturing a false gap -- confirmed real 2026-08-18 across a 6-company
    # batch.
    jd_required = sorted(
        {display for term, display in vocab.items() if _term_present(term, jd_lower)}
    )
    missing_from_resume = sorted(
        term for term in jd_required if not _term_present_stemmed(term.lower(), resume_lower)
    )
    # Of what's missing from the resume, note (informational only) which ones happen
    # to already appear in the cover letter -- doesn't reduce the gap, just useful
    # context for whoever resolves it (e.g. "already gestured at in the letter, still
    # needs to land in the resume itself").
    cover_letter_only_mentions = sorted(
        term for term in missing_from_resume if _term_present_stemmed(term.lower(), cover_lower)
    )
    return {
        "true_vocabulary_size": len(vocab),
        "jd_required_true_terms": jd_required,
        "missing_from_resume": missing_from_resume,
        "cover_letter_only_mentions": cover_letter_only_mentions,
    }


def check_folder(folder: str) -> dict:
    folder = folder.rstrip("/\\")
    company = os.path.basename(folder)
    jd_path = os.path.join(folder, "Original_JD.txt")
    resume_path = os.path.join(folder, "Resume.md")
    cover_path = os.path.join(folder, "CoverLetter.md")

    if not os.path.exists(jd_path):
        return {"submission": company, "generated_by": "scripts/jd_term_extractor.py", "error": "Original_JD.txt not found"}
    if not os.path.exists(resume_path):
        return {"submission": company, "generated_by": "scripts/jd_term_extractor.py", "error": "Resume.md not found"}

    jd_text = open(jd_path, encoding="utf-8").read()
    resume_text = open(resume_path, encoding="utf-8").read()
    cover_text = open(cover_path, encoding="utf-8").read() if os.path.exists(cover_path) else ""

    result = find_jd_term_gaps(jd_text, resume_text, cover_text)
    result["submission"] = company
    result["generated_by"] = "scripts/jd_term_extractor.py"
    return result


def main() -> None:
    folders = sys.argv[1:]
    if not folders:
        print(__doc__)
        sys.exit(1)

    any_flagged = False
    for folder in folders:
        result = check_folder(folder)
        out_path = os.path.join(folder.rstrip("/\\"), "jd_term_gaps.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        if result.get("error"):
            print(f"{result['submission']}: SKIPPED -- {result['error']}")
            continue

        missing = result["missing_from_resume"]
        if missing:
            any_flagged = True
            print(f"{result['submission']}: ATTENTION -- {len(missing)} JD-required term(s) missing from resume")
            for term in missing:
                cover_note = " (mentioned in cover letter only)" if term in result["cover_letter_only_mentions"] else ""
                print(f"    - {term}{cover_note}")
        else:
            print(f"{result['submission']}: clean -- no JD-required true term missing from resume")

    if any_flagged:
        sys.exit(1)


if __name__ == "__main__":
    main()
