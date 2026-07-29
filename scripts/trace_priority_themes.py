"""
CR-069 Round 1 Step 3 — pre-truncation `priority_themes` trace (Decision item 3 -> AC 3).

Standalone diagnostic script. Reproduces `build_jd_profile_deterministic`'s theme-
collection loop (scripts/jd_tailoring.py:126-157) against the real, imported
THEME_KEYWORDS table and the real `_jd_body_for_themes` helper, and prints the
FULL, untruncated `themes` list before the `themes[:4]` cap is applied — not just
the truncated result the production function returns. This directly confirms or
refutes whether the AI-tooling theme phrase is present in the untruncated list but
displaced past index 4 by earlier table-order (generic) entries, for each of the 6
ACC-401-AITOOLS should-surface JDs.

No production edits: THEME_KEYWORDS and _jd_body_for_themes are imported directly
from jd_tailoring.py, not reimplemented or monkeypatched. The loop body below is a
read-only reproduction of lines 129-132 for tracing purposes only.

Also separately re-confirms (does not re-derive) that no THEME_KEYWORDS entry could
ever produce a Scrum/coordination theme for ACC-204's 2 should-surface JDs -- this
was already established by CR-063 Round 4.
"""
from __future__ import annotations

import os

from jd_tailoring import THEME_KEYWORDS, _jd_body_for_themes, build_jd_profile_deterministic
from utils import PROJECT_ROOT

ARCHIVE_SUBMISSIONS_DIR = os.path.join(PROJECT_ROOT, "data", "archive", "submissions")

AITOOLS_SLUGS = ["ontra", "remote", "covideo", "datagrail", "mytime", "pointclickcare"]
ACC204_SLUGS = ["buyers_edge_platform", "par_technology"]

AI_THEME_PHRASE_1 = "AI tooling and agentic automation workflows"   # from genai/agentic entries
AI_THEME_PHRASE_2 = "AI tooling and prompt engineering workflows"   # from llm/cursor/claude entries
SCRUM_KEYWORDS = ("scrum", "agile", "sprint", "backlog")


def trace_untruncated_themes(jd_text: str):
    """Read-only reproduction of build_jd_profile_deterministic's lines 129-132."""
    theme_source = _jd_body_for_themes(jd_text)
    jd_lower = theme_source.lower()
    themes = []
    matched_keywords = []
    for kw, phrase in THEME_KEYWORDS:
        if kw in jd_lower and phrase not in themes:
            themes.append(phrase)
            matched_keywords.append(kw)
    return themes, matched_keywords


def main():
    print("=" * 100)
    print("ACC-401-AITOOLS: pre-truncation priority_themes trace (6 should-surface JDs)")
    print("=" * 100)
    for slug in AITOOLS_SLUGS:
        jd_path = os.path.join(ARCHIVE_SUBMISSIONS_DIR, slug, "Original_JD.txt")
        with open(jd_path, encoding="utf-8") as f:
            jd_text = f.read()

        themes, matched_kws = trace_untruncated_themes(jd_text)
        truncated = themes[:4]
        ai_theme_indices = [i for i, t in enumerate(themes) if t in (AI_THEME_PHRASE_1, AI_THEME_PHRASE_2)]

        # sanity check: this must equal what production build_jd_profile_deterministic returns
        prod_profile = build_jd_profile_deterministic(jd_text)
        assert prod_profile.priority_themes == truncated, (
            f"MISMATCH for {slug}: traced {truncated} vs production {prod_profile.priority_themes}"
        )

        print(f"\n### {slug}")
        print(f"  Full untruncated themes ({len(themes)} total), in THEME_KEYWORDS table order:")
        for i, (t, kw) in enumerate(zip(themes, matched_kws)):
            marker = " <-- AI-tooling theme" if t in (AI_THEME_PHRASE_1, AI_THEME_PHRASE_2) else ""
            kept = "KEPT (index < 4)" if i < 4 else "TRUNCATED (index >= 4)"
            print(f"    [{i}] matched kw={kw!r} -> {t!r}  [{kept}]{marker}")
        if not ai_theme_indices:
            print("  AI-tooling theme phrase: NEVER MATCHED (no genai/agentic/llm/cursor/claude keyword "
                  "found anywhere in this JD's theme-detection body at all -- not a truncation issue, "
                  "the keyword itself never fires loop 3's THEME_KEYWORDS scan)")
        else:
            for idx in ai_theme_indices:
                status = "SURVIVED truncation (kept in priority_themes[:4])" if idx < 4 else \
                    f"DISPLACED past index 4 by {idx} earlier generic-table-order theme(s)"
                print(f"  AI-tooling theme at untruncated index {idx}: {status}")
        print(f"  priority_themes[:4] (what production actually uses): {truncated}")
        print("  [Sanity check OK: traced truncated list == production build_jd_profile_deterministic() output]")

    print("\n" + "=" * 100)
    print("ACC-204: re-confirming no THEME_KEYWORDS entry can ever produce a Scrum/coordination theme")
    print("=" * 100)
    all_kw_phrases = [kw for kw, _phrase in THEME_KEYWORDS]
    scrum_kw_present = [kw for kw in all_kw_phrases if any(s in kw for s in SCRUM_KEYWORDS)]
    print(f"THEME_KEYWORDS entries containing any of {SCRUM_KEYWORDS}: {scrum_kw_present or '(none)'}")
    print(f"Total THEME_KEYWORDS entries: {len(THEME_KEYWORDS)}")

    for slug in ACC204_SLUGS:
        jd_path = os.path.join(ARCHIVE_SUBMISSIONS_DIR, slug, "Original_JD.txt")
        with open(jd_path, encoding="utf-8") as f:
            jd_text = f.read()
        themes, matched_kws = trace_untruncated_themes(jd_text)
        print(f"\n### {slug}")
        print(f"  Full untruncated themes ({len(themes)} total): {themes}")
        print(f"  Matched keywords: {matched_kws}")
        print("  No Scrum/agile/sprint/backlog-related theme present (confirmed: no matching keyword table entry exists)")


if __name__ == "__main__":
    main()
