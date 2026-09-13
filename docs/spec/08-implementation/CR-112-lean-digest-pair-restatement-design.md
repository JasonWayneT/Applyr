---
status: implemented_pending_qa
created: 2026-09-13
from: Cursor (Grok 4.6)
candidate: cr112-integrated-validation-candidate
head: 257b003
related: CR-112, FR-254, NFR-007, AC-332, FR-319, AC-417
scope: lean-digest instruction only; no detector change; not CR-097 promote
---

# Story: lean digest cross-document restatement prevention

Authoring prevention. Detector already exists (`LW-009-PAIR` /
`check_cross_document_repetition`). Do not load the defect ledger, WE,
context pack, or no-ai-slop into Stage 1. Do not change ranking.

## Recurring pattern (do not re-investigate from scratch)

Camunda first draft (untouched 64/57): three near-identical sentences
in resume and letter (Java-platform description, Critical Save /
high-risk account retention, PTO capacity model). Caught after
authoring by `LW-009-PAIR`; digest had no pair-restatement line.

Older evidence (2026-07-20): eight of nine real pairs failed Stage 2
on resume↔letter restatement. Detector and Stage 1 skill prose were
added then. Lean digest (CR-074) never received the line. Camunda
proved the gap still fires.

Sony/Solace example-bank row `sony-resume-letter-repetition-2026-08-22`
already teaches: keep the strongest fact, change structure and
mechanism framing. Digest should not duplicate that example bank.

## Current contracts (do not reopen)

- `AC-332`: substantive `LW-009-PAIR` findings **block Stage 1 verify**.
  `run_verify_only` already sets `passed = False` when pair_warns is
  non-empty. Jason's "advisory unless contracts say otherwise" clause
  applies: leave detector and Stage 1 FAIL as they are.
- Digest is 9538 chars (soft 8000, hard 10000). Headroom ~462 chars.
  Addition must stay well under that.

## Candidate instruction (section 5, Cover Letter Argument Rules)

Two bullets, after the existing JD-paraphrase-hook line:

```
- Same strongest packet fact may appear in both documents. Do not drop
  it, swap to a weaker claim, invent a second story, or add proof
  points or length just to create variety.
- Resume owns metric and outcome wording. The letter must add
  interpretation, decision logic, relevance, or narrative in different
  words. Do not restate a resume bullet in near-identical language.
```

Does not name `LW-009-PAIR` (author does not need the rule id). Does
not load extra files. Does not tell the author to omit strong evidence.

## Tests

- `generate_digest()` contains both operational clauses (keep strongest
  fact; letter adds interpretation/decision/relevance/narrative).
- `build_authoring_prompt` SYSTEM block contains those clauses.
- Negative control: a digest/prompt that mentions "resume" and "cover
  letter" without those clauses must fail the new assertion (prove we
  are not matching incidental document-type words).
- Existing digest size and no-PII tests still pass.

## Independent design review — DR-001

**Reviewer:** Cursor (Claude Opus 4.6), design-review-only mode
**HEAD:** `257b003`
**Verdict: ACCEPT WITH CHANGES**

### Locked instruction (single bullet, 250 chars, ~62 tokens)

```
- Same strongest packet fact may appear in both documents. Do not drop it or swap to a weaker claim for variety. Resume owns the metric/outcome wording. The letter adds interpretation, decision logic, or narrative, not near-identical resume phrasing.
```

Placement: §5 (Cover Letter Argument Rules), after the JD-paraphrase-hook line.

Post-addition digest size: 9788 / 10000 (212 chars headroom remaining).

### What changed from the candidate and why

| Candidate element | Disposition | Reason |
|---|---|---|
| Two bullets | **Compressed to one** | Keep-fact and change-language are two halves of one instruction, not independent rules. Splitting risks an author reading bullet 1 alone ("OK, copy-paste is fine") or bullet 2 alone ("use a different claim"). One bullet makes the duality immediately visible. Also saves ~130 chars. |
| "invent a second story" | **Dropped** | Redundant with §1 Closed-World Rule, which already hard-blocks fabrication. |
| "add proof points or length just to create variety" | **Compressed to "for variety"** | The anti-padding spirit is kept via "Do not drop it or swap to a weaker claim for variety." The specific failure mode (padding) is already covered by §1b's "Do not pad, stretch a claim, or force in extra content." |
| "relevance" in the alternatives list | **Dropped** | Redundant with "interpretation" in this context (why-it-matters-to-this-company is a form of interpretation). Saves 13 chars. |
| "metric and outcome wording" | **Changed to "metric/outcome wording"** | "/" treats them as a unit (a resume bullet's metric IS its outcome framing), reads tighter, and matches how the linter suggestion already phrases it. |

### Challenge results

1. **Ambiguity (claim-swap vs language-change):** LOW RISK. "Do not drop it or swap" plus "not near-identical resume phrasing" creates a clear keep-fact / change-language split in one sentence arc. No plausible misreading that says "use a different claim in the letter."

2. **Token cost:** Original two-bullet candidate was 380 chars (9918 / 10000, only 82 chars headroom). The compressed single bullet is 250 chars (9788 / 10000, 212 chars remaining). Under the ~350-char ask. Approximately 62 tokens added to a ~2384-token digest.

3. **Unintended pressure to omit strong evidence:** Explicitly guarded. "Do not drop it or swap to a weaker claim for variety" is the first imperative the author reads after the permission grant. The sentence order is deliberate: permission first, anti-omission guard second, differentiation requirement third.

4. **Conflict with §3 second-claim guidance:** None. §3 addresses the case where two claims map to the same JD item (use stronger in resume, weaker can go in letter). The new instruction addresses the case where the same claim appears in both documents (keep it, change the language). These are complementary, not competing. §3 uses "can" and "if," making it permissive. An author reading both will understand: different claims for the same JD item is an option, and when the same fact IS shared, the language must differ.

5. **"6+ words" overfitting:** Not present. The candidate correctly says "near-identical resume phrasing" instead of naming the detector's 6-word window. This teaches the job (don't repeat phrasing) without coupling to `find_shared_phrases`'s `min_len=6` implementation detail. If the threshold changes, the instruction still holds.

6. **Two bullets vs one:** One is enough and better. See the compression rationale above.

### Confirmation

- No code changes made
- No paid API calls
- No other worktrees touched
- No WE, context pack, defect ledger, or no-ai-slop loaded
- No ranking, JD, or live submission work

## Out of scope

Detector severity. Ranking formula. CR-097 ledger promote. Example-bank
edits. Regenerating live packets. Camunda re-author.
