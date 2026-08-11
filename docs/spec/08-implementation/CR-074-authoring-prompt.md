# CR-074 — Authoring Prompt Contract (Epic 5, Story 5.1)

**Implements:** FR-254  
**Status:** defined 2026-08-06  
**Runner:** `scripts/author_from_packet.py` (Story 5.2)

---

## Purpose

Specifies the exact inputs, constraints, output shape, and fix-loop protocol
for the single cloud compose pass that turns a ready `authoring_packet.json`
into `Resume.md` + `CoverLetter.md`. This contract is what `author_from_packet.py`
assembles into `authoring_prompt.md` for manual paste into Cursor/Claude.

---

## Input format: two blocks

The runner assembles `authoring_prompt.md` with exactly two sections.
Use `--user-format json` (default) for the USER block — pretty JSON
is unambiguous and survives copy-paste without reformatting loss.

### SYSTEM block

Contents of `data/authoring_rule_digest.md` verbatim, as the system prompt.

- Do **not** load `agent_context_pack.md`, full `CLAUDE.md`, or the full skill.
- Do **not** load `master_claims.json` or `workExperience.md`.
- The digest is ~1,600 tokens. The packet is a further 2–8k tokens. Total input
  stays well under 20k — that is the budget target (see CR-074 Epic 1 Metrics).

### USER block

A short preamble followed by the full `authoring_packet.json` as pretty JSON
inside a fenced code block.

#### Preamble text (exact — do not reword)

```
You are authoring a Resume.md and a CoverLetter.md for a job application.

CLOSED-WORLD RULE: use ONLY the claim_ids and excerpts in the packet below.
Do not invent any metric, tool, company, team name, or date not present in the packet.
Do not load any external file. Do not call any tool (tools are not needed for v1).

The packet field `packet_status` MUST be "ready" before you proceed.
If it is not "ready", stop and print the incomplete_reasons — do not draft.

Output exactly three fenced code blocks in this order:
  1. A block labeled "Resume.md" containing the full resume Markdown.
  2. A block labeled "CoverLetter.md" containing the full cover letter Markdown.
  3. A block labeled "claim_provenance.json" containing a JSON object that records, for every
     bullet and proof point you just drafted, which packet claim_ids you used to back it. You
     are already choosing this evidence from the packet's evidence_map as you write each
     bullet — this block just records the choice you already made, it is not new work. Exact
     schema:
       {
         "company": "<packet's company>",
         "resume_claims": [
           {"bullet": "<first several words or full text of the bullet>", "claim_ids": ["ACC-104", "MET-10"]},
           ...
         ],
         "cover_letter_claims": [
           {"proof_point": "<first several words or full text of the proof point>", "claim_ids": ["ACC-117"]},
           ...
         ]
       }
     Use only claim_ids present in the packet below. Every resume bullet and every cover
     letter proof point needs at least one claim_id.

Write each block to its own file in this submission folder, named exactly after the block's
label: Resume.md, CoverLetter.md, and claim_provenance.json.

Do not output anything else between the three blocks.
```

---

## Closed-world constraints (runtime)

The runner enforces these before writing `authoring_prompt.md`:

1. **`packet_status` must be `"ready"`** — refuse + exit 1 if not.
2. **`rule_digest_version` must match current digest** — the digest
   used to generate the system block must be the same version the packet
   was built against. Mismatch → exit 1 unless `--force`.
3. **`authoring_packet.json` must exist** in the target folder — exit 1 if missing.

---

## Output contract

The composing agent MUST produce exactly:

| File | Required | Notes |
|---|---|---|
| `Resume.md` | Yes | Exact structure per digest §2; all three canonical roles; exactly 3 summary sentences; one page. |
| `CoverLetter.md` | Yes | Exact structure per digest §4; 250–400 words; no bullet points. |
| `claim_provenance.json` | Yes (CR-075 Story 5.0) | Records which packet `claim_ids` back each resume bullet / cover letter proof point. Schema in `scripts/claim_provenance.py`'s docstring; checked (WARN-tier) by `verify_submission.py`. |

No other files. No commentary outside the three fenced code blocks.

---

## Tools (v1)

None required. The composer has no tool access and needs none: all evidence is
pre-loaded in the packet. Do not add tool calls for v1.

---

## Fix-loop protocol

After the composer writes `Resume.md` and `CoverLetter.md`, run:

```
python scripts/author_from_packet.py --verify-only data/submissions/COMPANY
```

This runs lint (submission_linter), ground-truth coverage, and JD term checks.
If FAIL, the agent re-edits **using packet + digest only** — no additional
context files. Maximum 2 fix rounds before escalating to Jason.

Docstring in `author_from_packet.py` repeats this protocol so it's visible
at the call site.

---

## Security / anti-injection note

The `authoring_packet.json` content is deterministically built by
`build_authoring_packet.py` from ground-truth sources only (workExperience.md,
master_claims_tags_only.json, JD text). It is **not** built from LLM output.
The packet builder enforces fail-closed rules before setting `packet_status: ready`.

Adversarial fixture payloads are kept in `tests/fixtures/adversarial/` — these
are test inputs for the packet builder's refusal logic, not for this prompt contract.
