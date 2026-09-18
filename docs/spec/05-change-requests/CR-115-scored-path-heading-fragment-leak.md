---
status: in_progress
date: 2026-09-17
related: CR-086, CR-089, CR-114, FEAT-002
---

# CR-115: Scored-path heading and fragment leak

## Decision

Stage 0's leftover path and scored path do not share leftover `junk`. A JD section heading or truncated fragment that NLP confidently labels required/preferred is scored and can inflate fit. Drop heading/fragment strings from required/preferred **before** evidence scoring, using the same chrome class leftover already junks, before any 30-JD replay that treats `false_skips = 0` and `silent_losses = 0` as a promotion gate.

No model answer is a gold label. This CR does not manufacture adjudication marks.

## Problem

Sitting 1 of the CR-114 8-JD adjudication found a class, not a one-off:

- `accuity:req:0` "Education and Credentials" scored evidence level 4 and matched to the BBA.
- `accuity:req:1` is the actual degree requirement, also level 4, matched to the same BBA. One credential counted twice, once against a heading.
- `1uphealth:req:0` "Mid and Senior level" is job-board metadata scored 3.
- `1uphealth:req:2` "experiences that involve data, APIs and/or systems" is a truncated fragment scored 2.

The leftover path correctly junks "Additional Details", "Company Summary", and "Expectations of the Role". Two paths, opposite treatment of the same class of string. The scored path is the one that moves the fit number.

## What is shared today

`_collect_nlp_section_candidates` runs `_is_boilerplate_item` / `_is_orphan_header_item` / `_is_list_leadin` **before** the leftover vs confident split. Both paths share that filter.

They do **not** share leftover `junk`.

`_ORPHAN_HEADER_LABEL_RE` is an allowlist. "Education and Credentials" is 24 characters, does not end in a colon, and is not on the list, so it survives as a bullet. If local NLP confidence is >= 0.65, it lands in required/preferred and is scored. Leftover `junk` only sees low-confidence lines.

A replay that measures zero silent losses while headings score 4s is measuring the wrong thing.

## Stories

1. [ ] Treat heading/fragment strings as non-scored chrome on the required/preferred path, not only on leftover. Cover section headings without a trailing colon ("Education and Credentials"), job-board metadata ("Mid and Senior level"), and truncated fragments. Independent QA remains. Production switch off.
2. [ ] Add regression fixtures from the sitting-1 8-JD set (Accuity heading vs degree pair, 1uphealth metadata and fragment). A heading must not receive an evidence level that moves fit. Independent QA remains.
3. [ ] Confirm leftover `junk` semantics stay unchanged (chrome visible on the fit gate, never a culture hook, never scored). Independent QA remains.

## Out of scope

- Manufacturing gold labels or enabling `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER`.
- Changing skip rules, travel/visa Settings, or leftover bucket vocabulary.
- Retraining the leftover classifier on unreviewed Agy drafts.

## Implementation gate

Do not run the adjudicated 30-JD replay as a CR-114 promotion gate until Story 1 is in and Story 2 fixtures pass. Jason marks sitting 1 before the next 22 slugs are curated.
