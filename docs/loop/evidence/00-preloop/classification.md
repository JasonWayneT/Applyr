# Uncommitted work inspected 2026-09-23

Branch point: `6c6837759667009d65253d471fca562d0b309eba` on main.
The working tree had 12 modified pipeline files, about 990 insertions. They were not committed. They are not applied on `loop/2026-09-23`.

The patch file is a record only. Do not `git apply` it. Several hunks loosen a gate, add an allowlist entry, or suppress a finding. The mission marks that class NEEDS_HUMAN.

## Not applied (forbidden or mixed with a loosening)

- `scripts/approved_metrics.py`: adds `25%` and `$100,000` / `100000` to `APPROVED_METRICS`. Allowlist expansion.
- `scripts/build_authoring_packet.py`: adds generic overlap tokens (`analytics`, `ownership`, `communication`, `context`, `decisions`, `stakeholders`, `strategic`). Fewer proof obligations fire.
- `scripts/submission_linter.py`: drops cloud-platform phrases from the JD-paraphrase hook check; treats a trailing plural as a specificity hit; skips `built alignment` in the attribution-verb check; narrows the Ad Hoc company-name pattern.
- `scripts/resume_conversion_eval.py`: stops flagging a coordinated gerund list as a truncated summary sentence.
- `scripts/pipeline_queue.py`: promotes paused rows when the only mech hold is an unapproved metric that the new allowlist would accept, and when a recorded Stage 1 block now passes the loosened checks.
- `scripts/workflow/runner.py`: queue prose rewrite that softens ownership verbs and rewrites an intersection opener. Content rewrite plus the retry policy that depends on the loosened checks. Left with the rest of the mixed diff.

## Possibly a tightening, still not applied

`scripts/author_from_packet.py` calls existing hard blocks (`check_bypass_authorship`, `check_competency_process_notes`, `check_placeholder_company`, `check_cited_span_fidelity`) during Stage 1 verify so repair can see them. That wiring is a candidate for a later iteration only after a confirmed root cause, and only by itself. It was inside the same uncommitted tree as the loosenings, so it was reverted with them.

## Left untracked on purpose

`_tmp_*.txt` and `_tmp_*.py` at the repo root. Not read into this record. Not committed.
`docs/spec/08-implementation/SESSION-PACKS-2026-09-22-paused-queue.md` is a different session. Not part of this loop.
