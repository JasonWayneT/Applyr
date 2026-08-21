"""Stage 0 JD extraction helpers: clean, harvest candidate lines, resolve id labels.

Qwen must not copy JD wording. Python enumerates candidate lines and assigns
stable integer ids. The model only returns those ids plus bucket labels.
Resolved text is always a lookup into the harvested list.

See CR-093 extraction-quality notes (Stripe/Judge Group paragraph-as-item,
HTML-entity JDs) and the 2026-08-20 id-only design.
"""
from __future__ import annotations

import re

_MIN_CHARS = 20
_SPLIT_CHARS = 400
_MIN_CANDIDATES_BEFORE_SENTENCE_FALLBACK = 3
_MAX_CANDIDATES = 100

_BULLET_RE = re.compile(r"^[\s]*[-–—*•◦▪▸→·]+[\s]*")
_NUMBERED_RE = re.compile(r"^[\s]*(?:\(?\d{1,3}\)?[.)]|[a-z][.)])[\s]+", re.I)
_HEADER_LINE_RE = re.compile(
    r"^(?:"
    r"requirements?|qualifications?|preferred(?:\s+qualifications?)?|"
    r"what\s+you.?ll\s+(?:do|need|bring)|what\s+we.?re\s+looking\s+for|"
    r"responsibilities|about\s+(?:us|you|the\s+role)|benefits|"
    r"equal\s+opportunity|who\s+we\s+are|who\s+you\s+are|"
    r"nice\s+to\s+have|must\s+have|bonus(?:\s+points)?|"
    # Schellman diagnosis (2026-08-21 Stage 1-3 audit): confirmed real cause
    # of that folder's 8,111-token packet overflow -- this bare section label
    # carries no requirement verb but is long enough (32 chars) to clear
    # _MIN_CHARS, so it was harvested and evidence-mapped as a real required
    # item, one of 27 evidence_map entries feeding an 8,000-token cap.
    r"education,?\s*work\s+experience\s+and\s+certifications"
    r")\s*:?$",
    re.I,
)
_BOILERPLATE_RE = re.compile(
    r"e-verify|starting pay|equal opportunity employer|"
    r"window of at least \d+ days|total direct compensation|"
    r"we are an equal|diversity and inclusion statement|"
    r"to all applicants without regard|"
    # Fix 3 (2026-08-21 Stage 1-3 audit): this is the harvester's own,
    # much thinner filter -- build_stage0_fit_gate.py's larger
    # _BOILERPLATE_ITEM_RE never runs on this (now-default, 2026-08-17+)
    # extraction path, so a line the LLM section-splitter is separately
    # told (via its own prompt) to skip can still get harvested as a
    # candidate and, if it carries a required/preferred header hint,
    # force-included by resolve_labeled_buckets()'s unresolved-hint
    # fallback regardless of what the model decided. Confirmed real on
    # Point C ("$90,000—$100,000 USD" + a compensation-commensurate
    # disclaimer), Tm2 Group ("Compensation Range: $185.9K - $204.1K" +
    # benefits para + background-check consent line), and Alfa Laval
    # (recruiter name+email lines, an application deadline, a GDPR
    # application-method disclaimer, and a sign-off line) all landing in
    # `required`.
    # Bare currency range, with or without a leading label, K/M suffixes
    # allowed ("$90,000—$100,000 USD", "Compensation Range: $185.9K - $204.1K").
    r"compensation\s+range\s*:|"
    r"\$[\d,]+(?:\.\d+)?\s*[kKmM]?\s*[-–—]\s*\$?[\d,]+(?:\.\d+)?\s*[kKmM]?|"
    # A line built around an email address is a recruiter/contact line, never
    # a hire criterion -- a real requirement line does not carry an email.
    r"[\w.+-]+@[\w-]+\.\w{2,}|"
    r"for more information,?\s+please\s+contact|"
    # Application-deadline phrasing.
    r"no\s+later\s+than|apply\s+by\s+\w|application\s+deadline|"
    # GDPR / application-method / sign-off boilerplate.
    r"general\s+data\s+protection\s+regulation|"
    r"do\s+not\s+accept\s+applications\s+via\s+email|"
    r"continuous\s+review\s+of\s+received\s+applications|"
    r"we\s+look\s+forward\s+to\s+hearing\s+from\s+you|"
    # Background-check consent lines.
    r"background\s+investigation|consent\s+to\s+.{0,30}background\s+check|"
    # Generic compensation/benefits disclaimer paragraphs not already caught
    # by build_stage0_fit_gate.py's own filter.
    r"commensurate\s+with\s+the\s+candidate.s\s+experience|"
    r"eligible\s+for\s+additional\s+compensation,?\s+including\s+bonuses|"
    r"sales\s+commission\s+plan|"
    r"offer\s+a\s+competitive\s+salary\s+and\s+comprehensive\s+benefits|"
    # Schellman diagnosis: "flexible and balanced environment... opportunity
    # to work remotely" is company culture/perk framing, not a candidate
    # requirement -- the other confirmed real contributor to that folder's
    # 27-item evidence_map / 8,111-token overflow.
    r"flexible\s+and\s+balanced\s+environment|"
    r"opportunity\s+to\s+work\s+remotely",
    re.I,
)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def clean_jd_text(jd_text: str) -> str:
    """Unescape HTML entities and strip tags. Safe on already-plain text."""
    from dom_cleanup import clean_html_to_text

    return clean_html_to_text(jd_text or "")


