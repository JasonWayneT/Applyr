#!/usr/bin/env python3
"""Retrieval-augmented few-shot examples for Stage 0 LLM judgment calls
(2026-08-19 self-healing plan, item 3).

Why retrieval instead of a static block of examples: research on few-shot
prompting finds 3-5 examples is the real sweet spot -- performance stops
improving (and can get worse) past 5-10, because extra examples dilute the
pattern instead of reinforcing it. And Ollama's own "lost in the middle"
behavior means content buried deep in a long prompt is recalled less
reliably than content near the start or end. So the example BANK can grow
without limit (every confirmed real judgment call earns a slot), but each
call only ever sees the top few most relevant to the current input --
dynamic retrieval, not a growing static dump. This is a validated pattern,
not a guess: retrieval-based dynamic few-shot has been shown to outperform
static few-shot by several points of F1 in real studies, sometimes beating
fine-tuning outright at low example counts.

Deliberately NOT embedding-based (nomic-embed-text) yet, per the agreed
"keyword match first" plan -- the bank is currently tiny (a handful of
entries), so a simple token-overlap score is sufficient and correctness is
easier to verify than a similarity threshold would be. Revisit once the
bank grows past ~10-15 entries per category and overlap scoring starts
returning noisy ties; nomic-embed-text is already installed locally
(274MB, negligible VRAM next to qwen's ~4.7GB) and needs zero new
infrastructure to add later.

Source of truth: data/fit_rubric_golden_set.json's few_shot_eligible
entries. Not a separate parallel file -- the golden set already carries
the real jd_line, the confirmed-correct answer, and category/tags; a
second copy of the same facts would just be another thing to keep in
sync, exactly the kind of drift this whole self-healing effort exists to
avoid.
"""
from __future__ import annotations

import json
import os
import re

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)
_GOLDEN_SET = os.path.join(_ROOT, "data", "fit_rubric_golden_set.json")

_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "in", "for", "to", "with", "on",
    "is", "are", "this", "that", "across", "own", "own's",
})
_TOKEN_RE = re.compile(r"[a-z][a-z'-]*")


def _tokenize(text: str) -> set[str]:
    return {
        t for t in _TOKEN_RE.findall((text or "").lower())
        if t not in _STOPWORDS and len(t) > 2
    }


def load_few_shot_examples(category: str | None = None) -> list[dict]:
    """All active, few_shot_eligible golden-set entries, optionally filtered
    to one category. Returns [] (never raises) if the golden set is
    missing -- private local data that may not exist in every environment,
    same skip-not-fail posture as the extraction corpus regression test."""
    if not os.path.isfile(_GOLDEN_SET):
        return []
    with open(_GOLDEN_SET, encoding="utf-8") as f:
        golden = json.load(f)
    entries = [
        e for e in golden.get("entries", [])
        if e.get("status") == "active" and e.get("few_shot_eligible")
    ]
    if category:
        entries = [e for e in entries if e["category"] == category]
    return entries


def retrieve_examples(query_text: str, category: str | None, k: int = 3) -> list[dict]:
    """Top-k few_shot_eligible entries for *category*, ranked by token
    overlap with *query_text* (Jaccard similarity over lowercased,
    stopword-filtered tokens). Ties broken by added_date descending (most
    recently confirmed example first) so a fresh correction is at least as
    likely to surface as an old one of equal relevance.

    category=None retrieves across every category (CR-093's evidence-scale
    classifier doesn't know a line's category in advance -- that's what it's
    judging -- so it ranks the whole bank by relevance instead of filtering
    first).

    With today's small bank this will often just return everything
    available for the category (there usually aren't more than k
    candidates yet) -- the ranking becomes load-bearing once the bank
    grows past k per category, which is the point it's built in for now
    rather than retrofitted later."""
    candidates = load_few_shot_examples(category)
    if not candidates:
        return []

    query_tokens = _tokenize(query_text)
    scored: list[tuple[float, str, dict]] = []
    for entry in candidates:
        tags = set(t.lower() for t in entry.get("few_shot_tags", []))
        entry_tokens = _tokenize(entry.get("jd_line", "")) | tags
        if not entry_tokens:
            continue
        overlap = query_tokens & entry_tokens
        union = query_tokens | entry_tokens
        jaccard = len(overlap) / len(union) if union else 0.0
        scored.append((jaccard, entry.get("added_date", ""), entry))

    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [entry for _, _, entry in scored[:k]]


def format_examples_for_prompt(examples: list[dict]) -> str:
    """Render retrieved examples as a compact few-shot block, formatted for
    the internal_term judgment specifically (the one live call this wires
    into today -- see build_stage0_fit_gate.py's _SECTION_SPLIT_USER_TEMPLATE).
    These examples teach product-name spotting, not requirement-line copying.
    Returns "" when there's nothing to show, so callers can splice this in
    unconditionally without an extra empty-check."""
    if not examples:
        return ""
    lines = ["Examples of correctly identifying an employer's own internal terms:"]
    for entry in examples:
        ex = entry.get("few_shot_prompt_example") or {}
        jd_excerpt = ex.get("jd_excerpt", entry.get("jd_line", ""))
        correct = ex.get("correct_internal_terms", [])
        lines.append(f'- JD: "{jd_excerpt}"')
        lines.append(f"  internal_terms: {json.dumps(correct)}")
    return "\n".join(lines)


def format_evidence_examples_for_prompt(examples: list[dict]) -> str:
    """Render retrieved examples as a compact few-shot block for the
    evidence-scale classifier (CR-093, scripts/evidence_scale.py) -- the
    gate/evidence-level judgment call, not the internal-terms call
    format_examples_for_prompt() above formats for. Uses the golden set's
    own jd_line/expected_gate/expected_gap_source/expected_evidence_level/
    reasoning fields directly; unlike internal_term entries these categories
    don't need a separate few_shot_prompt_example shape. Returns "" when
    there's nothing to show."""
    if not examples:
        return ""
    lines = ["Examples of correctly judging real requirement lines (confirmed cases):"]
    for entry in examples:
        gate = entry.get("expected_gate", "NONE")
        source = entry.get("expected_gap_source")
        level = entry.get("expected_evidence_level")
        reasoning = entry.get("reasoning", "")
        lines.append(f'- JD line: "{entry.get("jd_line", "")}"')
        gate_desc = f"{gate}" + (f" ({source})" if gate == "HARD" and source else "")
        lines.append(f"  gate={gate_desc}, evidence_level={level} -- {reasoning}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "Own product strategy across the Foo and Bar platforms."
    hits = retrieve_examples(q, "internal_term", k=3)
    print(f"query: {q!r}")
    print(f"retrieved {len(hits)} example(s):")
    for h in hits:
        print(" -", h["id"], h.get("jd_line", "")[:80])
    print()
    print(format_examples_for_prompt(hits))
