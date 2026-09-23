---
status: implemented
date: 2026-09-23
related: CR-108, CR-121, CR-122, CR-124
---

# CR-125: Decide from today's work experience, correct later resumes only

## Decision sought

The queue decides when the posting is read. Review Center does not hold it. A later answer can add a tool to work experience. That changes later resumes only.

## Problem

Eligible jobs were sitting in Waiting. A Review Center card, or a model hard label that was not a written rule, stopped the row. A missing required line could also be left out of the fit score, so the number looked better than the posting.

CR-122 stopped the pause on an unknown tool and still opened one skill card per tool. It said Yes could not write work experience. CR-121 and CR-124 still described a required product (Dynamics, Delta Lake) as a withhold. The live scorer already returned verdict `ok` for that absence and kept the name in the reason list.

## Product outcome

Work experience is the closed world. A tool that is not in it is unused. The draft does not claim it.

A card exists only when a named tool is why one or more jobs never went out. One card per tool. The jobs are listed on that card. The sentence is "Stopped because {tool} is not in work experience." "I have used this" appends that tool under `## Confirmed tools` in `workExperience.md`. Nothing reruns on its own. Each listed job has its own Redo. Already-applied jobs stay off the card. A No is not stored. An "or similar" line that already names a catalog tool stays silent. These cards do not hold the queue. Do not add a Skip just to manufacture a card.

The score counts a missing required line as zero. Pass stays 40. From 40 to 64 the job still goes forward. 65 is the stronger band. A written hard gate skips now, with no card: advanced degree, a required certification, years in a named domain (healthcare, health industry, health tech, medical, ceramic), or a role Jason does not do (people management, model training, payments ownership, a title above senior individual contributor, building from nothing). Any other required miss only skips when the score is under 40. A preferred line, or a tool he has not used, never skips or pauses by itself.

A model hard label that is not one of those written rules becomes evidence 0. It does not open a card. Very Good Security's payments-platform line is that case.

Dynamics and Delta Lake can stay in the reason list. They are not claimed. They do not withhold the job. That supersedes the withhold in `FR-368` / `AC-478` and the "still withholds" clause in `FR-374`.

`python scripts/pipeline_queue.py decide-holds` classifies paused question holds from the stored gate and the posting. It does not start the worker. A written skip, or a stored score under 40, becomes `paused_reason=decided_skip`. A review-center pause at 40 or above, or with no stored score and no written skip, returns to queued. Failed runs, disposition holds, and an in-progress lease stay. `decided_skip` is a queue label. The skip ledger and the archive move still happen when Stage 0 runs.

The Pipeline page is its own tab. Each row is Continuing, Skipped, Running, or Failed, with one sentence. There is no Waiting state for a question. Upload lives there. The folder form is tucked at the bottom. Review Center states how many continued, how many were skipped, and that none are waiting, with a link to the pipeline. Nothing on that page starts a worker.

## Kept from earlier CRs

Missing tools do not pause Stage 0 (CR-122). Chrome is not a product gap (CR-124). Requirement-extraction review still pauses. A domain-years line skips with no card, and a Stage 1 timeout retries four times (FR-378).

## Requirements and acceptance

| Requirement | Acceptance |
| --- | --- |
| `FR-379` An unknown tool is unused and does not open a card | `AC-489` A required unknown tool is recorded as absent and creates no pending skill card |
| `FR-380` One card per tool that stopped jobs. "I have used this" writes work experience | `AC-490` A paused conversion-risk job whose gate names the tool is listed. Once queued, it is not. Confirming the tool appends it under Confirmed tools |
| `FR-381` Missing lines count as zero. Written gates skip. Questions do not hold the queue | `AC-491` A stored 38 becomes `decided_skip`. A stored 55 returns to queued. A healthcare-years posting with an empty gate skips. A payments line with no written rule returns to queued |
| `FR-382` Pipeline shows Continuing, Skipped, Running, or Failed | `AC-492` A `decided_skip` row reads as Skipped. An expired lease reads as Failed. A queued row reads as Continuing |

## Release

Tests in `scripts/test_build_stage0_fit_gate.py`, `scripts/test_pipeline_queue.py`, `scripts/test_stage0_confirmations.py`, `tests/unit/reviewCenterRepository.test.ts`, and `tests/unit/pipelineQueueRepository.test.ts`.

Live `decide-holds` on 2026-09-23, without starting the worker: skipped Compugroup, Isotalent, Staritas, Kraken, and Reltio. Queued Very Good Security. Left failed runs, disposition holds, and Allstate's in-progress lease. Did not write `workExperience.md` and did not archive folders.
