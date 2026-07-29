import sqlite3
from pathlib import Path
c = sqlite3.connect(Path('data/jobagent.sqlite'))
c.execute("UPDATE jobs SET status='Drafted' WHERE company='Amplify'")
c.commit()
print('Amplify -> Drafted')
c.close()
