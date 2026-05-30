# CR-028: Collection Quality — Keywords, Anchors, Scout Fixes

## Metadata

| Field | Value |
|---|---|
| **CR ID** | `CR-028` |
| **Date** | 2026-05-30 |
| **Status** | Implemented |
| **Priority** | P1 |
| **Implements** | `FR-171`, `FR-172`, `FR-173` |

## Problem statement

1. Zero-token keyword gate used loose OR matching on `jd_required_keywords` (including `"product"`), letting generic JDs through.
2. `required_anchors` referenced in fit rubric but not preserved in materialized prefs.
3. Levels.fyi scout used `"Product Manager"` fallback title, inventing false PM roles.
4. Geographic gate bypassed all checks when description &lt; 50 chars, leaking non-remote stubs for Remote-only seekers.

## Solution

| FR | Summary |
|---|---|
| `FR-171` | `must_have_keywords` (AND, max enforced in gate) + `signal_keywords` (OR); materializer preserves both |
| `FR-172` | `required_anchors` preserved in JSON; optional `ANCHOR_GATE_ENABLED=1` two-anchor zero-token gate |
| `FR-173` | Levels.fyi skip without parseable title; Remote-only geo bypass tightened |

## Acceptance criteria

| AC ID | Given | When | Then |
|---|---|---|---|
| `AC-179` | `must_have_keywords: ["saas","b2b"]` | JD contains only "agile" | Zero-token reject |
| `AC-180` | `ANCHOR_GATE_ENABLED=1`, anchors configured, 1 anchor in JD | Batch gate | Reject `anchor_hits_1` |
| `AC-181` | Levels.fyi card text empty title | Scout | Row skipped, not inserted as PM |
| `AC-182` | `work_setting: Remote`, BuiltIn stub no description | Scout geo | Rejected (not bypassed) |

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `ANCHOR_GATE_ENABLED` | `0` | Enable deterministic two-anchor gate |
