---
status: defect_stub
created: 2026-09-13
from: Cursor (Grok 4.6)
candidate: cr112-integrated-validation-candidate
related: CR-112, SEC-006, SESSION-HANDOFF-2026-09-13-cr112-jd3-newsela.md
implement_this_pass: no
do_not: fix in this closeout, copy production SQLite, use synthetic identity on a real practice JD, commit PII
---

# CR-112 unbracketed placeholder header stack

Bounded defect. **Not implemented.** Do not bundle into Story 8.2
(`SEC-006`), ranking, or score provenance. Needs its own regression
story.

## Proven defect (Newsela JD 3, 2026-09-13)

Stage 1 author wrote unbracketed identity placeholders:

- heading: unbracketed first-name line, not `[Name]` / `[Full Name]`
- contact: literal `Location | Email | Phone | LinkedIn`

`scripts/apply_resume_header.py` only replaces bracketed `[Name]` /
`[Email]`-style lines. It skipped both. Canonical header fill did not
run.

`quality_checker.check_and_repair_cover_letter` H-001 then injected
the real `workExperience.md` header **above** the leftover placeholder.
Result: stacked real identity plus placeholder labels on the cover
letter.

Session repair used `load_real_header()` from the same gitignored WE
file, then wrote the real header and stripped the leftover labels.
That is not a workflow prevention. No synthetic identity. No SQLite
identity row. No production DB.

## Why this is not SEC-006

Story 8.2 stopped silent John Doe fallback and made missing identity
fail closed. This defect is the next gap: a **present but unbracketed**
placeholder that the helper treats as already-real, after which H-001
can stack a second header.

## Expected future behavior (unimplemented)

1. Placeholder identity must be recognized and replaced **before**
   H-001 / cover-letter header repair.
2. Real identity and placeholder identity must never coexist in
   Resume.md or CoverLetter.md.
3. Malformed or ambiguous identity must fail before authoring
   (`WAITING_FOR_LLM`) or completion (`PRACTICE_COMPLETE` /
   `COMPLETE`).
4. Tests must use synthetic identity only and contain no PII.

## Out of scope for this stub

- Changing `apply_resume_header.py` or H-001 now
- Re-editing Newsela
- Ranking formula
- Score provenance
- Lowering CONVERT-READY floors
