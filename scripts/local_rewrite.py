"""Local-model sentence naturalization (CR-062 / Phase 1 of the local-LLM builder redesign).

OPT-IN (not default): activated only when DRAFT_MODE=local_rewrite. Default drafting
does not call this path. Kept deliberately per CR-062 — do not archive as dead code.

Deliberately the narrowest possible LLM surface: every call site hands this module ONE
already-selected, already-fact-checked piece of text and gets back either a naturalized
rewrite (same facts, same numbers, same entities, different wording) or the exact same
text unchanged. Claim selection, quota assignment, structure, and cover-letter proof-point
selection are untouched deterministic code elsewhere in the pipeline — this module never
sees a JD profile, a claim catalog, or a choice between candidates.

Grounding is enforced twice, mechanically, never by asking a model to judge its own output:
before the call (input is already-verified source text) and after the call (numeric-token-set
EQUALITY, not just no-fabrication; a proper-noun subset check; the existing bullet gates for
bullet-shaped text). Any failure falls back to the verbatim source, silently and safely,
logged to a per-batch audit file for an after-the-fact skim -- never a blocking human step.

See docs/reports/local-llm-builder-architecture-options.md for the full design rationale
(this implements the #1-ranked "Deterministic-Minimal-LLM" proposal).
"""
from __future__ import annotations

import datetime
import json
import os
import re
from typing import Callable, Optional, Tuple

from llm_stages import call_llm_stage
from verify_claims import extract_numeric_tokens

_REWRITE_SCHEMA = {
    "type": "object",
    "properties": {"rewritten": {"type": "string"}},
    "required": ["rewritten"],
}

# Same family as primary rewrite stage — phi escalation produced unusable wording.
_ESCALATION_MODEL = "llama3.1:8b-instruct-q5_K_M"

_PROPER_NOUN_RE = re.compile(r"\b[A-Z][a-zA-Z]+\b")
_PROPER_NOUN_STOPWORDS = {
    "I", "The", "A", "An", "My", "This", "That", "These", "Those", "And", "But",
    "For", "With", "At", "In", "On", "Of", "To", "As", "It", "Its",
}


def is_local_rewrite_mode() -> bool:
    """DRAFT_MODE=local_rewrite is additive -- it never touches the 'compose' default
    or the dormant 'legacy_llm' path."""
    return os.environ.get("DRAFT_MODE", "compose").strip().lower() == "local_rewrite"


def _numeric_tokens_equal(source_text: str, rewritten_text: str) -> bool:
    src = extract_numeric_tokens(source_text.replace(",", ""))
    out = extract_numeric_tokens(rewritten_text.replace(",", ""))
    return src == out


def _proper_nouns(text: str) -> set:
    return {w for w in _PROPER_NOUN_RE.findall(text) if w not in _PROPER_NOUN_STOPWORDS}


def _entity_subset_ok(source_text: str, rewritten_text: str) -> bool:
    """Every proper noun/tool/team token in the rewrite must already appear in the source --
    catches the class of leak (e.g. echoing a JD's own company/tool name) that a pure
    numeric-token check misses.

    Compares case-insensitively against the whole source text, not just the source's own
    capitalized words: a rewrite is free to re-capitalize a word that already appears in the
    source in lowercase (e.g. moving it to a sentence-initial position), which is common,
    safe rephrasing, not an invented entity.
    """
    source_lower = source_text.lower()
    for word in _proper_nouns(rewritten_text):
        if not re.search(r"(?<![\w-])" + re.escape(word.lower()) + r"(?![\w-])", source_lower):
            return False
    return True


