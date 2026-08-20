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
    r"nice\s+to\s+have|must\s+have|bonus(?:\s+points)?"
    r")\s*:?$",
    re.I,
)
_BOILERPLATE_RE = re.compile(
    r"e-verify|starting pay|equal opportunity employer|"
    r"window of at least \d+ days|total direct compensation|"
    r"we are an equal|diversity and inclusion statement|"
    r"to all applicants without regard",
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
