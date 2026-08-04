# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from generate_cheat_sheet import generate_cheat_sheet

for co in ["ladders", "tillster", "guidehealth", "hackajob", "ottimate", "ukg"]:
    try:
        generate_cheat_sheet(co)
        print(f"cheat {co} ok")
    except Exception as exc:
        print(f"cheat {co} FAIL: {exc}")
