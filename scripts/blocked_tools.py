#!/usr/bin/env python3
"""Shared hard-blocked tool vocabulary for Stage 0 fit and output linting.

Invariant: Stage 0 gap classification and Stage 2/HM linting must agree on which
named tools Jason cannot claim. Drift previously let Stage 0 treat Amplitude as
a soft/unknown domain while LR-026 hard-blocked it in drafted docs (and the
reverse for Procore/Smartsheet/Monday.com — Stage 0 knew, LR-026 did not).

Display forms (capitalization / Power BI spacing) are derived for lint regexes.
Matching forms are lowercase phrases suitable for ``\\b`` alternation.
"""
from __future__ import annotations

import re

# Lowercase match phrases. Multi-word entries use the spaced form; add compact
# aliases where JDs commonly omit the space (powerbi, monday.com).
HARD_BLOCKED_TOOLS: frozenset[str] = frozenset({
    # Healthcare data standards
    "fhir", "hl7", "epic", "cerner", "meditech", "athenahealth",
    "redox", "mirth", "smartonfhir", "dicom",
    # Data warehouse / analytics infrastructure
    "snowflake", "databricks", "dbt", "fivetran", "airbyte",
    "tableau", "looker", "power bi", "powerbi", "qlik", "sisense",
    "amplitude", "mixpanel",
    # Infrastructure / cloud infra
    # Docker is personal-only (WE ACC-172, corrected 2026-08-21). Not a
    # professional Cision skill. Block it the same as other unverified infra.
    "docker", "kubernetes", "k8s", "terraform", "helm",
    "ansible", "puppet", "chef",
    # ML / AI frameworks (engineering, not tooling)
    "tensorflow", "pytorch", "keras", "scikit-learn", "huggingface",
    "mlflow", "kubeflow", "sagemaker",
    # Marketing / support / chat tooling not in resume
    "braze",
    "zendesk", "freshdesk",
    "intercom",
    "launchdarkly",
    # Finance/payments/billing tools
    "stripe", "braintree", "adyen", "recurly", "chargebee",
    "netsuite", "workday", "sap",
    # Legal/contract
    "ironclad", "docusign",
    # Domain-specific
    "coupa",
    "veeva",
    # Construction / work-mgmt platforms (2026-08-10 pressure test)
    "procore",
    "smartsheet",
    "monday.com",
    # Insurance-industry platforms (2026-08-15, Mercury Insurance real miss --
    # see looks_like_named_tool()/load_skills_catalog_terms() below for the
    # allow-list layer that catches tools not on this necessarily-incomplete
    # deny-list going forward)
    "guidewire", "guidewire policycenter", "duck creek", "majesco",
    # Programming languages not in Jason's history (2026-09-03, Jason-supplied
    # after alphasense JD wanted hands-on Python -- not in workExperience.md,
    # do not claim it)
    "python",
})

# Prefer human-readable forms in lint messages / alternation (longest first).
_DISPLAY_ALIASES: dict[str, str] = {
    "power bi": "Power BI",
    "powerbi": "Power BI",
    "monday.com": "Monday.com",
    "scikit-learn": "scikit-learn",
    "k8s": "Kubernetes",
    "hl7": "HL7",
    "fhir": "FHIR",
    "dbt": "dbt",
    "sap": "SAP",
}


def _epic_pattern(esc: str) -> str:
    """``epic`` (the healthcare EHR company) false-positives on the ordinary
    Agile noun ("epic"/"epics" as in epics and stories) -- live miss on binance,
    2026-09-19, where ACC-179's own approved language ("drafting epics and
    stories") tripped the healthcare-tool block. Same negative-lookahead shape
    as the ``workday`` exclusion below: exclude the Agile idiom, not the word.
    """
    return rf"{esc}s?(?!\s*(?:-level|\s+and\s+(?:user\s+)?stor(?:y|ies)|\s+hierarch))"


