"""Score loop_eval.py against the before-fix gold quotes.

Prints recall on known-bad quotes and the false-positive rate on other
sentences in the same files. Does not modify those files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from loop_eval import _units, evaluate_pair  # noqa: E402

_ROOT = _SCRIPT_DIR.parent
_EVIDENCE = _ROOT / "data" / "review_evidence" / "2026-09-23-before-fix"
_GOLD = _ROOT / "docs" / "loop" / "evidence" / "f1" / "gold.json"


def _slug(name: str) -> str:
    """Return the company slug from a bak filename."""
    stem = name.removeprefix("bak_").removesuffix(".md")
    return stem.removesuffix("_Resume").removesuffix("_CoverLetter")


def _load_pair(name: str) -> tuple[str, str, dict]:
    """Load resume, letter, and provenance for one bak file's slug."""
    slug = _slug(name)
    resume = (_EVIDENCE / f"bak_{slug}_Resume.md").read_text(encoding="utf-8")
    letter = (_EVIDENCE / f"bak_{slug}_CoverLetter.md").read_text(encoding="utf-8")
    provenance = json.loads((_EVIDENCE / f"bak_{slug}_prov.json").read_text(encoding="utf-8"))
    return resume, letter, provenance


def main() -> int:
    """Print recall and false-positive rate. Returns 0 when both bars are met."""
    gold = json.loads(_GOLD.read_text(encoding="utf-8"))
    cache: dict[str, list[dict[str, str]]] = {}
    missed: list[str] = []
    absent: list[str] = []
    hit = 0
    present = 0
    for item in gold:
        text = (_EVIDENCE / item["file"]).read_text(encoding="utf-8")
        quote = item["quote"]
        if quote.lower() not in text.lower():
            absent.append(f"{item['file']}: {quote}")
            continue
        present += 1
        slug = _slug(item["file"])
        if slug not in cache:
            resume, letter, provenance = _load_pair(item["file"])
            cache[slug] = evaluate_pair(resume, letter, provenance)
        excerpts = " ".join(row.get("text") or row["excerpt"] for row in cache[slug]).lower()
        if quote.lower() in excerpts:
            hit += 1
        else:
            missed.append(f"{item['file']}: {quote}")

    good = 0
    false_pos = 0
    seen: set[str] = set()
    for item in gold:
        slug = _slug(item["file"])
        if slug in seen:
            continue
        seen.add(slug)
        resume, letter, _provenance = _load_pair(item["file"])
        quotes = [row["quote"].lower() for row in gold if _slug(row["file"]) == slug]
        flagged = {(row.get("text") or row["excerpt"]).lower() for row in cache.get(slug, [])}
        for _doc, unit in _units(resume, letter):
            lower = unit.lower()
            if any(quote in lower for quote in quotes):
                continue
            good += 1
            if any(lower[:180] in excerpt or excerpt[:180] in lower for excerpt in flagged):
                false_pos += 1

    recall = hit / present if present else 0.0
    fp_rate = false_pos / good if good else 0.0
    print(f"present {present} hit {hit} recall {recall:.3f}")
    print(f"known_good {good} false_pos {false_pos} fp_rate {fp_rate:.3f}")
    print(f"absent {len(absent)}")
    for line in absent:
        print(f"ABSENT {line}")
    for line in missed:
        print(f"MISS {line}")
    return 0 if recall >= 0.9 and fp_rate < 0.1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
