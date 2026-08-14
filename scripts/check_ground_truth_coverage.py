"""
Mechanical ground-truth-coverage check for one or more submission folders.

Why this exists (2026-07-31, Jason-prompted, second occurrence): a batch of
10 real submissions was scored and verified without ever checking whether
stronger, JD-relevant evidence sat unused in the claim catalog. This is the
exact failure mode generate-submission/SKILL.md's Stage 2 point 1 already
names ("ask specifically whether real, relevant ground truth exists that
never made it into the document") -- the rule existed, it just wasn't
mechanically enforced, so it got skipped under the same self-review
collapse the skill's own cross-harness history already documented (R8:
"the drafting model fell back to filling draft_manifest.json's required
fields with plausible/template-shaped scores rather than blocking or
flagging the miss").

What this script does: for a submission folder, cross-reference every
claim's tags in data/master_claims_tags_only.json against the target JD's
text. A claim is "JD-relevant" if any of its tags appears in the JD. A
JD-relevant claim is flagged "possibly unused" if none of its metrics (or,
for metric-less claims, at least two of its tags) appear anywhere in
Resume.md + CoverLetter.md combined. This is a heuristic, not a substitute
for judgment -- a flagged claim might genuinely not fit this specific JD's
framing, or might already be covered under different phrasing than its tag
literally uses. It exists to force the question, the way --audit forces a
second look at a suspiciously identical score, not to auto-fail a
submission.

What this script does NOT do: decide whether a flagged claim should be
added. That's still a real per-document judgment call. It also does not
score anything -- verify_submission.py handles mechanical
lint/structure/metrics/page-count checks, and the qualitative rubric_score
still requires a real read against data/conversion_rubric.md.

Historically (2026-07-31): ACC-111/113/115 existed in master_claims.json before
their WE narratives landed; this script gated them via UNVERIFIED_PROJECT_IDS.
Those three now have full WE backing (2026-08-10); the set was cleared in CR-088.
Keep the empty-set hook so a future phantom project_id can be gated the same way.
ACC-117 (Pendo) had the opposite problem (in WE, missing from claims) and was
added to master_claims earlier -- see CHANGELOG.md. Catalog WE<->claims coverage
is now also checked by scripts/audit_claims_coverage.py (CR-088).

Usage:
    python scripts/check_ground_truth_coverage.py data/submissions/{company}
    python scripts/check_ground_truth_coverage.py data/submissions/{c1} data/submissions/{c2} ...
"""
from __future__ import annotations

import json
import os
import re
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)

# Project ids in master_claims with no backing WE narrative. Empty after CR-088
# cleared ACC-111/113/115 (now in workExperience.md as of 2026-08-10). Add here
# only for genuine phantoms — tag overlap alone is not verification.
UNVERIFIED_PROJECT_IDS: set[str] = set()

_WORD_RE = re.compile(r"[A-Za-z0-9$%]+")


def _normalize(text: str) -> str:
    return text.lower()


def _load_claims() -> dict:
    tags_only_path = os.path.join(_REPO_ROOT, "data", "master_claims_tags_only.json")
    fallback_path = os.path.join(_REPO_ROOT, "data", "master_claims.json")
    path = tags_only_path if os.path.exists(tags_only_path) else fallback_path
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    projects: dict[str, dict] = {}
    for entry in raw.values():
        if entry.get("disabled"):
            continue
        pid = entry["project_id"]
        bucket = projects.setdefault(pid, {"tags": set(), "metrics": set()})
        bucket["tags"] |= set(entry.get("tags", []))
        bucket["metrics"] |= set(entry.get("metrics", []))
    return projects


