# Feature Spec: FEAT-010 Master Career Experience Onboarding

## Metadata

- Feature ID: `FEAT-010`
- Status: implemented
- Source artifacts: User Request
- Related requirements: `FR-050`, `FR-051`, `DATA-001`
- Related features: `FEAT-009` (ACC-ID codification engine), `FEAT-005` (style compliance)

## Problem statement

New users opening the Experience tab had no guidance on what to enter, what the five-section document
structure means, or why proof codes exist. Existing users editing a codified document had no clear
rules about how to add new claims, correct wording, or safely retire outdated achievements without
silently breaking the anti-hallucination traceability chain.

## Goals

- `GOAL-001`: Give first-time users an onboarding path that explains the VOC/MET/ACC system before they paste raw content.
- `GOAL-002`: Show experienced users at a glance how many coded proof points their document contains.
- `GOAL-003`: Document the three safe edit patterns — Minor Edit, New Claim, Retire — in-context so users never need to guess.
- `GOAL-004`: Mirror the SDD "retire, don't delete" convention in user-facing language so the mental model transfers.

## Users and stories

| Story ID | Priority | User story | Related requirements |
|---|---|---|---|
| `STORY-010-01` | P1 | As a new user, I want to understand what to paste and why before I start, so I don't paste the wrong thing. | `FR-050` |
| `STORY-010-02` | P1 | As an experienced user, I want to see how many ACC/VOC/MET codes my document contains so I know how well-sourced my drafts will be. | `FR-050` |
| `STORY-010-03` | P1 | As an experienced user, I want clear guidance on how to fix a typo, add a new achievement, or retire a stale claim without breaking existing codes. | `FR-051` |

## Requirements covered

| Requirement ID | Summary | Notes |
|---|---|---|
| `FR-050` | Context-Aware Experience Onboarding Flow | Two-state UI based on `experience.trim().length < 100`; empty → onboarding; active → status bar |
| `FR-051` | Claim Update Protocol | Collapsible three-panel guide with retire-don't-delete rule, mirrors SDD convention |

## Architecture

### State gate

```
experience.trim().length < 100
    → Empty state: onboarding card + raw paste textarea
    → Active state: codification status bar + collapsible edit guide + full editor textarea
```

The 100-character threshold is a heuristic — below it the file is considered uninitialized.
The threshold is not a hard requirement boundary; it prevents the status bar from flashing
during brief intermediate edits.

### Live code counts

```typescript
const expStats = useMemo(() => ({
  acc: (experience.match(/ACC-\d+/g) || []).length,
  voc: (experience.match(/VOC-\d+/g) || []).length,
  met: (experience.match(/MET-\d+/g) || []).length,
}), [experience]);
```

Counts update live as the user types. They reflect what the codification engine last wrote —
not what the user is currently drafting (new untagged lines won't count until saved).

### Retire-don't-delete convention

Retiring a claim means removing the `[ACC-NNN]` tag from the bold header (`**[ACC-NNN] text**`
becomes `**text**`). On the next save, `codifyExperienceAndAssignIDs()` skips the untagged bold
line (no code pattern found) and does not assign a new code. The text is preserved as historical
context but future AI drafts cannot cite it because no proof code points to it.

This is intentional: silently deleting a claim would erase the record. Unlinking preserves
evidence while removing the AI's ability to fabricate or embellish from it.

## UI layout

### Empty state

Single card with three zones:
1. **Header** — icon, title, and anti-hallucination purpose explanation
2. **Getting started** — paste instructions, VOC/MET/ACC three-card grid (icon + label + description)
3. **Toolbar + textarea** — filename label, "Save & Sync AI" CTA (disabled until dirty), raw paste area with descriptive placeholder

### Active state

Three stacked components:
1. **Codification status bar** — verified icon, "Codification Active" label, live ACC/VOC/MET count pills
2. **Collapsible edit guide** — toggle reveals three panels:
   - *Minor Edit — Safe*: keep the `[ACC-NNN]` tag; wording changes are safe
   - *New Claim — Add*: add a plain bold line; system assigns next available code on save
   - *Retire a Claim — Unlink*: remove the tag; keep the plain text; AI cannot cite unlinked lines
   - Info banner: "Never delete a coded line entirely. Retire, don't delete."
   - Document structure reference grid (§1–§5 labels)
3. **Editor** — toolbar with filename, unsaved-changes indicator, "Save & Sync AI" CTA, full-height textarea

## Acceptance criteria

| AC ID | Requirement ID | Given | When | Then |
|---|---|---|---|---|
| `AC-052` | `FR-050` | `data/workExperience.md` is empty or under 100 chars | User opens Experience tab | Empty-state onboarding card is shown with VOC/MET/ACC three-card layout and paste CTA; active-state appears once content exceeds threshold |
| `AC-053` | `FR-051` | User removes `[ACC-NNN]` tag from a bold header and saves | Server calls `codifyExperienceAndAssignIDs()` | Plain-text line is preserved in `workExperience.md` with no new ACC code; future AI drafts cannot cite it |

## Implementation tasks

| Task ID | Requirement IDs | Description | Status |
|---|---|---|---|
| `TASK-010-01` | `FR-050` | Add `isExperienceEmpty` boolean and `expStats` useMemo to `ProfileView.tsx` | done |
| `TASK-010-02` | `FR-050` | Replace Experience tab JSX with two-branch conditional (empty/active state) | done |
| `TASK-010-03` | `FR-050` | Implement empty-state onboarding card with VOC/MET/ACC three-card explanation | done |
| `TASK-010-04` | `FR-050` | Implement active-state codification status bar with live ACC/VOC/MET counts | done |
| `TASK-010-05` | `FR-051` | Implement collapsible edit guide with Minor Edit / New Claim / Retire panels | done |
| `TASK-010-06` | `FR-051` | Add "Never delete a coded line entirely. Retire, don't delete." info banner | done |
| `TASK-010-07` | `FR-051` | Add document structure reference grid (§1–§5) inside collapsible guide | done |

## Verification plan

| Test ID | Requirement/AC IDs | Test type | Expected result | Status |
|---|---|---|---|---|
| `TEST-010-01` | `AC-052` | manual | Clear `workExperience.md` to empty, open Experience tab — onboarding card appears; paste 200+ chars and save — status bar replaces onboarding card | accepted |
| `TEST-010-02` | `AC-053` | manual | Take a coded line `**[ACC-101] Built X**`, remove tag to get `**Built X**`, save — confirm the line survives in `workExperience.md` with no new ACC code assigned to it | accepted |
| `TEST-010-03` | `FR-050` | manual | Open Experience tab with populated file — confirm status bar shows correct ACC/VOC/MET counts matching manual grep on `workExperience.md` | accepted |
