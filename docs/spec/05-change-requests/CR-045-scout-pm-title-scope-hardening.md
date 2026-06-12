# CR-045: Scout PM Title Scope Hardening (WWR + Himalayas)

## Metadata
| Field | Value |
|---|---|
| **CR ID** | `CR-045` |
| **Date** | 2026-06-11 |
| **Status** | Implemented |
| **Priority** | P1 |
| **Implements** | `FR-240` |

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
