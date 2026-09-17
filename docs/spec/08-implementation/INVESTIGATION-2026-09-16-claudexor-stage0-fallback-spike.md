# Investigation — Subscription-harness (claudexor/Metis) fallback for Stage 0 provider limits

**Date:** 2026-09-16
**Investigator:** Claude Code (Sonnet 5)
**Status:** Spike complete. Blocked on a tool bug in `claudexor`. No implementation started, no CR opened.
**Constraint:** Read-only repo/doc exploration plus one CLI smoke test run from a scratch directory. No changes to Applyr provider code, no production data, no commits.

**Goal:** Jason already has Metis (a separate project) routing engineering work to `claude`/`cursor`/`agy`/`codex`/`factory` through subscription logins instead of API tokens (via the `claudexor` CLI and, for Factory, the `droid` CLI). He wants that same subscription-backed access available to Applyr, specifically as a **fallback provider for Stage 0** — right now Stage 0's default provider chain (Groq → Gemini free tier, per FR-279/CR-108) can't reliably get through a single batch before hitting free-tier rate limits, and he doesn't want to solve that by turning on metered paid API calls. He was explicit that he does not want Applyr to adopt Metis's whole architecture (goals/team-plans/methodology gate) — just the ability to use `agy`, `codex`, `cursor`, `claude` as a provider option, the same way Ollama or a raw Gemini API call are options today.

---

## 1. What already exists in Applyr (no gap here)

- Stage 0's LLM routing is `call_llm()` in `scripts/utils.py`, driven by a provider-policy chain (default Groq → Gemini, Local/Ollama as an explicit opt-in), normalized identically in Python and TypeScript per CR-108/FR-279 (`docs/spec/03-feature-specs/FEAT-007-multi-llm.md`).
- CR-112 already anticipates a subscription-backed cost model: `scripts/cost_eligibility.py` tracks `subscription_minutes` as a field distinct from `api_cents`, specifically so subscription-harness time is never summed with metered API cost. **It is hardcoded to `0` everywhere it appears** — the accounting slot exists, nothing populates it yet.
- A `.metis/` directory is already active in this repo (`evidence/`, `state/`, `team-plans/`) from separate, unrelated CR-112 engineering-dispatch work. That confirms Metis-for-engineering-tasks is already wired up here — but that is Metis's own methodology-gated `dispatch()` path (write-scope checks, doc-approval markers), built for implementation work, not for a per-JD classification call.

## 2. What I checked and found

**a. The subscription auth layer works.** `npx claudexor@3.12.0 accounts snapshot --json` returned live, verified profiles:
- `claude` → Claude Pro, verified via vendor login
- `codex` → ChatGPT Plus, verified via vendor login
- `agy` (Antigravity) → verified, bound to `gemini-3.8-flash-high`
- `cursor` → **not reliably verified** — status `unknown`, "cursor-agent status returned unrecognized JSON output"

**b. The CLI already has the right shape for a Stage-0-style call**, distinct from Metis's own `dispatch()`. `claudexor agent --help` exposes, per-call:
- `--access readonly` (no write intent needed for classification)
- `--workspace-kind directory` (no git init required)
- `--output-schema <file>` — engine-validated JSON Schema conformance for the final answer
- `--no-review`, `--max-seconds <n>`, `--harness <id>`, `--profile <id>`

This means the correct integration point is **Applyr shelling out to the `claudexor`/`droid` CLIs directly as a new provider backend inside `call_llm()`'s chain**, bypassing Metis's Python `dispatch()`/`evaluate_gate()` entirely — that gate enforces engineering-process rules (doc approval, write-scope disjointness) that have no meaning for "classify this JD and return JSON."

**c. It doesn't work yet.** I ran a real dispatch three times from a scratch directory — `claudexor agent "<toy JD classification prompt>" --harness claude --profile claude-default --access readonly --workspace-kind directory --no-review --json --output-schema stage0_schema.json --max-seconds 120` — against a minimal JSON Schema mirroring a Stage-0-shaped decision (role title, seniority, people-management flag, 0-to-1 flag, key skills).

Every attempt failed the same way, ~8–10s in:
```
{"ok": false, "exitCode": 1, "message": "claudexor: daemon connection closed", "error": "claudexor: daemon connection closed"}
```
I explicitly started the daemon (`claudexor daemon start` → reported ready) immediately before the third attempt; it still died mid-call. `Get-CimInstance Win32_Process` found no leftover `claudexor` process afterward (ruling out the stale-daemon/pipe-lock case Metis's own `claudexor.py` already has detection code for). The daemon log (`C:\Users\Jason\.claudexor\v3\daemon\claudexord.log`) shows a fresh `claudexord` PID starting per invocation and going quiet shortly after, across all three attempts — consistent with the daemon crashing during the request rather than a lock/contention problem.

## 3. Assessment

The architecture Jason pointed to is real and is the right shape: subscription-authenticated, schema-constrained, read-only-capable calls to `claude`/`codex`/`agy` (and `droid` for Factory) are technically exposed exactly where Stage 0 would need them. But the actual dispatch path crashes on this machine on the current `claudexor@3.12.0`, on the flag combination Stage 0 would use. That's a bug in `claudexor` itself (Jason's own separate tool), not a wiring mistake — nothing about a Stage 0 integration would route around it.

## 4. Suggested next steps

1. **Root-cause the `claudexor` daemon crash first — this blocks everything else.** Jason has visibility into `claudexor`'s own source/build that I don't from inside Applyr; worth checking whether this is a known issue with 3.12.0, or specific to `--access readonly` / `--workspace-kind directory` / `--output-schema` (a combination Metis's own `dispatch()` never exercises — Metis always calls with `--in-place` write access).
2. **Once one real call succeeds end-to-end**, rerun the smoke test with the actual Stage 0 evidence-cascade JSON schema (not the toy schema used here), and time a small batch (5–10 archived JDs) against it to get a real latency/reliability comparison against Groq/Gemini free-tier throughput — a full agentic harness answering "return this JSON" is a much heavier unit of work than a raw completion call, and that trade-off (removes rate-limit blocking, but likely much slower per item) needs real numbers before it's a fallback anyone would want automatic.
3. **If step 2 looks good, scope it as a CR-112 story** (it fits squarely under the existing CR-112 Stage 0 reliability umbrella): a new provider type in `call_llm()`'s chain that shells out directly to `claudexor`/`droid`, populating `subscription_minutes` for real instead of the current hardcoded `0`, with the same Python/TS provider-policy normalization parity CR-108 already requires for Groq/Gemini.
4. **Decide the policy shape before writing the story:** Jason's framing was an opt-in fallback for when Groq+Gemini are both rate-limited mid-batch, not a first-class Settings-selectable provider on par with them — worth locking that down explicitly so the story doesn't quietly grow into full provider parity.
5. `cursor`'s profile isn't reliably verifiable right now (`cursor-agent status` returns unrecognized JSON) — scope any first pass to `claude`/`codex`/`agy` and treat `cursor` as a later addition once that's sorted.
