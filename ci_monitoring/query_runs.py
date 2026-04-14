import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()
db_path = os.getenv("CI_SQLITE_PATH", "data/processed/ci_monitoring.db")

conn = sqlite3.connect(db_path)
rows = conn.execute("""
SELECT run_id, status, conclusion, branch, actor_login, created_at
FROM workflow_runs
ORDER BY created_at DESC
LIMIT 10
""").fetchall()
conn.close()

print(f"Rows found: {len(rows)}")
for row in rows:
    print(row)