def hard_blocked_tool_pattern() -> re.Pattern[str]:
    """Case-insensitive word-boundary alternation over HARD_BLOCKED_TOOLS.

    ``workday`` keeps a negative lookahead so capacity phrasing like
    ``workday-hours`` / ``workday hours`` is not treated as the Workday HCM
    product (live false positive on neogen/precisepk/procede, 2026-08-11).
    ``epic`` keeps a similar lookahead for the Agile-noun sense (see
    ``_epic_pattern``).
    """
    parts: list[str] = []
    for tool in sorted(HARD_BLOCKED_TOOLS, key=len, reverse=True):
        esc = re.escape(tool)
        if tool == "workday":
            parts.append(rf"{esc}(?![\s-]*hours?\b)")
        elif tool == "epic":
            parts.append(_epic_pattern(esc))
        else:
            parts.append(esc)
    pattern = r"\b(?:" + "|".join(parts) + r")\b"
    return re.compile(pattern, re.I)


def hard_blocked_tools_lint_alternation() -> str:
    """Alternation string for submission_linter LR-026 (display-oriented).

    Includes spaced Power BI and common Title Case spellings. Compact aliases
    like powerbi remain covered via the Stage 0 matcher; the linter catches
    drafted prose which almost always uses the spaced/Title form.

    Workday uses the same hours-compound exclusion as ``hard_blocked_tool_pattern``.
    """
    display: set[str] = set()
    for tool in HARD_BLOCKED_TOOLS:
        if tool in _DISPLAY_ALIASES:
            display.add(_DISPLAY_ALIASES[tool])
            continue
        if tool in {"powerbi", "k8s"}:
            continue  # covered by display alias of the canonical form
        if "." in tool:
            display.add(tool)
            continue
        display.add(tool.title() if tool.islower() and " " not in tool else tool)
    parts: list[str] = []
    for t in sorted(display, key=len, reverse=True):
        esc = re.escape(t)
        if t.lower() == "workday":
            parts.append(rf"{esc}(?![\s-]*hours?\b)")
        elif t.lower() == "epic":
            parts.append(_epic_pattern(esc))
        else:
            parts.append(esc)
    return "|".join(parts)


# ---------------------------------------------------------------------------
# Allow-list layer (CR-092, 2026-08-15)
# ---------------------------------------------------------------------------
# HARD_BLOCKED_TOOLS above is a deny-list -- it will always miss a tool
# nobody thought to add in advance (Guidewire's absence, found real on a
# Mercury Insurance JD, was the entire failure mode, not a missing entry).
# OWASP's Input Validation Cheat Sheet and general access-control practice
# converge on the same fix whenever the safe set is enumerable and the
# unsafe set is not: allow-list as the primary defense, deny-list layered on
# top as a "confirmed cannot claim, ever" tier -- not the only mechanism.
# Jason's verified tool set (data/skills_catalog.json) is small and
# enumerable; the universe of tools a JD might name is not.

import json as _json
import os as _os

_REPO_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_DEFAULT_SKILLS_PATH = _os.path.join(_REPO_ROOT, "data", "skills_catalog.json")


def load_skills_catalog_terms(skills_path: str | None = None) -> frozenset[str]:
    """Every verified tool/skill term from data/skills_catalog.json, lowercased.

    This is the allow-list: a requirement naming a tool that appears here is
    a clean anchor (Jason genuinely has it). Promoted here from a private
    copy that used to live only in build_stage0_fit_gate.py so Stage 0 and
    any future linter check share one source, the same reasoning that
    already keeps HARD_BLOCKED_TOOLS itself shared across Stage 0 and
    submission_linter's LR-026 (see module docstring)."""
    path = skills_path or _DEFAULT_SKILLS_PATH
    terms: set[str] = set()
    if _os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as handle:
                catalog = _json.load(handle)
            for values in catalog.values():
                for t in values:
                    t = t.strip().lower()
                    if t:
                        terms.add(t)
        except Exception:
            pass
    return frozenset(terms)


