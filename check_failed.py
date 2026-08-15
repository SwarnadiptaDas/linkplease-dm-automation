import sqlite3

c = sqlite3.connect('linkplease.db')
for row in c.execute('select id, status, comment_id, error_count from dm_tasks where status="failed"'):
    print(row)
