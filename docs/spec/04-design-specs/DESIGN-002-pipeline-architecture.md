# Design Spec: DESIGN-002 Pipeline Architecture

## Metadata

- Design spec ID: `DESIGN-002`
- Status: implemented
- Related feature specs: `FEAT-001` through `FEAT-005`
- Related requirements: `ARCH-001`, `ARCH-002`

## System Overview

JobAgent is a hybrid Python/Node system. 
- **Frontend:** React SPA (Vite)
- **Backend:** Express API (Node)
- **Pipeline:** Batch-processing scripts (Python)
- **Persistence:** SQLite for logs/leads; Markdown for career data.

## Pipeline Sequence

1. `scout.ts` / `openpostings.py` (Ingestion)
2. `batch_pipeline.py` (Orchestration)
3. `evaluate_job_fit` (Gating)
4. `research-engine.py` (Intelligence)
5. `drafting_engine.py` (Generation)
6. `claim_verifier.md` (Audit)

## Data Flow

- The React UI triggers the Express API.
- Express spawns a Python subprocess for the batch pipeline.
- Python reads/writes to `jobagent.sqlite` and the `jobs/` directory.
- React polls the API for log updates from SQLite.
