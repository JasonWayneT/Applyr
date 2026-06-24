# PII Refactor and Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Relocate candidate PII from the tracked `CLAUDE.md` to gitignored local configuration files and verify that the public repo scanner continues to pass.

**Architecture:** Remove personal contact details from the tracked `CLAUDE.md` file and document how agents dynamically access identity profiles via gitignored files (`data/workExperience.md`). Update the template `workExperience.example.md` with structured mock fields.

**Tech Stack:** Markdown, Python (for verification via `audit_public_repo.py` and `run_all_tests.py`).

---

### Task 1: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Replace Who This Is For section in CLAUDE.md**

Modify [CLAUDE.md](file:///c:/Users/Jason/Desktop/Jason/Resource/CodeProjects/Applyr/CLAUDE.md) around lines 7-12:
```diff
-## Who This Is For
-
-**Jason Taylor** — B2B SaaS Platform PM, 6+ years. Mid-level IC target (PM II). Based in San Diego, CA.
-- Email: jason.wayne.t@example.com | Phone: (000) 000-0000
-- LinkedIn: https://www.linkedin.com/in/jason-taylor-placeholder/ | Portfolio: Taylorbuilt.me
+## Who This Is For
+
+This workspace is configured for a **B2B SaaS Platform PM** with 6+ years of experience.
+To protect candidate privacy:
+- All real contact details (PII) are stored locally in the gitignored [data/workExperience.md](file:///c:/Users/Jason/Desktop/Jason/Resource/CodeProjects/Applyr/data/workExperience.md) (Section 1.0) and inside the gitignored SQLite database `jobagent.sqlite`.
+- Do NOT write or commit real names, emails, phone numbers, or LinkedIn URLs to tracked Git files.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: remove PII placeholders from CLAUDE.md and add pointer instructions"
```

---

### Task 2: Add Contact Info to data/workExperience.md

**Files:**
- Modify: `data/workExperience.md`

- [ ] **Step 1: Add Section 1.0 to data/workExperience.md**

Modify [data/workExperience.md](file:///c:/Users/Jason/Desktop/Jason/Resource/CodeProjects/Applyr/data/workExperience.md) around line 27:
```diff
 ## Section 1: Role Identity & Positioning
 
+### 1.0 Contact Information (Gitignored Ground Truth)
+- Name: Jason Taylor
+- Email: [REDACTED_EMAIL]
+- Phone: [REDACTED_PHONE]
+- LinkedIn: https://www.linkedin.com/in/redacted-linkedin-slug/
+- Portfolio: Taylorbuilt.me
+
 Jason Taylor is a **B2B SaaS Platform Product Manager** with 6+ years of experience...
```

- [ ] **Step 2: Verify git status shows workExperience.md is still ignored**

Run: `git status`
Expected: `data/workExperience.md` is NOT listed under untracked files or changes (since it is ignored by git).

---

### Task 3: Add Contact Info template to data/workExperience.example.md

**Files:**
- Modify: `data/workExperience.example.md`

- [ ] **Step 1: Add Contact Information header block to data/workExperience.example.md**

Modify [data/workExperience.example.md](file:///c:/Users/Jason/Desktop/Jason/Resource/CodeProjects/Applyr/data/workExperience.example.md) around lines 1-3:
```diff
 # Master Career Context Spec (example)
 
+## Contact Information (Example)
+- Name: John Doe
+- Email: john.doe@example.com
+- Phone: (555) 019-9238
+- LinkedIn: https://www.linkedin.com/in/johndoe/
+- Portfolio: johndoe.com
+
 ## Professional Summary
```

- [ ] **Step 2: Run verification scripts locally**

Run: `python scripts/audit_public_repo.py`
Expected: `PUBLIC REPO AUDIT PASSED`

Run: `python scripts/run_all_tests.py --python-only`
Expected: `OVERALL RESULT: SUCCESS`

- [ ] **Step 3: Commit**

```bash
git add data/workExperience.example.md
git commit -m "docs: add mock contact details to workExperience.example.md"
```
