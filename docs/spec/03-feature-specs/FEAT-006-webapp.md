# Feature Spec: FEAT-006 Web Application

## Metadata

- Feature ID: `FEAT-006`
- Status: implemented
- Source artifacts: `BMAD-SRC-003`
- Related requirements: `FR-023`, `FR-024`, `FR-025`, `FR-026`, `FR-027`, `FR-028`, `FR-029`, `FR-285`, `FR-316`

## Problem statement

A CLI-only pipeline is hard to monitor. Users need a visual dashboard to watch progress, edit their profile, manage job leads, and visually edit output materials with immediate feedback.

## Goals

- `GOAL-001`: Provide a real-time terminal stream in the UI.
- `GOAL-002`: Allow inline editing of `workExperience.md`.
- `GOAL-003`: Enable seamless browser-based WYSIWYG editing of cover letters and resumes with instant background compilation.

## Requirements covered

| Requirement ID | Summary | Notes |
|---|---|---|
| `FR-023` | Express API | Backend bridge |
| `FR-024` | Sync Dashboard | Polling-based UI |
| `FR-025` | Profile Hub | Markdown editor |
| `FR-026` | Visual WYSIWYG Editor | Toast UI integration |
| `FR-027` | Background PDF compiler | python single compile |
| `FR-028` | Side-by-Side dual pane | Review UI workspace |
| `FR-029` | LLM-assisted document edit | setting key gated |
| `FR-285` | Review Center workflow | Existing sidebar entry, focused question view, progressive evidence, and shared UI/harness resolver (`CR-108`, rollout-flagged) |
| `FR-287` | Bad-data flag | "Not a real skill" answer durably suppresses extraction false positives and feeds the learning loop (`CR-109`) |
| `FR-288` | Single-tap queue flow | Answers save on selection and advance to the next card with a visible transition; no save step (`CR-109`) |
| `FR-289` | Completed-card correction | Completed cards show the recorded answer and support in-place change (`CR-109`) |
| `FR-316` | Submission workflow operator | Review Center shows Stage 0/1/2 status and explicit Start, Resume, and Finalize controls through the authenticated canonical workflow routes (`CR-112`) |

## Verification plan

| Test ID | Requirement/AC IDs | Test type | Expected result | Status |
|---|---|---|---|---|
| `TEST-006` | `FR-024` | manual | Clicking "Sync" starts the terminal log in the UI | verified |
| `TEST-007` | `FR-026`, `FR-028` | manual | Clicking Edit opens a side-by-side split screen with rich editor | accepted |
| `TEST-008` | `FR-027` | manual | Clicking Save & Compile saves Markdown, regenerates PDF, and updates iframe | accepted |
| `TEST-108C` | `FR-285` | integration/UI | Review Center groups pending confirmations, focuses one question, progressively reveals evidence, links affected jobs, and submits answers through the shared resolver | proposed |
| `TEST-108D` | `FR-285`, `NFR-011` | API integration | Review Center list and answer routes use an injected isolated database and cover authentication, grouped answers, hard-gate actions, and idempotent repeats | verified |
| `TEST-109A` | `FR-287`, `AC-375`, `AC-376` | unit/API | BAD_DATA completes skill items, writes durable memory, records history, suppresses re-queue, and is rejected on hard-gate reviews | verified |
| `TEST-109B` | `FR-286`, `AC-374` | unit | Live-failure JD lines (Spirit/Preferred/Thinking/Workday compounds) produce zero or only real-tool candidates | verified |
| `TEST-109C` | `FR-289`, `AC-377`, `AC-378` | unit/API | Completed items surface their recorded answer; re-answering updates memory and appends history | verified |
| `TEST-109D` | `FR-288` | manual UI | Answering a card saves in one tap, the next card appears with the card-swap transition, and the queue drains to a clear state | proposed |
| `TEST-112O` | `FR-316`, `AC-413` | client unit/UI | Operator response normalization is allowlisted, all four commands use authenticated API routes, and a cost pause renders the required no-call/no-cost/incomplete-stage guidance and three resume prerequisites | verified |
