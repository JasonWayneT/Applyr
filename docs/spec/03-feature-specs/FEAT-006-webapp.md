# Feature Spec: FEAT-006 Web Application

## Metadata

- Feature ID: `FEAT-006`
- Status: implemented
- Source artifacts: `BMAD-SRC-003`
- Related requirements: `FR-023`, `FR-024`, `FR-025`, `FR-026`, `FR-027`, `FR-028`, `FR-029`

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

## Verification plan

| Test ID | Requirement/AC IDs | Test type | Expected result | Status |
|---|---|---|---|---|
| `TEST-006` | `FR-024` | manual | Clicking "Sync" starts the terminal log in the UI | verified |
| `TEST-007` | `FR-026`, `FR-028` | manual | Clicking Edit opens a side-by-side split screen with rich editor | accepted |
| `TEST-008` | `FR-027` | manual | Clicking Save & Compile saves Markdown, regenerates PDF, and updates iframe | accepted |
