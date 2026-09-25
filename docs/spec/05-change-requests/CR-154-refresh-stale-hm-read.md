# CR-154 — A rewritten document gets a new hiring-manager read

**Status:** Implemented
**Date:** 2026-09-24
**Requirements:** FR-417, AC-528

## Product outcome

When the hiring-manager pass rewrites a document after a read was recorded, that read is rebuilt from the current files. The hash check stays. An open warning other than the read is not closed by this path. A review that fails for any reason other than a stale hash stays parked.

## Why

Holdout 16 parked. The pair warning and the audience warnings were already accepted. Policy passed. The stored read still hashed the previous resume bytes, because this pass rewrites the documents and the finding ids do not change.

## Out of scope

- Loosening the hash check
- Recording a read that does not quote the files
- Accepting a warning that is not already on the heuristic list
- A holdout run
