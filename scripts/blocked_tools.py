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