def validate_bullet_rewrite(source_text: str, rewritten_text: str, max_words: int = 40) -> Tuple[bool, Optional[str]]:
    """Gate for resume bullets / the summary proof clause -- reuses the existing bullet
    gate stack verbatim (numeric superset, blocked tools, seniority inflation, tone, verb
    alignment, word cap, leading-verb) and adds the two stricter checks this design calls
    for: numeric-set EQUALITY (not just no-new-fabrication) and a proper-noun subset check."""
    from local_draft_stages import validate_bullet_for_local

    valid, err = validate_bullet_for_local(source_text, rewritten_text)
    if not valid:
        return False, err
    if not _numeric_tokens_equal(source_text, rewritten_text):
        return False, "Numeric token set changed (dropped or altered a number)"
    if not _entity_subset_ok(source_text, rewritten_text):
        return False, "Introduced a proper noun/tool/team not present in source"
    if len(rewritten_text.split()) > max_words:
        return False, f"Exceeds {max_words} words"
    return True, None


def validate_prose_rewrite(source_text: str, rewritten_text: str, max_words: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """Lighter gate for cover-letter paragraphs -- same numeric/entity/tool/tone/seniority
    checks as the bullet gate, but WITHOUT the leading-verb requirement (prose paragraphs
    don't start with a bare action verb the way resume bullets do)."""
    from local_draft_stages import BLOCKED_TOOLS, SENIORITY_INFLATION_PHRASES
    from tone_guard import tone_violations

    if not rewritten_text or not rewritten_text.strip():
        return False, "Empty rewrite"

    lower = rewritten_text.lower()
    for tool in BLOCKED_TOOLS:
        pat = r"(?<![\w-])" + re.escape(tool.lower()) + r"(?![\w-])"
        if re.search(pat, lower):
            return False, f"Blocked tool: {tool}"

    for phrase in SENIORITY_INFLATION_PHRASES:
        if phrase in lower:
            return False, f"Seniority inflation: {phrase}"

    tone_hits = tone_violations(rewritten_text)
    if tone_hits:
        return False, f"Blocked tone: {tone_hits[0]}"

    if not _numeric_tokens_equal(source_text, rewritten_text):
        return False, "Numeric token set changed (dropped or altered a number)"
    if not _entity_subset_ok(source_text, rewritten_text):
        return False, "Introduced a proper noun/tool/team not present in source"
    if max_words and len(rewritten_text.split()) > max_words:
        return False, f"Exceeds {max_words} words"
    return True, None


def _normalize_quotes(text: str) -> str:
    """Force straight quotes/apostrophes -- the rest of the pipeline's templates use
    plain ASCII punctuation, and small local models default to curly Unicode quotes,
    which would otherwise read as a typographic inconsistency within one document."""
    return (
        text.replace("‘", "'").replace("’", "'")
        .replace("“", '"').replace("”", '"')
    )


def _extract_rewrite_text(raw) -> str:
    if isinstance(raw, dict):
        return _normalize_quotes((raw.get("rewritten") or "").strip())
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return _normalize_quotes((data.get("rewritten") or "").strip())
    except (json.JSONDecodeError, TypeError):
        pass
    return _normalize_quotes(text.strip().strip('"'))


def _audit_log_path() -> str:
    from utils import PROJECT_ROOT

    batch_id = os.environ.get("REWRITE_BATCH_ID") or datetime.date.today().isoformat()
    log_dir = os.path.join(PROJECT_ROOT, "data", "submissions", "_batch_audit", batch_id)
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "rewrite_fallbacks.log")


