# Architecture Decision Record: ADR-002 Gemini Flash Model

## Status

accepted

## Context

We need an LLM with a massive context window (to read JD + workExperience) but with low cost and high speed for a batch pipeline.

## Decision

Use `gemini-flash-latest` as the default model for fit scoring and asset drafting.

## Requirement links

- `NFR-002` Cost Optimization
- `INT-001` Gemini Integration

## Consequences

- **Positive:** Extremely fast, low cost, handles long documents well.
- **Negative:** Slightly less reasoning depth than Pro models (compensated by deterministic pre-filters).
