# Applyr Public-Ready Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Applyr safe for public GitHub scrutiny — no PII, no secrets, no personal application history in tracked files or git history, and pipeline code that works for any user who configures their own profile.

**Architecture:** Three layers of defense: (1) **git history purge** removes data already pushed to `JobHuntAgent`; (2) **`.gitignore` + untracked index** keeps personal runtime data local-only going forward; (3) **profile-driven code** replaces hardcoded contact info and dogfood employer constants with SQLite `identity` profile + `data/workExperience.md` parsing. A CI `audit_public_repo.py` gate blocks regressions.

**Tech Stack:** Python 3.10+, TypeScript/React, SQLite (`jobagent.sqlite`), git-filter-repo, GitHub Actions

**Current state (2026-06-09):** Phase 2 partial work is done locally but uncommitted (~512 staged deletions). `python scripts/audit_public_repo.py` passes on 319 tracked files. **Blocker:** `jobhunt/main` on GitHub still contains `archive/`, personal `data/`, and old hardcoded PII in history.

---

## Phase 0: Revoke compromised secrets (manual, do first)

No code changes. Do before any public push.

- [ ] **Step 1: Revoke OpenAI key** (if ever in KinBridge or elsewhere)
  - Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
  - Revoke any key that appeared in plain-text files

- [ ] **Step 2: Revoke Gemini keys from deprecated scratch scripts**
  - Files (local only, gitignored under `archive/`): `archive/deprecated-scripts/scripts-scratch/fix_db_key.py`, `test_all_keys.py`
  - Keys to revoke at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) — see local `archive/deprecated-scripts/scripts-scratch/` (never commit those files)
  - Rotate any key stored in local `jobagent.sqlite` via Settings → API

- [ ] **Step 3: Verify no keys in tracked files**

```powershell
Set-Location "C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Applyr"
git grep -E "sk-[A-Za-z0-9]{20,}|AIzaSy[A-Za-z0-9_-]{30,}" $(git ls-files)
```

Expected: no output

---

## Phase 1: Purge git history on public remote (critical blocker)

**Why:** `.gitignore` and `git rm --cached` only affect *future* commits. `https://github.com/JasonWayneT/JobHuntAgent.git` (`jobhunt` remote) already has 414+ `archive/` files and personal `data/` in commit `6c5acca`.

**Choose one strategy:**

| Strategy | When to use | Risk |
|----------|-------------|------|
| **A. git-filter-repo** | Repo has valuable commit history to keep | Rewrites all SHAs; force-push required |
| **B. Orphan branch** | Repo is young; clean slate is fine | Loses history; simplest |

### Task 1A: History purge with git-filter-repo (recommended)

**Files:**
- None created; operates on `.git/`

- [ ] **Step 1: Install git-filter-repo**

```powershell
pip install git-filter-repo
```

- [ ] **Step 2: Backup the repo**

```powershell
Copy-Item -Recurse "C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Applyr" "C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Applyr-backup-pre-purge"
```

- [ ] **Step 3: Run path purge**

```powershell
Set-Location "C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Applyr"

git filter-repo --force `
  --path archive/ --invert-paths `
  --path submissions/ --invert-paths `
  --path .agent/ --invert-paths `
  --path docs/reports/ --invert-paths `
  --path docs/legacy/ --invert-paths `
  --path data/workExperience.md --invert-paths `
  --path data/workExperience_summary.md --invert-paths `
  --path data/Resume.md --invert-paths `
  --path data/Cover_Letter_Reference.md --invert-paths `
  --path data/Resume_Style_Reference.md --invert-paths `
  --path data/application_question_bank.md --invert-paths `
  --path data/bridge_phrases.json --invert-paths `
  --path data/candidate_preferences.json --invert-paths `
  --path data/master_claims.json --invert-paths `
  --path data/claim_embeddings.json --invert-paths `
  --path data/cover_voice.md --invert-paths `
  --path data/Resume_LinkedIn_Featured.md --invert-paths `
  --path PRODUCT_CAPABILITIES_AND_RELEASE_NOTES.md --invert-paths `
  --path-glob "*.sqlite" --invert-paths `
  --path-glob ".env*" --invert-paths
```

Expected: "Parsed N commits" and "New history written"

- [ ] **Step 4: Re-add remotes** (filter-repo removes them)

