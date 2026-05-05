# Architecture Decision Record: ADR-003 Deterministic Pre-filter

## Status

accepted

## Context

Calling an LLM for every job posting (including "Senior" roles that are obviously wrong) is wasteful.

## Decision

Implement a "Zero-Token Gate" that rejects jobs based on regex matches for titles (e.g., Senior, Director) before the LLM is ever invoked.

## Requirement links

- `FR-006` Zero-Token Gate
- `NFR-002` Cost Optimization

## Consequences

- **Positive:** Massive cost reduction, instant rejection for 50%+ of leads.
- **Negative:** Risk of "false rejections" if blocklist is too aggressive.
