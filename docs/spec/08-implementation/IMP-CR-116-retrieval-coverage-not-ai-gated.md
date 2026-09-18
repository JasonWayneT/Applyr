# IMP-CR-116 Retrieval coverage is not AI-token-gated

Status: in progress. Stories in `docs/spec/05-change-requests/CR-116-retrieval-coverage-not-ai-gated.md` stay unchecked until independent QA.

## What landed

- `scripts/evidence_scale.py`: synonym expansion (`brief` → `present`/`presented`/`presenting`), window huge inventory chunks around distinctive tokens, force-include the smallest chunk that holds each corpus-backed coverage token. Implements FR-331 / AC-429.
- `retrieval_coverage()` is not AI-token-gated. Sitting-1 sheet now records `coverage_ok`.
- Tests: `scripts/test_evidence_context.py::RetrievalCoverageTests` (synthetic starve corpus plus live WE when present).
- Production switch stays off. No gold labels manufactured.

## Not done

Independent QA has not marked the CR-116 stories. Replay is still not a promotion gate.
