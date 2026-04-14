import os
import sqlite3
import csv
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("CI_SQLITE_PATH", "data/processed/ci_monitoring.db")
OUTPUT_PATH = Path("ci_monitoring/data/ci_runs_raw.csv")


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT
            run_id,
            workflow_name,
            status,
            conclusion,
            branch,
            actor_login,
            created_at,
            duration_seconds
        FROM workflow_runs
        ORDER BY created_at ASC
    """).fetchall()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_id",
            "workflow_name",
            "status",
            "conclusion",
            "branch",
            "actor_login",
            "created_at",
            "duration_seconds",
        ])
        for row in rows:
            writer.writerow([
                row["run_id"],
                row["workflow_name"],
                row["status"],
                row["conclusion"],
                row["branch"],
                row["actor_login"],
                row["created_at"],
                row["duration_seconds"],
            ])

    conn.close()
    print(f"Saved raw CSV: {OUTPUT_PATH}")
    print(f"Rows: {len(rows)}")


if __name__ == "__main__":
    main()