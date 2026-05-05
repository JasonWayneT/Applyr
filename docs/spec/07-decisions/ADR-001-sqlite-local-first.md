# Architecture Decision Record: ADR-001 SQLite Local-First

## Status

accepted

## Context

Job hunting involves sensitive PII (Phone, Address, Full History). We need a database that is fast, local, and requires zero cloud infrastructure.

## Decision

Use SQLite (`better-sqlite3` for Node, `sqlite3` for Python) as the primary data store. The database is a single file (`jobagent.sqlite`) in the repo.

## Requirement links

- `SEC-001` Zero-Knowledge Architecture
- `DATA-001` SQLite Persistence

## Consequences

- **Positive:** No cloud setup, absolute privacy, easy backups.
- **Negative:** Limited to single-user (acceptable for this use case).
