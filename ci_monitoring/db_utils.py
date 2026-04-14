import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("CI_SQLITE_PATH", "data/processed/ci_monitoring.db")


def get_ci_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_ci_summary():
    conn = get_ci_connection()

    total_runs = conn.execute("SELECT COUNT(*) AS count FROM workflow_runs").fetchone()["count"]
    success_runs = conn.execute(
        "SELECT COUNT(*) AS count FROM workflow_runs WHERE conclusion = 'success'"
    ).fetchone()["count"]
    failure_runs = conn.execute(
        "SELECT COUNT(*) AS count FROM workflow_runs WHERE conclusion = 'failure'"
    ).fetchone()["count"]

    avg_duration_row = conn.execute(
        "SELECT AVG(duration_seconds) AS avg_duration FROM workflow_runs WHERE duration_seconds IS NOT NULL"
    ).fetchone()
    avg_duration = round(avg_duration_row["avg_duration"], 2) if avg_duration_row and avg_duration_row["avg_duration"] else 0

    rows = conn.execute("""
        SELECT
            run_id,
            workflow_name,
            status,
            conclusion,
            branch,
            actor_login,
            created_at,
            duration_seconds,
            html_url
        FROM workflow_runs
        ORDER BY created_at DESC
        LIMIT 10
    """).fetchall()

    recent_runs = []
    for row in rows:
        recent_runs.append({
            "run_id": row["run_id"],
            "workflow_name": row["workflow_name"],
            "status": row["status"],
            "conclusion": row["conclusion"],
            "branch": row["branch"],
            "actor_login": row["actor_login"],
            "created_at": row["created_at"],
            "duration_seconds": row["duration_seconds"],
            "html_url": row["html_url"],
        })

    conn.close()

    return {
        "total_runs": total_runs,
        "success_runs": success_runs,
        "failure_runs": failure_runs,
        "avg_duration": avg_duration,
        "recent_runs": recent_runs,
    }