# Common capitalized JD words that are not tool/product names -- excluded so
# the mid-sentence-capitalization heuristic below doesn't false-positive on
# ordinary JD vocabulary (role words, methodology names, day-to-day nouns).
# Not exhaustive by design: false positives here just mean an extra soft WARN
# a human dismisses in one glance, which is a far cheaper failure mode than
# the silent false-negative this whole layer exists to fix.
_TOOL_DETECTION_STOPWORDS: frozenset[str] = frozenset({
    "product", "manager", "senior", "junior", "lead", "director", "head",
    "agile", "scrum", "kanban", "waterfall", "saas", "b2b", "b2c",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
    "united", "states", "america", "remote", "hybrid", "onsite",
    "experience", "requirements", "qualifications", "responsibilities",
    "excellent", "strong", "proven", "demonstrated", "ability",
    # Added 2026-09-01 (CR-108 cascade testing): these were caught only after
    # this stopword list started feeding a BLOCKING gate (Stage0NeedsInput via
    # _prepare_skill_confirmations), not just the original WARN-tier use this
    # list's own comment above describes. A false positive here now produces
    # an individually-blocking "Have you used X in your work?" review-center
    # question per company, not a glance-and-dismiss WARN -- so degree/field/
    # domain words (which appear in nearly every JD's education/domain lines)
    # need to be excluded proactively, not just as they're each independently
    # rediscovered. Confirmed live on one real archived JD (early_warning):
    # Engineering, STEM, Computer Science, Information Systems, Data
    # Architecture, Data Engineering, Data Product Management, Software
    # Engineering, Platform Engineering, Platform Product Management,
    # Analytics Engineering, and Visa all fired as false "named tool" hits.
    "engineering", "science", "sciences", "computer", "stem", "information",
    "systems", "architecture", "analytics", "platform", "visa", "degree",
    "data", "software", "business", "healthcare", "health", "public",
    "administration", "administrative",
    "bachelor", "bachelors", "master", "masters", "mba", "phd", "diploma",
    "field", "discipline", "related", "equivalent", "certification",
    "certifications", "certified", "management", "engineer", "engineers",
    # Added 2026-09-02 (CR-109 / BUG-001): JD trait words, qualifier words,
    # role-title words, and generic tech nouns confirmed firing as false
    # "named tool" blocking questions in a live Review Center queue (Spirit,
    # Thinking, Fluency, Prioritization, Methodologies, Competencies,
    # Preferred, Implementation Consultant, Solutions Architect, Talent
    # Acquisition, API, HCM, GTM, LLM, Finance, Legal, Sales). The label-shape
    # guard in looks_like_named_tool() kills the colon/header variants of
    # these; the stopwords cover the same vocabulary when it appears without
    # that punctuation. The BAD_DATA review answer (FR-287) is the durable
    # learning loop for whatever still slips past both layers.
    "preferred", "highly", "bonus", "ideally",
    "spirit", "entrepreneurial", "mindset", "thinking", "fluency",
    "prioritization", "methodologies", "competencies", "aptitude", "acumen",
    "ownership", "communication", "communications", "collaboration",
    "solutions", "implementation", "integration", "consultant", "talent",
    "acquisition", "finance", "legal", "sales", "marketing", "recruiting",
    "api", "apis", "rest", "json", "xml", "llm", "llms", "ai", "ml",
    "machine", "learning", "gtm", "hcm", "ats", "crm", "hris",
    # Added 2026-09-02 (CR-109 follow-up): second batch confirmed in a live
    # Stage 0 run the same day — Tools And Frameworks, Utilizing Strategic
    # Marketing, SKILLS AND REQUIRED, Decision Making, Strategy, Empathy,
    # KPIs, CSPO. None are named tools/products.
    "tools", "frameworks", "utilizing", "strategic", "skills", "required",
    "decision", "making", "strategy", "empathy", "kpis", "cspo",
    "stakeholder", "stakeholders",
    # Added 2026-09-02 (CR-109 follow-up 2): Jason flagged "Judgment" as an
    # absurd card. These are soft skills / traits / competencies that the
    # evidence comparison evaluates — they are never binary tool-questions.
    "judgment", "judgement", "negotiation", "analytical", "critical",
    "creativity", "adaptability", "resilience", "leadership", "mentorship",
    "coaching", "facilitation", "presentation", "storytelling",
    "organization", "planning", "execution", "teamwork", "networking",
    "influence", "persuasion", "listening", "writing", "verbal",
    "interpersonal", "conceptual", "logical", "quantitative", "qualitative",
    "research", "analysis", "synthesis", "evaluation", "vision", "mission",
    "purpose", "values", "culture", "ethics", "integrity", "accountability",
    "responsibility", "initiative", "proactive", "awareness", "alignment",
    "engagement", "empowerment", "governance", "compliance", "scalability",
    "agility", "capability", "capacity", "curiosity", "rigor", "rigour",
    "collaboration", "communication", "communications",
})