def _strip_marker(line: str) -> str:
    line = _BULLET_RE.sub("", line)
    line = _NUMBERED_RE.sub("", line)
    return line.strip()


def _is_skippable(text: str) -> bool:
    if len(text) < _MIN_CHARS:
        return True
    if text.lower().startswith("url:"):
        return True
    if _HEADER_LINE_RE.match(text):
        return True
    if _BOILERPLATE_RE.search(text):
        return True
    return False


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _classify_header(line: str) -> tuple[str | None, bool]:
    try:
        from build_stage0_fit_gate import classify_jd_header
    except ImportError:
        return None, False
    return classify_jd_header(line)


def _add_candidate(out: list[dict], text: str, section: str | None) -> None:
    text = " ".join(text.split())
    if _is_skippable(text):
        return
    hint = section if section in ("required", "preferred") else None
    existing = {c["text"] for c in out}
    if len(text) > _SPLIT_CHARS:
        parts = [sent for sent in _split_sentences(text) if not _is_skippable(sent)]
        if len(parts) > 1:
            for sent in parts:
                if sent not in existing:
                    out.append({"text": sent, "section": hint})
                    existing.add(sent)
            return
    if text not in existing:
        out.append({"text": text, "section": hint})


def harvest_extract_candidates(jd_text: str) -> list[dict]:
    """Return [{"id": 1, "text": "...", "section": ...}, ...] from cleaned JD lines.

    Long paragraphs are sentence-split. If almost nothing looks like a list,
    fall back to sentence-splitting the whole cleaned JD.

    `section` is required/preferred when a mature JD header is sticky, else None.
    """
    cleaned = clean_jd_text(jd_text)
    lines: list[dict] = []
    current: str | None = None
    for raw_line in cleaned.splitlines():
        text = _strip_marker(raw_line)
        if not text:
            continue
        bucket, pure = _classify_header(text)
        if bucket == "ignore":
            current = None
            continue
        if bucket in {"required", "preferred", "responsibilities", "culture"} and pure:
            current = bucket
            continue
        hint = current if current in ("required", "preferred") else None
        _add_candidate(lines, text, hint)

    if len(lines) < _MIN_CANDIDATES_BEFORE_SENTENCE_FALLBACK:
        fallback: list[dict] = []
        for sent in _split_sentences(cleaned):
            _add_candidate(fallback, _strip_marker(sent), None)
        if len(fallback) > len(lines):
            lines = fallback

    lines = lines[:_MAX_CANDIDATES]
    return [
        {"id": i, "text": row["text"], "section": row.get("section")}
        for i, row in enumerate(lines, start=1)
    ]


def format_candidates_for_prompt(candidates: list[dict]) -> str:
    rows = []
    for c in candidates:
        hint = c.get("section")
        if hint in ("required", "preferred"):
            rows.append(f"[{c['id']}] ({hint}) {c['text']}")
        else:
            rows.append(f"[{c['id']}] {c['text']}")
    return "\n".join(rows)


def _coerce_id(raw) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    if isinstance(raw, float) and raw.is_integer():
        return int(raw) if raw > 0 else None
    if isinstance(raw, str):
        m = re.match(r"^\s*(\d{1,4})\s*$", raw)
        if m:
            return int(m.group(1))
    return None


def resolve_labeled_buckets(candidates: list[dict], data: dict) -> dict[str, list[str]]:
    """Map model id lists onto harvested text. Unknown ids and copied strings drop.

    If the same id is listed in more than one bucket, required wins, then
    preferred, then responsibilities, then culture.
    """
    by_id = {int(c["id"]): c["text"] for c in candidates}
    seen: set[int] = set()
    out: dict[str, list[str]] = {
        "required": [],
        "preferred": [],
        "responsibilities": [],
        "culture": [],
    }
    for bucket in out:
        raw_items = data.get(bucket)
        if not isinstance(raw_items, list):
            continue
        for raw in raw_items:
            cid = _coerce_id(raw)
            if cid is None or cid in seen:
                continue
            text = by_id.get(cid)
            if not text:
                continue
            out[bucket].append(text)
            seen.add(cid)
    for cand in candidates:
        try:
            cid = int(cand["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if cid in seen:
            continue
        hint = cand.get("section")
        if hint not in ("required", "preferred"):
            continue
        text = cand.get("text")
        if not text:
            continue
        out[hint].append(text)
        seen.add(cid)
    return out
