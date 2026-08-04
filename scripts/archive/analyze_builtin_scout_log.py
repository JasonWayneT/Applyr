# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Parse Built In scout log and summarize funnel."""
import re
import sys
from collections import Counter
from pathlib import Path

log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("logs/builtin-scout-run.txt")
if not log_path.exists():
    alt = Path(__file__).resolve().parents[1] / "logs" / "builtin-scout-run.txt"
    log_path = alt if alt.exists() else log_path

text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else sys.stdin.read()

found = re.findall(r"^\[FOUND\] (.+?) \(Built In\)", text, re.M)
rejects = re.findall(r"^\[REJECT\] (.+)$", text, re.M)

def bucket(reason: str) -> str:
    if "Title Blocklist" in reason:
        return "title_blocklist"
    if "URL already exists" in reason:
        return "url_dup"
    if "Company/Title already exists" in reason:
        return "company_title_dup"
    if "DESCRIPTION_TOO_SHORT" in reason:
        return "jd_too_short"
    if "GEOGRAPHIC REJECT" in reason:
        return "geo_gate"
    if "required_years_" in reason:
        return "years_gate"
    if "industry_blocked" in reason:
        return "industry"
    if "title_blocked" in reason:
        return "title_blocked"
    return "other"

buckets = Counter(bucket(r) for r in rejects)

print("=== Built In scout log analysis ===")
print(f"Log: {log_path}")
print(f"[FOUND] count: {len(found)}")
print(f"[REJECT] count: {len(rejects)}")
print("\nReject buckets:")
for k, v in buckets.most_common():
    print(f"  {k}: {v}")

m = re.search(r"Total raw: (\d+) \| After dedup: (\d+) \| Saved: (\d+)", text)
if m:
    print(f"\nPipeline: raw={m.group(1)} dedup={m.group(2)} saved={m.group(3)}")

print("\n--- Saved / found (post card filters, pre Phase 3) ---")
for line in found[:25]:
    print(f"  + {line}")
if len(found) > 25:
    print(f"  ... +{len(found)-25} more")

geo = [r for r in rejects if "GEOGRAPHIC" in r]
years = [r for r in rejects if "required_years" in r]
if geo:
    print("\n--- Geographic rejects (Phase 3) ---")
    for r in geo[:12]:
        print(f"  - {r}")
if years:
    print("\n--- Years rejects (Phase 3) ---")
    for r in years[:12]:
        print(f"  - {r}")
