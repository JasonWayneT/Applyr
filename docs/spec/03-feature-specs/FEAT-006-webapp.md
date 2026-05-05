# Feature Spec: FEAT-006 Web Application

## Metadata

- Feature ID: `FEAT-006`
- Status: implemented
- Source artifacts: `BMAD-SRC-003`
- Related requirements: `FR-023`, `FR-024`, `FR-025`, `FR-026`, `FR-027`, `FR-028`

## Problem statement

A CLI-only pipeline is hard to monitor. Users need a visual dashboard to watch progress, edit their profile, and manage job leads.

## Goals

- `GOAL-001`: Provide a real-time terminal stream in the UI.
- `GOAL-002`: Allow inline editing of `workExperience.md`.

## Requirements covered

| Requirement ID | Summary | Notes |
|---|---|---|
| `FR-023` | Express API | Backend bridge |
| `FR-024` | Sync Dashboard | Polling-based UI |
| `FR-025` | Profile Hub | Markdown editor |

## Verification plan

| Test ID | Requirement/AC IDs | Test type | Expected result | Status |
|---|---|---|---|---|
| `TEST-006` | `FR-024` | manual | Clicking "Sync" starts the terminal log in the UI | verified |
