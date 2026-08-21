"""
Generate data/agent_context_pack.md -- a single, lean briefing document that
authoring/reviewing subagents read instead of separately cold-reading
AGENTS.md, SKILL.md, data/workExperience.md, and data/conversion_rubric.md
each time (measured 2026-07-27: ~47.7k tokens of pure fixed overhead per
agent, repeated across every Stage 1/Stage 2 agent in a batch).

AGENTS.md is the canonical always-on rules file (CLAUDE.md is now a thin
`@AGENTS.md` import stub for Claude Code, not a second copy -- see the
harness-bridge session-009 rules/reference split). This script reads
AGENTS.md directly; it does NOT read CLAUDE.md, which would only return the
short stub text.

Why a *generated* file, not a hand-edited one: AGENTS.md and SKILL.md
deliberately carry their own incident history ("Added 2026-07-21, after X
shipped in 5 of 11 letters...") -- that history has real value for a human
auditing why a rule exists, and for anyone doing a self-repair fix. Stripping
it permanently would be a real loss. This script instead extracts only the
sections a drafting/reviewing agent actually needs and regenerates on demand,
so the source docs stay exactly as rich as they are today.

Extraction scope (deliberately conservative -- section-level cuts only, never
sentence-level narrative stripping inside a kept section, because that's
exactly the kind of edit that can silently drop an operative rule):

- AGENTS.md: drop two named top-level sections that are pure engineering/
  pipeline-maintenance content, irrelevant to drafting or reviewing a real
  submission ("Active Engineering Work", "Documentation Update Checklist").
  Everything else is copied verbatim.
- SKILL.md: drop the "Self-repair protocol" section -- only relevant when
  actively fixing a process bug, not during normal Stage 0-3 execution.
  Everything else (Stage 0/1/2/3, Cross-Harness Operating Rules) is copied
  verbatim.
- workExperience.md: copied with §1.0 / 1.0a (contact / references) stripped
  (CR-094). Remaining stories, metrics, VOC, and DO NOT CLAIM hedges stay.
- conversion_rubric.md: copied verbatim, no trimming.
- master_claims.json: NOT bundled into the markdown pack (different format,
  consumed differently). See generate_claims_tags_only() below -- writes a
  sibling data/master_claims_tags_only.json with `text`/`cover_story`
  stripped from every claim, since SKILL.md's own Stage 1 instruction is
  "read tags only, never text/cover_story" -- this makes that instruction
  true by construction instead of relying on every agent to self-police it.

Freshness: a machine-readable manifest (sha256 of every source file at
generation time) is embedded as an HTML comment at the top of the generated
pack. check_context_pack_freshness.py recomputes those hashes and fails loudly
if any source file has changed since the pack was generated -- see that
script's own docstring for why this has to be a hard gate, not a reminder.

Usage:
    python scripts/generate_context_pack.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

AGENTS_MD = os.path.join(REPO_ROOT, "AGENTS.md")
SKILL_MD = os.path.join(REPO_ROOT, ".claude", "skills", "generate-submission", "SKILL.md")
WORK_EXPERIENCE_MD = os.path.join(REPO_ROOT, "data", "workExperience.md")
CONVERSION_RUBRIC_MD = os.path.join(REPO_ROOT, "data", "conversion_rubric.md")
MASTER_CLAIMS_JSON = os.path.join(REPO_ROOT, "data", "master_claims.json")

PACK_OUTPUT = os.path.join(REPO_ROOT, "data", "agent_context_pack.md")
CLAIMS_TAGS_OUTPUT = os.path.join(REPO_ROOT, "data", "master_claims_tags_only.json")

MANIFEST_MARKER_START = "<!-- CONTEXT_PACK_MANIFEST"
MANIFEST_MARKER_END = "-->"

# Exact ## heading text (without the "## " prefix) to drop from AGENTS.md.
AGENTS_MD_EXCLUDE_SECTIONS = frozenset(
    {
        "Active Engineering Work — Read This First If You're Here to Build, Not Draft",
        "Documentation Update Checklist — Where to Update When You Change Pipeline Behavior",
    }
)

# Exact ## heading text to drop from SKILL.md.
SKILL_MD_EXCLUDE_SECTIONS = frozenset(
    {
        "Self-repair protocol — what to do when a real JD surfaces a mistake",
    }
)

# Same PII headings Stage 0 already excludes from evidence_scale retrieval (CR-094).
_WE_PII_HEADING_SUBSTRINGS = ("contact information", "professional references")
_WE_HEADING_SPLIT_RE = re.compile(r"(?m)^(#{1,4}\s+.*)$")


def _sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def split_into_h2_sections(markdown_text: str) -> list[tuple[str, str]]:
    """
    Split a markdown document into (heading_text, full_section_text) pairs at
    '## ' boundaries. The preamble before the first '## ' heading is returned
    as a pair with heading_text == "" (always kept, never filtered).
    """
    lines = markdown_text.splitlines(keepends=True)
    sections: list[tuple[str, list[str]]] = []
    current_heading = ""
    current_lines: list[str] = []
    for line in lines:
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            sections.append((current_heading, current_lines))
            current_heading = m.group(1)
            current_lines = [line]
        else:
            current_lines.append(line)
    sections.append((current_heading, current_lines))
    return [(heading, "".join(body)) for heading, body in sections]


def filter_sections(markdown_text: str, exclude_headings: frozenset) -> str:
    kept = [
        body
        for heading, body in split_into_h2_sections(markdown_text)
        if heading not in exclude_headings
    ]
    return "".join(kept)


def strip_we_pii_sections(we_text: str) -> str:
    """Drop WE sections whose headings name contact or professional references.

    Implements CR-094. Stage 1 still must not load the pack; this is defense if a
    process/cloud session does. Does not log the dropped body.
    """
    if not we_text:
        return we_text
    parts = _WE_HEADING_SPLIT_RE.split(we_text)
    out: list[str] = []
    if parts and parts[0]:
        out.append(parts[0])
    for i in range(1, len(parts), 2):
        heading = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        if any(s in heading.lower() for s in _WE_PII_HEADING_SUBSTRINGS):
            continue
        out.append(heading)
        out.append(body)
    return "".join(out)


def generate_claims_tags_only() -> dict:
    """
    Read master_claims.json and return an equivalent structure with `text`
    and `cover_story` stripped from every claim entry. Preserves everything
    else (ids, tags, disabled flag, any other metadata field) untouched, and
    preserves claim count exactly -- this is a field-level filter, not a
    claim-level filter (disabled claims stay present with their `disabled`
    flag intact, since Stage 1 needs to see that flag to skip them).
    """
    with open(MASTER_CLAIMS_JSON, encoding="utf-8") as f:
        raw = json.load(f)

    def _strip_claim(claim: dict) -> dict:
        return {k: v for k, v in claim.items() if k not in ("text", "cover_story")}

    if isinstance(raw, list):
        return [_strip_claim(c) if isinstance(c, dict) else c for c in raw]
    if isinstance(raw, dict):
        # Some claim catalogs are wrapped as {"claims": [...]}; handle both shapes.
        if "claims" in raw and isinstance(raw["claims"], list):
            out = dict(raw)
            out["claims"] = [
                _strip_claim(c) if isinstance(c, dict) else c for c in raw["claims"]
            ]
            return out
        # Dict-of-claims shape: {"ACC-101": {...}, "ACC-102": {...}}
        return {
            k: (_strip_claim(v) if isinstance(v, dict) else v) for k, v in raw.items()
        }
    raise ValueError(f"Unrecognized master_claims.json top-level shape: {type(raw)}")


def build_manifest() -> dict:
    # Keys must be paths relative to REPO_ROOT -- check_context_pack_freshness.py
    # joins these directly onto REPO_ROOT to relocate each source file. This bit
    # a real run once already (SKILL.md's key didn't match its actual nested
    # path), which is exactly the kind of mismatch the freshness check exists
    # to catch -- fixed here at the source instead of papering over it.
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            os.path.relpath(AGENTS_MD, REPO_ROOT).replace(os.sep, "/"): _sha256(AGENTS_MD),
            os.path.relpath(SKILL_MD, REPO_ROOT).replace(os.sep, "/"): _sha256(SKILL_MD),
            os.path.relpath(WORK_EXPERIENCE_MD, REPO_ROOT).replace(os.sep, "/"): _sha256(
                WORK_EXPERIENCE_MD
            ),
            os.path.relpath(CONVERSION_RUBRIC_MD, REPO_ROOT).replace(os.sep, "/"): _sha256(
                CONVERSION_RUBRIC_MD
            ),
            os.path.relpath(MASTER_CLAIMS_JSON, REPO_ROOT).replace(os.sep, "/"): _sha256(
                MASTER_CLAIMS_JSON
            ),
        },
    }


def generate_pack() -> tuple[str, dict]:
    with open(AGENTS_MD, encoding="utf-8") as f:
        agents_trimmed = filter_sections(f.read(), AGENTS_MD_EXCLUDE_SECTIONS)
    with open(SKILL_MD, encoding="utf-8") as f:
        skill_trimmed = filter_sections(f.read(), SKILL_MD_EXCLUDE_SECTIONS)
    with open(WORK_EXPERIENCE_MD, encoding="utf-8") as f:
        work_experience = strip_we_pii_sections(f.read())
    with open(CONVERSION_RUBRIC_MD, encoding="utf-8") as f:
        conversion_rubric = f.read()

    manifest = build_manifest()
    manifest_comment = (
        f"{MANIFEST_MARKER_START}\n{json.dumps(manifest, indent=2)}\n{MANIFEST_MARKER_END}"
    )

    parts = [
        manifest_comment,
        "",
        "# Applyr Agent Context Pack (generated -- do not hand-edit)",
        "",
        "This file is generated by `scripts/generate_context_pack.py` from the "
        "real source docs below. It exists so a drafting/reviewing subagent reads "
        "ONE lean file instead of cold-reading AGENTS.md + SKILL.md + "
        "workExperience.md + conversion_rubric.md separately every time.",
        "",
        "**Before relying on this file, run `python scripts/check_context_pack_freshness.py` "
        "and confirm it prints FRESH.** If it reports STALE, a source doc changed since this "
        "was generated -- regenerate first (`python scripts/generate_context_pack.py`), don't "
        "proceed on stale rules.",
        "",
        "**If you are fixing a process bug (not drafting a submission), also read "
        "`.claude/skills/generate-submission/SKILL.md`'s Self-repair protocol section directly "
        "-- it is intentionally excluded from this pack as drafting-irrelevant.**",
        "",
        "**Claim retrieval**: read `data/master_claims_tags_only.json` for claim tags "
        "(an index into workExperience.md). Packet excerpts are WE spans, not catalog "
        "`text`/`cover_story`. Stage 1 still must not load this pack.",
        "",
        "---",
        "",
        "## From AGENTS.md",
        "",
        agents_trimmed,
        "",
        "---",
        "",
        "## From SKILL.md (.claude/skills/generate-submission/SKILL.md)",
        "",
        skill_trimmed,
        "",
        "---",
        "",
        "## From data/workExperience.md",
        "",
        work_experience,
        "",
        "---",
        "",
        "## From data/conversion_rubric.md",
        "",
        conversion_rubric,
        "",
    ]
    return "\n".join(parts), manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    pack_text, manifest = generate_pack()
    with open(PACK_OUTPUT, "w", encoding="utf-8") as f:
        f.write(pack_text)

    claims_tags_only = generate_claims_tags_only()
    with open(CLAIMS_TAGS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(claims_tags_only, f, indent=2)
        f.write("\n")

    pack_chars = len(pack_text)
    claims_chars = os.path.getsize(CLAIMS_TAGS_OUTPUT)
    source_chars = sum(
        os.path.getsize(p)
        for p in (AGENTS_MD, SKILL_MD, WORK_EXPERIENCE_MD, CONVERSION_RUBRIC_MD, MASTER_CLAIMS_JSON)
    )
    print(f"Wrote {PACK_OUTPUT} ({pack_chars:,} chars)")
    print(f"Wrote {CLAIMS_TAGS_OUTPUT} ({claims_chars:,} chars)")
    total_new = pack_chars + claims_chars
    reduction_pct = 100.0 * (1 - total_new / source_chars) if source_chars else 0.0
    print(
        f"Source total: {source_chars:,} chars -> Pack total: {total_new:,} chars "
        f"({reduction_pct:.1f}% reduction)"
    )
    print(f"Manifest: {json.dumps(manifest, indent=2)}")


if __name__ == "__main__":
    main()
