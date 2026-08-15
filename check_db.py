import sqlite3
from datetime import datetime, timezone

c = sqlite3.connect('linkplease.db')
print("Total queued:", c.execute('select count(*) from dm_tasks where status="queued"').fetchone()[0])

now = datetime.now(timezone.utc).replace(tzinfo=None)
print("Now:", now)

res = c.execute('select next_attempt_at from dm_tasks where status="queued" limit 5').fetchall()
print("Next attempt times:", res)

# Check how many are eligible
count = 0
for row in c.execute('select next_attempt_at from dm_tasks where status="queued"'):
    dt_str = row[0]
    dt = datetime.fromisoformat(dt_str)
    if dt <= now:
        count += 1
print("Eligible in Python logic:", count)

# Check SQLite comparison
db_eligible = c.execute('select count(*) from dm_tasks where status="queued" and next_attempt_at <= ?', (now.isoformat(' '),)).fetchone()[0]
print("Eligible in DB query logic:", db_eligible)
