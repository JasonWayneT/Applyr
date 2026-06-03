# IMP-CR-040 — Theme primary claims

**CR:** [CR-040-theme-primary-claims.md](../05-change-requests/CR-040-theme-primary-claims.md)  
**Requirements:** `FR-193`, `FR-091`, `FR-101`

## Tasks

| ID | Task | File(s) | Status |
|----|------|---------|--------|
| T1 | Theme → ACC primary map + inject into Stage 2 | `scripts/theme_primaries.py`, `scripts/draft_compiler.py` | done |
| T2 | Quota padding prefers theme primaries | `scripts/local_draft_stages.py` | done |
| T3 | Cover verify corpus = bullets ∪ catalog | `scripts/draft_compiler.py` | done |
| T4 | Security/compliance cover scoring bonus | `scripts/jd_tailoring.py`, `scripts/cover_claim_picker.py` | done |
| T5 | Smoke test | `scripts/smoke_draft_compiler.py` | done |

## Verification

```bash
python scripts/smoke_draft_compiler.py
```
