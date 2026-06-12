# Scout PM Title Scope Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop non-PM roles (SDR, Solutions Engineer, Program Manager, etc.) from entering the pipeline at scout ingest — especially from WWR and Himalayas — by applying the same PM title scope gate already used on JobsCollider and Working Nomads.

**Architecture:** Promote `passesBroadPmTitleScope()` from a private helper in `scout_local.ts` into `scripts/domain/gates.ts` as a pure, unit-tested function. Extend it with explicit adjacent-role deny patterns drawn from today's bad ingest. Wire it into `scoutWWR()` and `scoutHimalayas()`. Drop WWR's `remote-management-finance-jobs.rss` feed (it is not a PM feed and would return zero rows after the gate anyway). Update SDD docs under `CR-045` / `FR-195`.

**Tech Stack:** TypeScript (`scripts/domain/gates.ts`, `scripts/scout_local.ts`), Vitest (`tests/unit/gates.test.ts`), Python smoke (`scripts/test_smoke_regression.py`)

**Triggering incident:** 2026-06-11 app pipeline run ingested 22 jobs; 4 WWR junk roles stayed `New` (Kojo SDR, JMS Solutions Engineer, Intapp Program Manager, TCWGlobal Support Operations Program Manager); 15 Himalayas junk roles were evaluated and rejected late.

---

## File map