```powershell
git remote add jobhunt https://github.com/JasonWayneT/JobHuntAgent.git
git remote add origin https://github.com/JasonWayneT/ApplyrPrivate.git
```

- [ ] **Step 5: Verify purged history**

```powershell
git log --all --full-history -- archive/ | Measure-Object -Line
git log --all --full-history -- data/workExperience.md | Measure-Object -Line
```

Expected: 0 lines for both

- [ ] **Step 6: Force-push public remote** (only after Jason approves)

```powershell
git push jobhunt main --force
```

### Task 1B: Orphan branch fallback (if filter-repo fails)

- [ ] **Step 1: Create orphan branch with current clean tree**

```powershell
Set-Location "C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Applyr"
git checkout --orphan public-main
git add -A
git commit -m "chore: public-ready baseline — scrubbed personal data and secrets"
```

- [ ] **Step 2: Replace main and force-push**

```powershell
git branch -M main
git push jobhunt main --force
```

---

## Phase 2: Commit local hardening (already implemented, needs commit)

Most of this work is done in the working tree. Verify before committing.

**Files already modified:**
- `.gitignore` — expanded ignore rules
- `scripts/utils.py` — `load_identity_profile()`, `format_contact_header_block()`, `contact_placeholder_map()`
- `scripts/drafting_engine.py`, `style_compliance_guard.py`, `quality_checker.py`, `local_draft_stages.py` — profile-driven contact
- `src/components/Sidebar.tsx`, `SettingsView.tsx` — generic placeholders
- `scripts/bootstrap_local_data.py` — copies all example templates
- `scripts/audit_public_repo.py` — pre-push scanner (new)
- `scripts/pii_guard.py`, `smoke_draft_compiler.py`, `test_resume_conversion_eval.py` — generic test fixtures
- `data/job_fit_engine.md`, `docs/spec/*.md` — de-personalized references
- ~430 files `git rm --cached` (archive, personal data, .agent)

### Task 2: Verify and commit Phase 2

- [ ] **Step 1: Run public audit**

```powershell
Set-Location "C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Applyr"
python scripts/audit_public_repo.py
```

Expected: `PUBLIC REPO AUDIT PASSED`

- [ ] **Step 2: Run existing smoke suite**

```powershell
python scripts/bootstrap_local_data.py
pip install -r requirements.txt
npm ci
npm run build
python scripts/smoke_draft_compiler.py
python scripts/test_smoke_regression.py
```

Expected: all pass

- [ ] **Step 3: Review staged deletions**

```powershell
git status --short | Select-String "^D" | Measure-Object -Line
git diff --cached --stat | Select-Object -Last 5
```

Expected: ~430 deletions, no personal files re-added

- [ ] **Step 4: Commit** (when Jason requests)

```powershell
git add -A
git commit -m "$(cat <<'EOF'
chore: harden repo for public release

Remove personal application history from tracking, load contact info from
SQLite identity profile, expand gitignore, and add audit_public_repo gate.
EOF
)"
```

---

## Phase 3: Genericize dogfood employer logic in pipeline scripts

**Problem:** 15 Python scripts still hardcode `Cision`, `Sterkly`, `National University`, and `zero_to_sixty` in repair/guard logic. This is not contact PII, but it fingerprints the repo as built for one person and breaks for fresh clones.

**Approach:** Add `scripts/candidate_context.py` that parses employers, education, and contact from `data/workExperience.md` + SQLite `identity`. All guards import from there instead of literals.

### Task 3: Create candidate_context module

**Files:**
- Create: `scripts/candidate_context.py`
- Test: `scripts/test_candidate_context.py`

- [ ] **Step 1: Write the failing test**

Create `scripts/test_candidate_context.py`:

```python
import unittest
from candidate_context import parse_employers_from_experience, build_contact_header


SAMPLE_EXP = """# John Doe

## **Acme Corp**
**Product Manager**
*   Did a thing with metrics.
"""


class TestCandidateContext(unittest.TestCase):
    def test_parse_employers(self):
        employers = parse_employers_from_experience(SAMPLE_EXP)
        self.assertIn("Acme Corp", employers)

    def test_build_contact_header_uses_profile(self):
        header = build_contact_header({
            "name": "John Doe",
            "location": "City, State",
            "phone": "555-019-9238",
            "email": "email@example.com",
            "linkedin": "linkedin.com/in/johndoe",
        })
        self.assertIn("# JOHN DOE", header)
        self.assertIn("email@example.com", header)
        self.assertNotIn("jason.wayne", header.lower())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
python scripts/test_candidate_context.py
```

