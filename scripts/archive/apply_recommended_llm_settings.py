# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Apply stage-specific local model routing to profiles/llm_settings."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "jobagent.sqlite"

RECOMMENDED = {
    "primaryProvider": "local",
    "localModel": "llama3.1:8b-instruct-q5_K_M",
    "localModelFit": "qwen2.5:7b-instruct-q4_K_M",
    # Same as primary — never fall to a weaker model that produces unusable drafts.
    "localFallbackModel": "llama3.1:8b-instruct-q5_K_M",
}


def main() -> None:
    conn = sqlite3.connect(DB)
    row = conn.execute("SELECT value FROM profiles WHERE key='llm_settings'").fetchone()
    settings = json.loads(row[0]) if row else {}
    settings.update(RECOMMENDED)
    settings.setdefault("localUrl", "http://localhost:11434")
    settings.pop("vram_threshold_mb", None)
    conn.execute(
        "UPDATE profiles SET value=? WHERE key='llm_settings'",
        (json.dumps(settings),),
    )
    conn.commit()
    conn.close()
    print(json.dumps(settings, indent=2))


if __name__ == "__main__":
    main()
