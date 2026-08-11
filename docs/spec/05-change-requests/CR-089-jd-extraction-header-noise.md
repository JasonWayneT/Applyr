# CR-089: JD Section-Header Noise (Company-Prefix + Missing Triggers)

## Metadata
- **Status**: Implemented (2026-08-10)
- **Date**: 2026-08-10
- **Source**: Follow-up to CR-085/086 measurement — Jason asked "why not let the model do
  extraction instead," resolved by measuring root cause first (see Decision)
- **Related**: CR-086 (same mechanism, narrower coverage), CR-090 (soft-gap classification,
  addressed together as the two causes of `packet_status: incomplete` regressions)

## Problem
CR-086 fixed a narrow class of JD-extraction noise (physical/office/pay-disclaimer
boilerplate). Re-measuring `_extract_sections()` against all 54 real `data/submissions/`
JDs found two distinct, still-live root causes, not covered by CR-086:

1. **Company-name-prefixed headers defeat the anchored regex.** Every header pattern in
   `_SECTION_HEADERS`/`_IGNORE_SECTION_HEADERS` is anchored at line-start (`^...`). Real JDs
   commonly prefix section headers with the company name (confirmed directly:
   `data/submissions/leaflink/Original_JD.txt` has "**LeafLink** Perks & Benefits", not
   "Perks & Benefits"). The prefix silently defeats the match, `current_bucket` never
   resets, and every line under it (mostly benefits copy) gets miscategorized as a
   requirement.
2. **Recognized-but-not-redirecting headers.** "What We Offer" was already in the orphan
   *item* filter (so the header line itself doesn't become a fake requirement) but was
   never a `_SECTION_HEADERS` trigger, so it never redirected `current_bucket` — every line
   underneath kept flowing into whatever bucket was active.

Measured before fix: 10 of 54 companies (18.5%) had ≥1 contaminated required/preferred/
responsibilities item; 23 of 1046 items (2.2%) were noise, dominated by benefits copy
(PTO/401k/medical-dental-vision), with a smaller share of interview-process/application-
instruction language.

A second measurement pass (against the CR-063 eval-set corpus, cross-referenced with the
packet-level eval harness from CR-085) found the same two root causes recurring for
`responsibilities`/`culture` headers specifically: "What the job involves" (a
responsibilities-section header, not in the trigger list) was the single largest blocker
across the remaining incomplete packets — present in 6 of 10 still-incomplete real
companies, each time dragging the company-intro paragraph, "You'll report to:", and
downstream interview-process steps into the wrong bucket. "What's in this for you?" and
bare "Interview with recruiter" (no article before the name) had the same gap.

## Decision
Extend the same deterministic mechanism CR-086 already proved works — not a rewrite, not
an LLM. Deliberately rejected LLM-based JD extraction: Stage 0 is LLM-free by design
(CR-074's token-conscious architecture), CR-063 already measured no accuracy gain from
`jd_profile_mode="llm"` on a related extraction task, and the root cause here is a
formatting-pattern gap, not a semantic-judgment problem — confirmed by checking the actual
JD text directly before deciding, not assumed.

1. `_SECTION_HEADERS`'s culture pattern and `_IGNORE_SECTION_HEADERS` both gain an optional,
   bounded company-name-prefix tolerance (`(?:[A-Z][\w'&.-]{1,20}\s+){0,3}`) before the
   trigger phrase. Bounded to 0–3 short capitalized tokens so it can't drift into matching
   mid-paragraph.
2. `_SECTION_HEADERS`'s responsibilities pattern gains `what the job involves`; culture
   gains `what we offer` / `what we'll offer` / `our perks` / `what you'll get` / `what's
   in this for you` as real triggers (not just orphan-item filters).
3. `_BOILERPLATE_ITEM_RE` gains a content-level safety net (same belt-and-suspenders
   pattern as CR-086's physical/ADA items): benefits-copy phrases (medical/dental/vision,
   401k, PTO, stock options, parental leave, "perks & benefits") and interview-process/
   application-instruction phrases (broadened `interview with X` to any word, not just
   "our/the/a"; start date; "product deep dive"; "offer + prior employment verification").
   No header regex will ever cover every real-world phrasing — this catches it item-by-item
   regardless of whether the header redirect fired.

## Acceptance Criteria
| ID | Criterion |
|----|-----------|
| AC1 | Re-running the 54-company measurement after the fix shows contaminated companies drop from 10 to ≤2 (measured: 10→1) |
| AC2 | Full test suite (`run_all_tests.py`) passes unmodified |
| AC3 | Packet-level eval (`eval_packet_selection.py`) shows no should-surface recall regression from this change alone |
| AC4 | Real submissions previously blocked purely by header-redirect noise (not genuine soft gaps) flip from `incomplete` to `ready` on a fresh Stage 0 rebuild |

## Out of Scope
- LLM-based or embeddings-based JD extraction — explicitly rejected, see Decision.
- Genuine soft gaps (real skill/domain gaps with no claim evidence) — those are the system
  working as designed, not noise; left untouched.
- The "administratively satisfied" category (education, years-of-experience) — see CR-090.
