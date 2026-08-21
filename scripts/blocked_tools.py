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
    # Docker is verified (WE ACC-172 / skills_catalog hands-on environments).
    "kubernetes", "k8s", "terraform", "helm",
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


def hard_blocked_tool_pattern() -> re.Pattern[str]:
    """Case-insensitive word-boundary alternation over HARD_BLOCKED_TOOLS.

    ``workday`` keeps a negative lookahead so capacity phrasing like
    ``workday-hours`` / ``workday hours`` is not treated as the Workday HCM
    product (live false positive on neogen/precisepk/procede, 2026-08-11).
    """
    parts: list[str] = []
    for tool in sorted(HARD_BLOCKED_TOOLS, key=len, reverse=True):
        esc = re.escape(tool)
        if tool == "workday":
            parts.append(rf"{esc}(?![\s-]*hours?\b)")
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
            catalog = _json.loads(open(path, encoding="utf-8").read())
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
        hits.append(candidate)
    return hits
