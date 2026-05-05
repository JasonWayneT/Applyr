# Architecture Decision Record: ADR-004 Bridge Logic

## Status

accepted

## Context

Jason is transitioning from Platform/Infrastructure PM to Growth/User-facing PM. The resume must bridge this gap without lying.

## Decision

Implement "Bridge Logic" in the drafting engine: map Platform wins (Stability, Latency, Scale) to the *business results* they enabled (User Retention, Faster Onboarding, Revenue Growth).

## Requirement links

- `FR-014` Bridge Logic

## Consequences

- **Positive:** Positions Jason as a "Revenue-aware Technical PM."
- **Negative:** Requires careful audit to ensure business results aren't hallucinated.