def _log_rewrite_event(source_text: str, candidate: Optional[str], reason: str, doc_type: str, success: bool = False) -> None:
    entry = {
        "ts": datetime.datetime.now().isoformat(),
        "doc_type": doc_type,
        "success": success,
        "reason": reason,
        "source_preview": source_text[:120],
    }
    try:
        with open(_audit_log_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # audit logging must never break drafting


_SYSTEM_PROMPT = (
    "You rewrite one piece of text so it reads more naturally, optionally echoing the "
    "reader's own vocabulary where it genuinely fits. Rules, no exceptions: never add, "
    "remove, or change any number, tool name, team name, company name, or degree of scale. "
    "Keep the same core facts and the same verb family. Do not invent anything not already "
    "present in the source text. Return only the rewritten text, nothing else -- no preamble, "
    "no markdown, no explanation."
)


def local_rewrite_sentence(
    source_text: str,
    matched_jd_phrase: str = "",
    *,
    validator: Optional[Callable[[str, str], Tuple[bool, Optional[str]]]] = None,
    max_words: int = 40,
    doc_type: str = "bullet",
) -> str:
    """Rephrase source_text using JD vocabulary, never inventing content.

    Escalation ladder (fully automatic, no human step, per the hard automation constraint):
    1. Default local model ("rewrite" stage, qwen2.5:7b-instruct-q4_K_M) at temperature 0.3.
    2. Same model, retried once with the specific violated rule named in the prompt.
    3. llama3.1:8b-instruct-q5_K_M as an independent second try (phi removed — draft quality).
    4. Fall back to source_text verbatim -- guaranteed-safe, already gate-passing text.

    Every step is validated by `validator` (defaults to the bullet gate); every fallback is
    logged to the per-batch audit file for Jason to skim after a batch completes, never a
    blocking per-submission prompt.
    """
    if not source_text or not source_text.strip():
        return source_text

    validate = validator or (lambda s, r: validate_bullet_rewrite(s, r, max_words=max_words))

    jd_context = (
        f"\n\nThe reader's own phrasing, to echo ONLY if it fits naturally (never force it, "
        f"never treat it as a fact to add): {matched_jd_phrase}"
        if matched_jd_phrase
        else ""
    )
    user_prompt = f"Source text (rewrite this; keep every fact exactly as stated):\n{source_text}{jd_context}"

    attempts = [
        {"model": None, "system_suffix": ""},
        {
            "model": None,
            "system_suffix": "\n\nYour previous attempt violated a rule. Rewrite again, more conservatively -- change word choice only.",
        },
        {"model": _ESCALATION_MODEL, "system_suffix": ""},
    ]

    for i, attempt in enumerate(attempts):
        try:
            raw = call_llm_stage(
                "rewrite",
                _SYSTEM_PROMPT + attempt["system_suffix"],
                user_prompt,
                model=attempt["model"],
                temperature=0.3,
                response_schema=_REWRITE_SCHEMA,
            )
        except Exception as exc:  # network/model errors must never break drafting
            _log_rewrite_event(source_text, None, f"call_error: {exc}", doc_type)
            continue

        candidate = _extract_rewrite_text(raw)
        if not candidate:
            _log_rewrite_event(source_text, None, "empty_response", doc_type)
            continue

        ok, err = validate(source_text, candidate)
        if ok:
            if i > 0:
                _log_rewrite_event(source_text, candidate, f"escalated_attempt_{i}", doc_type, success=True)
            return candidate
        _log_rewrite_event(source_text, candidate, err or "validation_failed", doc_type)

    _log_rewrite_event(source_text, None, "fallback_to_verbatim", doc_type)
    return source_text


def local_rewrite_bullet(source_text: str, matched_jd_phrase: str = "", max_words: int = 40) -> str:
    """Entry point for resume bullets and the summary proof clause."""
    return local_rewrite_sentence(
        source_text,
        matched_jd_phrase,
        validator=lambda s, r: validate_bullet_rewrite(s, r, max_words=max_words),
        max_words=max_words,
        doc_type="bullet",
    )


def local_rewrite_prose(source_text: str, matched_jd_phrase: str = "", max_words: int = 150) -> str:
    """Entry point for cover-letter paragraphs (no leading-verb requirement)."""
    return local_rewrite_sentence(
        source_text,
        matched_jd_phrase,
        validator=lambda s, r: validate_prose_rewrite(s, r, max_words=max_words),
        max_words=max_words,
        doc_type="cover_letter_paragraph",
    )