def _metric_variants(metric: str) -> list[str]:
    """A metric like '$40,000,000' should also match '$40M' or '3,500'
    should match '3500' in prose. Generates the literal, a comma-stripped
    form, a comma-inserted form (for a bare number authored with commas),
    and M/K abbreviations for large dollar figures -- doesn't try to catch
    every possible phrasing, this is a floor, not a perfect matcher."""
    variants = {metric}
    bare = metric.replace(",", "").replace("$", "").replace("%", "")
    is_dollar = metric.startswith("$")
    if bare.isdigit():
        n = int(bare)
        variants.add(bare)
        # comma-inserted form, e.g. 3500 -> 3,500
        variants.add(f"{n:,}")
        if is_dollar:
            variants.add(f"${bare}")
            variants.add(f"${n:,}")
            if n >= 1_000_000 and n % 1_000_000 == 0:
                variants.add(f"${n // 1_000_000}m")
                variants.add(f"${n // 1_000_000} million")
            elif n >= 1_000 and n % 1_000 == 0:
                variants.add(f"${n // 1_000}k")
    return [v.lower() for v in variants]


def check_folder(folder: str) -> dict:
    folder = folder.rstrip("/\\")
    company = os.path.basename(folder)
    jd_path = os.path.join(folder, "Original_JD.txt")
    resume_path = os.path.join(folder, "Resume.md")
    cover_path = os.path.join(folder, "CoverLetter.md")

    result: dict = {"submission": company, "generated_by": "scripts/check_ground_truth_coverage.py"}

    if not os.path.exists(jd_path):
        result["error"] = "Original_JD.txt not found"
        return result

    jd_text = _normalize(open(jd_path, encoding="utf-8").read())
    doc_text = ""
    for p in (resume_path, cover_path):
        if os.path.exists(p):
            doc_text += _normalize(open(p, encoding="utf-8").read()) + "\n"

    if not doc_text:
        result["error"] = "Resume.md and CoverLetter.md both missing -- nothing to check yet"
        return result

    claims = _load_claims()
    flagged = []
    unverified_relevant = []

    for pid, bucket in sorted(claims.items()):
        relevant_tags = sorted(t for t in bucket["tags"] if t.lower() in jd_text)
        if not relevant_tags:
            continue

        if pid in UNVERIFIED_PROJECT_IDS:
            unverified_relevant.append(
                {
                    "project_id": pid,
                    "matched_tags": relevant_tags,
                    "note": "JD-relevant, but this claim has no backing narrative in workExperience.md -- "
                    "do not use until Jason confirms it's real.",
                }
            )
            continue

        if bucket["metrics"]:
            used = any(
                variant in doc_text for m in bucket["metrics"] for variant in _metric_variants(m)
            )
        else:
            # No metric to check literally -- fall back to requiring 2+ tag
            # hits in the actual document text (not just the JD) as a
            # weaker signal the claim's substance made it in.
            tag_hits_in_doc = sum(1 for t in bucket["tags"] if t.lower() in doc_text)
            used = tag_hits_in_doc >= 2

        if not used:
            flagged.append(
                {
                    "project_id": pid,
                    "matched_tags": relevant_tags,
                    "metrics": sorted(bucket["metrics"]),
                }
            )

    result["jd_relevant_claims_possibly_unused"] = flagged
    result["jd_relevant_but_unverified_claims"] = unverified_relevant
    result["clean"] = len(flagged) == 0
    return result


def main() -> None:
    folders = sys.argv[1:]
    if not folders:
        print(__doc__)
        sys.exit(1)

    any_flagged = False
    for folder in folders:
        result = check_folder(folder)
        out_path = os.path.join(folder.rstrip("/\\"), "ground_truth_coverage.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        if result.get("error"):
            print(f"{result['submission']}: SKIPPED -- {result['error']}")
            continue

        flagged = result["jd_relevant_claims_possibly_unused"]
        unverified = result["jd_relevant_but_unverified_claims"]
        if flagged or unverified:
            any_flagged = True
            print(f"{result['submission']}: ATTENTION -- {len(flagged)} possibly-unused, {len(unverified)} unverified-but-relevant")
            for f in flagged:
                print(f"    - {f['project_id']} (tags matched: {', '.join(f['matched_tags'])})")
            for u in unverified:
                print(f"    - {u['project_id']} [UNVERIFIED] (tags matched: {', '.join(u['matched_tags'])})")
        else:
            print(f"{result['submission']}: clean -- no JD-relevant claim found unused")

    if any_flagged:
        sys.exit(1)


if __name__ == "__main__":
    main()
