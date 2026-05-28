# CR-020: 20 Local Optimizations

## Metadata

| Field | Value |
|---|---|
| **CR ID** | `CR-020` |
| **Status** | Implemented |
| **Priority** | P1 |
| **Date** | 2026-05-28 |
| **Builds on** | `CR-019` |
| **Implements** | `FR-111` through `FR-130` |

## Decision

Implement 20 local-first optimizations requested to improve JobAgent's ability to run efficiently on 8GB-16GB VRAM systems, reducing reliance on cloud APIs and speeding up the drafting pipeline. Features include vector-based JD deduplication, local salary extraction, DOM cleanup for HTML, SQLite FTS5 search integration, Local WebGPU grammar inference using MLC WebLLM, Auto-Pruning DB scripts, SSE Text Streaming for local models, and Zero-Shot On-Site Classifier.

## Acceptance criteria

- **AC-119:** JD Deduplication via Vector Similarity
- **AC-120:** I/O vs GPU Concurrency Splitting safely
- **AC-121:** Local Salary Extraction passes string matching
- **AC-122:** Vector-Based ATS Backlog Re-ranking sorts efficiently
- **AC-123:** Rapid Metadata Tagging via vectors
- **AC-124:** SQLite FTS5 Search Integration for faster dashboard
- **AC-125:** DOM Cleanup Pre-Processor for JDs
- **AC-126:** Prompt Context Truncation Guard for Local LLMs
- **AC-127:** Fast-Fail Context Fallbacks inside `_call_local`
- **AC-128:** Local Skill-Gap Analysis route works without cloud
- **AC-129:** Cover Letter Intro Customization drafted correctly
- **AC-130:** Local Offline Web Research (SearXNG)
- **AC-131:** Competitor Matrix via Local Vectors
- **AC-132:** Zero-Shot On-Site Classifier determines remote status
- **AC-133:** Auto-Pruning Stale DB Blobs via `setInterval`
- **AC-134:** Local Model Text Streaming (SSE) integrated with UI
- **AC-135:** WebGPU Browser-Side Inference loads MLC WebLLM worker
- **AC-136:** Responsive PDF Layout Feedback dynamically scales PDF
- **AC-137:** Notification Webhooks (NTFY) sent on batch completion
- **AC-138:** Local PII Redaction Guard via Regex masks sensitive info

## Files

| File | Action |
|------|--------|
| `scripts/auto_prune_db.py` | New |
| `scripts/rerank_backlog.py` | New |
| `scripts/zero_shot_classifier.py` | New |
| `scripts/dom_cleanup.py` | New |
| `scripts/metadata_tagger.py` | New |
| `src/lib/grammarCheck.ts` | WebGPU |
| `src/lib/grammar-worker.ts` | WebGPU |
| `scripts/utils.py` | Edited (PII guard, truncations) |
| `scripts/batch_pipeline.py` | Edited (Concurrency, Fast Gates) |
| `src/components/DocumentEditor.tsx` | Edited (SSE, Linting) |
| `server/routes/system.ts` | Edited (SSE) |
| `server/index.ts` | Edited (Cron auto-pruning) |