Expected: FAIL — `ModuleNotFoundError: candidate_context`

- [ ] **Step 3: Implement candidate_context.py**

Create `scripts/candidate_context.py`:

```python
"""Load candidate-specific context from profile + workExperience.md."""
from __future__ import annotations

import os
import re

from utils import WORK_EXP_FILE, load_identity_profile, format_contact_header_block


def parse_employers_from_experience(text: str) -> list[str]:
    pattern = re.compile(r"^## \*\*(.+?)\*\*", re.MULTILINE)
    return [m.group(1).strip() for m in pattern.finditer(text or "")]


def parse_education_from_experience(text: str) -> list[str]:
    hits = []
    for line in (text or "").splitlines():
        if "university" in line.lower() or "bachelor" in line.lower() or "master" in line.lower():
            hits.append(line.strip().lstrip("* ").strip())
    return hits


def load_work_experience_text() -> str:
    if os.path.exists(WORK_EXP_FILE):
        with open(WORK_EXP_FILE, encoding="utf-8") as f:
            return f.read()
    return ""


def build_contact_header(profile: dict | None = None) -> str:
    return format_contact_header_block(profile)


def employer_slugs(text: str) -> list[str]:
    """Lowercase slug keys for employer header lookup."""
    return [re.sub(r"[^a-z0-9]+", "_", e.lower()).strip("_") for e in parse_employers_from_experience(text)]
```

- [ ] **Step 4: Run test to verify it passes**

```powershell
python scripts/test_candidate_context.py
```

Expected: OK

- [ ] **Step 5: Commit**

```powershell
git add scripts/candidate_context.py scripts/test_candidate_context.py
git commit -m "feat: add candidate_context module for profile-driven pipeline"
```

### Task 4: Refactor quality_checker.py employer repair blocks

**Files:**
- Modify: `scripts/quality_checker.py` (lines ~432-448 — Cision/Sterkly/zero_to_sixty injection)
- Modify: `scripts/local_draft_stages.py` (`EMPLOYER_EXPERIENCE_HEADERS` dict)

- [ ] **Step 1: Replace hardcoded employer repair in quality_checker.py**

Remove blocks like:

```python
if "cision" not in lower:
    content += "\n" + EMPLOYER_EXPERIENCE_HEADERS["cision"]...
```

Replace with dynamic loop over `parse_employers_from_experience(load_work_experience_text())` — only inject a stub `## **{employer}**` header if that employer slug is missing from content.

- [ ] **Step 2: Refactor EMPLOYER_EXPERIENCE_HEADERS in local_draft_stages.py**

Build headers at runtime from parsed employers in `workExperience.md` instead of a static dict with `cision`, `sterkly`, `zero_to_sixty` keys.

- [ ] **Step 3: Run smoke suite**

```powershell
python scripts/smoke_draft_compiler.py
python scripts/test_smoke_regression.py
```

- [ ] **Step 4: Commit**

```powershell
git add scripts/quality_checker.py scripts/local_draft_stages.py
git commit -m "refactor: derive employer headers from workExperience instead of hardcoded names"
```

### Task 5: Refactor remaining employer literals

**Files to modify (grep-confirmed):**
- `scripts/drafting_engine.py` — `KNOWN_HALLUCINATIONS`, `BLOCKED_TOOLS` comments referencing Jason
- `scripts/style_compliance_guard.py` — any remaining employer-specific normalization
- `scripts/resume_conversion_eval.py` — test fixtures using Cision/Sterkly
- `scripts/conversion_framing.py`, `draft_compiler.py`, `resume_rubric.py`, `critique_retry.py`, `qc_fixer.py`, `generate_master_claims.py`

- [ ] **Step 1: Grep for remaining literals**

```powershell
git grep -l "Cision\|Sterkly\|National University\|zero_to_sixty" -- scripts/
```

- [ ] **Step 2: Replace each with data-driven lookup or generic example names** (`Acme Corp`, `Example Inc`, `Example University`)

- [ ] **Step 3: Re-run audit + smoke**

```powershell
python scripts/audit_public_repo.py
python scripts/smoke_draft_compiler.py
```

- [ ] **Step 4: Commit**

```powershell
git add scripts/
git commit -m "refactor: remove dogfood employer literals from pipeline scripts"
```

