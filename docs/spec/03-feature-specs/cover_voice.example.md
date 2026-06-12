# Cover Letter Voice (Deterministic) — Example Spec

**CR-043** · Runtime: `scripts/cover_phrasing.py` · Not the My Voice Writer skill.

Copy to `data/cover_voice.md` for local notes (gitignored). Code enforces the rules below.

## Identity thread (repeat across covers)

- Outcome-driven implementer: VOC and churn signals drive what engineering ships.
- Plain PM vocabulary: roadmap, backlog, stakeholder, platform, VOC, migration.
- Human-to-human: explain complex work the way you would to a sharp colleague.

## Do

- Keep **all grounded metrics** (%, ~, $, account counts) from `cover_story` and claims.
- Application-first opener: `I am applying for the {role} role at {company}.`
- **Value-first hook** (CR-044): next sentence from primary `cover_story` (setup + metric), not JD mirroring.
- **Show don't tell**: demonstrate tenure and requirements through stories; never recite “I bring 5+ years…”.
- `cover_story` paragraphs stand alone — no “That experience is relevant to…” bridge.
- **Forward close**: one sentence naming a specific JD business problem (`extract_role_challenge`), not generic availability.
- Dedupe opener: no stacked `match_thesis`, theme mirrors, or repeated fit phrases.

## Do not

- Okay so, right?, you know?, push back if you disagree.
- Robot bridges: “That experience is directly relevant to…”, “Together, these examples reflect…”
- Formal upgrades: utilize, leverage, furthermore, moreover.
- Em-dashes (—).
- Layoff / RIF language (use resource constraints — FR-096).
- LLM voice rewrite on the submission path.

## Word budget

- Target **300–400** words (renderer + audit).
- Do not trim metrics to hit word count.

## Situational vs My Voice skill

| My Voice (Slack/email) | Cover slice |
|------------------------|-------------|
| Okay so / I think / right? | Direct statements, no hedging stack |
| Same casual as technical | Professional-direct, still plain |
| Em-dash in edited examples | Commas and periods only |
