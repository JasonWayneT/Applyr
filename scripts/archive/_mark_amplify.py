# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import sqlite3
from pathlib import Path
c = sqlite3.connect(Path('data/jobagent.sqlite'))
c.execute("UPDATE jobs SET status='Drafted' WHERE company='Amplify'")
c.commit()
print('Amplify -> Drafted')
c.close()