---

## Phase 4: CI gate and governance docs

### Task 6: Add audit to GitHub Actions

**Files:**
- Modify: `.github/workflows/smoke.yml`

- [ ] **Step 1: Add audit step before smoke tests**

Insert after checkout in `.github/workflows/smoke.yml`:

```yaml
      - name: Public repo audit (no PII in tracked files)
        run: python scripts/audit_public_repo.py
```

- [ ] **Step 2: Push and verify CI green**

- [ ] **Step 3: Commit**

```powershell
git add .github/workflows/smoke.yml
git commit -m "ci: gate public repo audit on every push"
```

### Task 7: Add SECURITY.md

**Files:**
- Create: `SECURITY.md`

- [ ] **Step 1: Create SECURITY.md**

```markdown
# Security Policy

## Reporting a Vulnerability

Email security concerns privately before opening a public issue.

## Secrets handling

- API keys belong in **Settings → API or Connections** (local SQLite only).
- Never commit `.env`, `jobagent.sqlite`, `submissions/`, `archive/`, or `data/workExperience.md`.
- Run `python scripts/audit_public_repo.py` before pushing.

## If you forked and see personal data in git history

That is a history contamination issue. Do not use keys found in old commits — rotate immediately.
```

- [ ] **Step 2: Commit**

```powershell
git add SECURITY.md
git commit -m "docs: add security policy for public repo"
```

---

## Phase 5: Fresh-clone verification (public user journey)

### Task 8: Simulate a new user's first run

- [ ] **Step 1: Clone to temp directory**

```powershell
git clone https://github.com/JasonWayneT/JobHuntAgent.git C:\Temp\applyr-fresh-clone
Set-Location C:\Temp\applyr-fresh-clone
```

- [ ] **Step 2: Bootstrap and build**

```powershell
python scripts/bootstrap_local_data.py
npm ci
npm run build
python scripts/audit_public_repo.py
```

Expected: audit passes; example data files created

- [ ] **Step 3: Grep clone for PII patterns**

```powershell
git grep -i "760-317\|jason.wayne\|redacted-linkedin-slug" $(git ls-files)
```

Expected: no output

- [ ] **Step 4: Document any gaps in README Troubleshooting** if bootstrap misses a file

---

## Phase 6: GitHub repo settings and launch checklist

### Task 9: Pre-launch checklist

- [ ] **Public audit passes locally:** `python scripts/audit_public_repo.py`
- [ ] **Git history clean:** `git log --all -- archive/` returns nothing
- [ ] **CI green** on `main` after force-push
- [ ] **Fresh clone test** passes (Task 8)
- [ ] **All compromised API keys revoked** (Phase 0)
- [ ] **Repo settings on GitHub:**
  - Default branch: `main`
  - No secrets in Actions variables
  - Consider: disable fork workflows if paranoid about CI abuse
- [ ] **Private data stays local:** confirm `ApplyrPrivate` (`origin` remote) is where dogfood history lives if needed
- [ ] **Optional:** add `data/README.md` explaining which files are user-local vs example templates

---

## Execution order summary

```
Phase 0 (revoke keys)     → manual, 10 min
Phase 2 (commit hardening)→ 30 min, mostly done
Phase 1 (history purge) → 1 hr, BLOCKER before public push
Phase 3 (genericize code)→ 2-4 hrs
Phase 4 (CI + SECURITY) → 30 min
Phase 5 (fresh clone)   → 30 min
Phase 6 (launch)        → 15 min
```

**Do not push to `jobhunt` until Phase 0 + Phase 1 + Phase 2 are complete.**

---

## Self-review (spec coverage)

| Requirement | Task |
|-------------|------|
| No PII in tracked files | Phase 2 (done), Phase 4 Task 6 (CI gate) |
| No PII in git history | Phase 1 |
| No API keys in repo | Phase 0, Phase 2 audit |
| No personal submissions | Phase 1 + `.gitignore` |
| Works for new users | Phase 3 + Phase 5 |
| Profile-driven contact | Phase 2 (done) |
| Employer-agnostic pipeline | Phase 3 |
| Automated regression prevention | Phase 4 |

**Open gap:** `master_claims.example.json` still uses `cision` as employer slug in examples — acceptable as fictional template data, but could be renamed to `acme_corp` in a follow-up for extra cleanliness.