| File | Responsibility |
|---|---|
| `scripts/domain/gates.ts` | Add/export `passesBroadPmTitleScope()` + `BROAD_NON_PM_TITLE_PATTERNS` |
| `scripts/scout_local.ts` | Import gate; apply in WWR + Himalayas; remove management-finance RSS feed |
| `tests/unit/gates.test.ts` | Unit tests for broad PM scope (including today's bad titles) |
| `docs/spec/05-change-requests/CR-045-scout-pm-title-scope-hardening.md` | Change request |
| `docs/spec/02-requirements-registry.md` | Add `FR-195` |
| `docs/spec/03-feature-specs/FEAT-001-scouting.md` | Update requirements + AC |
| `docs/spec/06-traceability/traceability-matrix.md` | Link `FR-195` → code |
| `docs/spec/08-implementation/IMP-CR-045-scout-pm-title-scope.md` | Implementation notes |

---

### Task 1: Change request + requirement (SDD Layer 2)

**Files:**
- Create: `docs/spec/05-change-requests/CR-045-scout-pm-title-scope-hardening.md`
- Modify: `docs/spec/02-requirements-registry.md`
- Modify: `docs/spec/03-feature-specs/FEAT-001-scouting.md`
- Modify: `docs/spec/06-traceability/traceability-matrix.md`

- [ ] **Step 1: Write CR-045**

Create `docs/spec/05-change-requests/CR-045-scout-pm-title-scope-hardening.md`:

```markdown
# CR-045: Scout PM Title Scope Hardening (WWR + Himalayas)

## Metadata
| Field | Value |
|---|---|
| **CR ID** | `CR-045` |
| **Date** | 2026-06-11 |
| **Status** | Planned |
| **Priority** | P1 |
| **Implements** | `FR-195` |

## Problem statement
`passesBroadPmTitleScope()` exists (FR-187) but is only applied to Working Nomads and JobsCollider.
WWR pulls a second RSS feed (`remote-management-finance-jobs.rss`) with only `passesTitleBlocklist`.
Himalayas trusts API `roles=` slug filtering but returns non-PM listings (SDR, freight broker, etc.).

## Solution
1. Export `passesBroadPmTitleScope()` from `scripts/domain/gates.ts`.
2. Apply at ingest in `scoutWWR()` and `scoutHimalayas()`.
3. Remove WWR management-finance RSS feed.
4. Extend deny patterns for adjacent roles: program manager, solutions engineer, sales development, customer success, account executive.

## Acceptance criteria
| AC ID | Given | When | Then |
|---|---|---|---|
| `AC-209` | Title "Sales Development Representative" | WWR scout ingest | Rejected `not_pm_title_scope` |
| `AC-210` | Title "Solutions Engineer / Network Automation Consultant" | WWR scout ingest | Rejected `not_pm_title_scope` |
| `AC-211` | Title "Program Manager Time Migration" | WWR scout ingest | Rejected `not_pm_title_scope` |
| `AC-212` | Title "Product Manager, B2B SaaS" | WWR scout ingest | Accepted |
| `AC-213` | Title "Senior Product Manager" | Himalayas scout ingest | Accepted |
| `AC-214` | WWR scout runs | Feed list inspected | Only `remote-product-jobs.rss` is fetched |
```

- [ ] **Step 2: Add FR-195 to requirements registry**

In `docs/spec/02-requirements-registry.md`, after `FR-187` row:

```markdown
| `FR-195` | functional | P1 | planned | Broad PM title scope gate applied to WWR + Himalayas; WWR management-finance feed removed; adjacent-role deny patterns | `AC-209`–`AC-214` | CR-045 |
```

- [ ] **Step 3: Update FEAT-001**

In `docs/spec/03-feature-specs/FEAT-001-scouting.md`:
- Add `FR-195`, `CR-045` to metadata Related lists
- Add row to Requirements covered table
- Add `TASK-008` | `FR-195` | WWR + Himalayas broad PM scope | planned
- Add AC-209–AC-214 to acceptance criteria table

- [ ] **Step 4: Update traceability matrix**

Add row linking `FR-195` → `CR-045` → `FEAT-001` → `scripts/domain/gates.ts`, `scripts/scout_local.ts`.

- [ ] **Step 5: Commit**

```bash
git add docs/spec/
git commit -m "docs: CR-045 scout PM title scope hardening (FR-195)"
```

---

### Task 2: Export and extend `passesBroadPmTitleScope` in gates.ts (TDD)

**Files:**
- Modify: `scripts/domain/gates.ts`
- Modify: `tests/unit/gates.test.ts`
- Modify: `scripts/scout_local.ts` (remove local duplicate after export)

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/gates.test.ts` (import `passesBroadPmTitleScope`):

```typescript
import {
    // ...existing imports...
    passesBroadPmTitleScope,
} from '../../scripts/domain/gates.js';

describe('passesBroadPmTitleScope', () => {
    it('accepts Product Manager', () => {
        expect(passesBroadPmTitleScope('Product Manager')).toBe(true);
    });
    it('accepts Senior Product Manager', () => {
        expect(passesBroadPmTitleScope('Senior Product Manager')).toBe(true);
    });
    it('accepts Product Owner', () => {
        expect(passesBroadPmTitleScope('Product Owner - SEPA/Payments')).toBe(true);
    });
    it('accepts Technical Product Manager', () => {
        expect(passesBroadPmTitleScope('Technical Product Manager')).toBe(true);
    });
    it('rejects Product Marketing', () => {
        expect(passesBroadPmTitleScope('Product Marketing Consultant (part-time)')).toBe(false);
    });
    // Implements FR-195 (CR-045) — 2026-06-11 incident titles
    it('rejects Sales Development Representative', () => {
        expect(passesBroadPmTitleScope('Sales Development Representative')).toBe(false);
    });
    it('rejects Solutions Engineer', () => {
        expect(passesBroadPmTitleScope('Solutions Engineer / Network Automation Consultant')).toBe(false);
    });
    it('rejects Program Manager', () => {
        expect(passesBroadPmTitleScope('Program Manager Time Migration')).toBe(false);
    });
    it('rejects Support Operations Program Manager', () => {
        expect(passesBroadPmTitleScope('Support Operations Program Manager (SaaS) REMOTE')).toBe(false);
    });
    it('rejects Account Executive', () => {
        expect(passesBroadPmTitleScope('Account Executive')).toBe(false);
    });
    it('rejects Customer Success Manager', () => {
        expect(passesBroadPmTitleScope('Senior Customer Success Manager')).toBe(false);
    });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
npm test -- tests/unit/gates.test.ts -t passesBroadPmTitleScope
```

Expected: FAIL — `passesBroadPmTitleScope` is not exported from `gates.ts`

- [ ] **Step 3: Implement in gates.ts**

Add after `passesBuiltInPmTitleScope` block in `scripts/domain/gates.ts`:

```typescript
/** FR-187 / FR-195: PM-family titles for broad-category RSS/API feeds (not Built In strict). */
const BROAD_NON_PM_TITLE_PATTERNS: RegExp[] = [
    /\bproduct marketing\b/i,
    /\bproduct design/i,
    /\bproduct analyt/i,
    // FR-195 (CR-045): adjacent roles that leak through category/search feeds
    /\bprogram manager\b/i,
    /\bproject manager\b/i,
    /\bsolutions engineer\b/i,
    /\bsales development\b/i,
    /\baccount executive\b/i,
    /\bcustomer success\b/i,
    /\binside sales\b/i,
];

export function passesBroadPmTitleScope(title: string): boolean {
    const t = (title || '').trim();
    if (!t) return false;
    for (const pat of BROAD_NON_PM_TITLE_PATTERNS) {
        if (pat.test(t)) return false;
    }
    return (
        /\bproduct manager\b/i.test(t) ||
        /\bproduct owner\b/i.test(t) ||
        /\b(technical|platform|data|ai|api|integration|enterprise|infrastructure) product\b/i.test(t)
    );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npm test -- tests/unit/gates.test.ts -t passesBroadPmTitleScope
```

Expected: PASS (all cases)

- [ ] **Step 5: Commit**

```bash
git add scripts/domain/gates.ts tests/unit/gates.test.ts
git commit -m "feat(FR-195): export passesBroadPmTitleScope with adjacent-role deny patterns"
```

---

### Task 3: Wire gate into scout_local.ts

**Files:**
- Modify: `scripts/scout_local.ts`

- [ ] **Step 1: Import exported gate; delete local duplicate**

At top import block, add:

```typescript
import {
    // ...existing...
    passesBroadPmTitleScope,
} from './domain/gates.js';
```

Delete the local `function passesBroadPmTitleScope` block (lines ~881–892).

- [ ] **Step 2: Harden scoutWWR**

In `scoutWWR()`:

1. Change feeds array to product feed only:

```typescript
const feeds = [
    'https://weworkremotely.com/categories/remote-product-jobs.rss',
];
```

2. After parsing `title`, before `passesTitleBlocklist`, add:

```typescript
if (!passesBroadPmTitleScope(title)) {
    console.log(`[REJECT] ${title} at ${company} (WWR) - not_pm_title_scope`);
    continue;
}
```

- [ ] **Step 3: Harden scoutHimalayas**

In the Himalayas posting loop, after `if (!title || !company || !url) continue;`, add:

```typescript
if (!passesBroadPmTitleScope(title)) {
    console.log(`[REJECT] ${title} at ${company} (Himalayas) - not_pm_title_scope`);
    continue;
}
```

- [ ] **Step 4: Run full unit suite**

```bash
npm test
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add scripts/scout_local.ts
git commit -m "feat(FR-195): apply broad PM title scope to WWR and Himalayas scouts"
```

---

### Task 4: Smoke verification against today's bad titles

**Files:**
- Modify: `scripts/test_smoke_regression.py` (if REG section exists for gates)

- [ ] **Step 1: Add Python smoke assertion (optional but recommended)**

If `test_smoke_regression.py` imports gate helpers, add:

```python
from scripts.domain.gates import passesBroadPmTitleScope  # only if TS gate is mirrored; otherwise skip

# Simpler: invoke vitest subset from smoke runner
```

**Preferred approach** — add a subprocess call in smoke regression:

```python
import subprocess
result = subprocess.run(
    ["npm", "test", "--", "tests/unit/gates.test.ts", "-t", "passesBroadPmTitleScope"],
    capture_output=True, text=True, cwd=PROJECT_ROOT,
)
assert_test("REG-16: Broad PM title scope blocks adjacent roles",
            result.returncode == 0,
            result.stdout + result.stderr)
```

- [ ] **Step 2: Run smoke**

```bash
python scripts/test_smoke_regression.py
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add scripts/test_smoke_regression.py
git commit -m "test(REG-16): smoke broad PM title scope gate"
```

---

### Task 5: Implementation notes + status closure

**Files:**
- Create: `docs/spec/08-implementation/IMP-CR-045-scout-pm-title-scope.md`
- Modify: `docs/spec/05-change-requests/CR-045-scout-pm-title-scope-hardening.md` (status → Implemented)
- Modify: `docs/spec/02-requirements-registry.md` (`FR-195` status → implemented)

- [ ] **Step 1: Write IMP doc**

```markdown
# IMP-CR-045: Scout PM Title Scope Hardening

## Requirements
- `FR-195`, `AC-209`–`AC-214`

## Changes
- `passesBroadPmTitleScope()` promoted to `scripts/domain/gates.ts`
- WWR: product RSS only; broad PM scope at ingest
- Himalayas: broad PM scope at ingest

## Verification
- `npm test -- tests/unit/gates.test.ts -t passesBroadPmTitleScope` — PASS
- `npm test` — PASS
- `python scripts/test_smoke_regression.py` — PASS

## Out of scope
- Remotive / Jobicy / OpenPostings (search-term filtered; no incident data)
- Retroactive DB cleanup of 2026-06-11 junk rows (manual, see Task 6)
```

- [ ] **Step 2: Mark CR + FR implemented**

- [ ] **Step 3: Commit**

```bash
git add docs/spec/
git commit -m "docs: close IMP-CR-045 scout PM title scope hardening"
```

---

### Task 6: Clean up today's junk rows (manual, post-merge)

Not a code change — run after deploy to clear the 4 bad `New` jobs already in SQLite.

- [ ] **Step 1: Inspect**

```bash
python -c "
import sqlite3
c = sqlite3.connect('jobagent.sqlite')
for r in c.execute(\"SELECT company, title, status, source_site FROM jobs WHERE status='New' AND created_at >= '2026-06-11'\"):
    print(r)
"
```

- [ ] **Step 2: Reject junk (keep Neostella, Capco, Revalize)**

```sql
UPDATE jobs
SET status = 'Rejected',
    summary = 'Not a fit — ingest scope reject (pre-FR-195 junk)',
    score = 0
WHERE status = 'New'
  AND created_at >= '2026-06-11'
  AND source_site IN ('WWR', 'Himalayas');
```

Run via:

```bash
python -c "
import sqlite3
c = sqlite3.connect('jobagent.sqlite')
c.execute('''
UPDATE jobs SET status = \"Rejected\",
  summary = \"Not a fit — ingest scope reject (pre-FR-195 junk)\",
  score = 0
WHERE status = \"New\" AND created_at >= \"2026-06-11\"
  AND source_site IN (\"WWR\", \"Himalayas\")
''')
c.commit()
print('updated', c.total_changes, 'rows')
"
```

Expected: 4 rows updated (Kojo, JMS, TCWGlobal, Intapp). JobsCollider `New` rows (Neostella, Capco, Revalize) remain.

---

## Self-review (spec coverage)

| Requirement / AC | Task |
|---|---|
| Export gate to domain module | Task 2 |
| WWR broad PM scope | Task 3 |
| Himalayas broad PM scope | Task 3 |
| Remove management-finance feed | Task 3 |
| Adjacent-role deny patterns | Task 2 |
| Unit tests for incident titles | Task 2 |
| SDD docs + traceability | Task 1, 5 |
| DB cleanup | Task 6 |

No placeholders. All code shown is complete.

---

## Execution handoff

**Plan saved to:** `docs/superpowers/plans/2026-06-11-scout-pm-title-scope-hardening.md`

**Two execution options:**

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks
2. **Inline Execution** — run tasks in this session with checkpoints

**Which approach?**