# Abstract-noun suffixes — a word ending in one of these is almost certainly
# a common English abstract noun (Judgment, Prioritization, Leadership,
# Resilience, Empowerment, Scalability), not a named tool/product. Tool names
# are proper nouns that don't follow English derivational morphology —
# "Kafka", "Asana", "Greenhouse", "Excel", "SAML" don't end in -tion/-ment.
# This is a structural guard so the stopword list isn't the only defense.
_ABSTRACT_NOUN_SUFFIXES: frozenset[str] = frozenset({
    "tion", "sion", "ment", "ness", "ity", "ship", "ance", "ence",
    "ism", "ist", "dom", "acy", "ency", "logy", "graphy",
})

# Mid-sentence capitalized token run: NOT at the start of the string/sentence
# (a lookbehind requiring a lowercase letter/comma-space before it), one or
# more Title-Case words, optionally followed by a version number or a
# tool-suffix qualifier (API/SDK/Platform/.com). Deliberately conservative --
# gazetteer-plus-capitalization is the standard lightweight approach for this
# shape of problem (product-name NER research consistently reaches for this
# before full ML NER, which is unwarranted for a small, mostly-known universe
# like Jason's JD corpus).
_TOOL_TOKEN_RE = re.compile(
    r"(?<=[a-z,]\s)(?-i:[A-Z][a-zA-Z0-9]{2,}(?:\.[a-z]{2,3}|(?:\s+[A-Z][a-zA-Z0-9]{1,}){0,2})"
    r"(?:\s+(?:API|SDK|Platform|\d+(?:\.\d+)?))?)"
)


def looks_like_named_tool(text: str) -> list[str]:
    """Best-effort detection of proper-noun tool/product names in *text* --
    NOT a verdict on whether Jason has the tool, just "this line appears to
    name a specific product," which the caller then checks against
    load_skills_catalog_terms() (allow) and HARD_BLOCKED_TOOLS (deny).
    Returns the matched surface strings (may be empty)."""
    hits = []
    for m in _TOOL_TOKEN_RE.finditer(text):
        candidate = m.group(0).strip()
        first_word = candidate.split()[0].lower()
        if first_word in _TOOL_DETECTION_STOPWORDS:
            continue
        # Structural guard (CR-109 follow-up 2): a word ending in an
        # abstract-noun suffix is an English derivation (Judgment, Leadership,
        # Prioritization, Resilience), not a tool/product name. Tool names are
        # proper nouns that don't follow English morphology. This is the
        # structural complement to the stopword list — together they catch
        # soft skills and traits without enumerating every English word.
        if any(first_word.endswith(suffix) for suffix in _ABSTRACT_NOUN_SUFFIXES):
            continue
        # Implements FR-286 / BUG-001 (CR-109, 2026-09-02): reject JD label
        # shapes. A capitalized run immediately followed by ":" is a bullet
        # label, not a product ("Entrepreneurial Spirit:", "Systems
        # Thinking:", "Ruthless Prioritization:"); one immediately followed
        # by ")" is a parenthesized qualifier, not a product ("(Highly
        # Preferred):"). Both fired as live blocking Review Center questions
        # asking Jason whether he has "used Spirit" or "used Preferred".
        tail = text[m.end():m.end() + 1]
        if tail in {":", ")"}:
            continue
        hits.append(candidate)
    return hits
