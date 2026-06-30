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
from dataclasses import dataclass, field
from typing import List, Literal, Optional


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
        pattern=r"I am confident that",
        message="Forbidden phrase: 'I am confident that'",
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
        pattern="[REDACTED_PHONE]",
        message="Placeholder '[REDACTED_PHONE]' left in document",
        suggestion="Replace with actual contact information or remove the line.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LR-008",
        severity="HARD_BLOCK",
        check_type="keyword",
        pattern="[REDACTED_EMAIL]",
        message="Placeholder '[REDACTED_EMAIL]' left in document",
        suggestion="Replace with actual email address or remove the line.",
        doc_types=["cover_letter", "resume"],
    ),
    LintRule(
        rule_id="LR-009",
        severity="HARD_BLOCK",
        check_type="regex",
        pattern=r"\b(leverage|passionate|dynamic|innovative|seamless|transformative|synergy|tapestry|revolutionize)\b",
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
        pattern=r"\$800K Canadian|\$800,000 Canadian",
        message="Disabled claim ACC-114 ($800K Canadian) detected",
        suggestion="Remove this claim. It is quarantined pending verification.",
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
    "engineering", "dba", "database administration", "devops", "customer experience",
    "cx", "customer support", "support", "sales", "account management",
    "legal", "infosec", "information security", "product marketing",
    "executive", "presidential", "executive leadership",
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
            flags = re.IGNORECASE if rule.rule_id not in ("LR-010",) else re.MULTILINE
            for i, line in enumerate(lines, start=1):
                if re.search(rule.pattern, line, re.IGNORECASE | re.MULTILINE):
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

    passed = len(blocks) == 0
    return LintResult(passed=passed, blocks=blocks, warns=warns, infos=infos, document_type=doc_type)


def lint_folder(folder: str) -> List[dict]:
    """Lint all .md files in a submission folder. Returns list of summary dicts."""
    results = []
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


def _run_cli(paths: List[str]) -> int:
    """CLI entry point. Returns exit code."""
    all_results: List[dict] = []

    for path in paths:
        path = os.path.normpath(path)
        if os.path.isdir(path):
            # Check if it's a submissions root (contains sub-dirs) or a single submission
            subdirs = [d for d in os.listdir(path)
                       if os.path.isdir(os.path.join(path, d)) and not d.startswith(".")]
            md_files = [f for f in os.listdir(path) if f.endswith(".md")]
            if md_files:
                all_results.extend(lint_folder(path))
            elif subdirs:
                for sub in sorted(subdirs):
                    all_results.extend(lint_folder(os.path.join(path, sub)))
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
