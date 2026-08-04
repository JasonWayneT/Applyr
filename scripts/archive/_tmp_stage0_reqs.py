# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Print requirements-focused excerpts for Stage 0."""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

jobs = json.loads(Path("data/_tmp_stage0_batch.json").read_text(encoding="utf-8"))
out_path = Path("data/_tmp_stage0_reqs.txt")
lines: list[str] = []

# Section header patterns that often start requirements
start_pats = [
    r"we'?re looking for",
    r"you'?ll need",
    r"what you'?ll need",
    r"requirements",
    r"qualifications",
    r"basic qualifications",
    r"minimum qualifications",
    r"required qualifications",
    r"must[- ]have",
    r"you have",
    r"you bring",
    r"about you",
    r"who you are",
    r"ideal candidate",
    r"skills and experience",
    r"what we'?re looking",
]

end_pats = [
    r"nice to have",
    r"preferred",
    r"bonus",
    r"supercharge",
    r"benefits",
    r"perks",
    r"compensation",
    r"what we offer",
    r"about (the )?company",
    r"equal opportunity",
]

def emit(s: str = "") -> None:
    lines.append(s)
    print(s)


for i, j in enumerate(jobs, 1):
    jd = j["jd"]
    emit("=" * 80)
    emit(f"{i}. {j['company']} — {j['position']}")
    emit(f"URL: {j['url'][:100]}")
    emit("-" * 40)
    # Find first requirements-ish section
    lower = jd.lower()
    starts = []
    for pat in start_pats:
        for m in re.finditer(pat, lower, re.I):
            starts.append(m.start())
    if starts:
        start = min(starts)
        # take up to 1800 chars from first hit
        chunk = jd[start : start + 2000]
        emit(chunk[:2000])
    else:
        # fallback: last 40% of JD often has quals
        chunk = jd[int(len(jd) * 0.45) :]
        emit("(no clear header — mid/late JD slice)")
        emit(chunk[:2000])
    emit()

out_path.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {out_path}")
