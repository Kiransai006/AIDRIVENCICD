import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("CI_SQLITE_PATH", "data/processed/ci_monitoring.db")


def get_ci_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_dashboard_columns(conn):
    existing_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(workflow_runs)").fetchall()
    }

    columns = {
        "failure_probability": "REAL",
        "predicted_target": "INTEGER",
        "risk_level": "TEXT",
        "remediation_status": "TEXT",
        "remediation_message": "TEXT",
        "remediation_created_at": "TEXT",
    }

    for col, col_type in columns.items():
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE workflow_runs ADD COLUMN {col} {col_type}")

    conn.commit()


def risk_label_from_probability(probability):
    if probability is None:
        return "N/A"

    probability = float(probability)

    if probability >= 0.8:
        return "High"
    if probability >= 0.5:
        return "Medium"
    return "Low"


def get_ci_summary():
    conn = get_ci_connection()
    ensure_dashboard_columns(conn)

    total_runs = conn.execute(
        "SELECT COUNT(*) AS count FROM workflow_runs"
    ).fetchone()["count"]

    success_runs = conn.execute(
        "SELECT COUNT(*) AS count FROM workflow_runs WHERE conclusion = 'success'"
    ).fetchone()["count"]

    failure_runs = conn.execute(
        "SELECT COUNT(*) AS count FROM workflow_runs WHERE conclusion = 'failure'"
    ).fetchone()["count"]

    avg_duration_row = conn.execute(
        """
        SELECT AVG(duration_seconds) AS avg_duration
        FROM workflow_runs
        WHERE duration_seconds IS NOT NULL
        """
    ).fetchone()

    avg_duration = (
        round(avg_duration_row["avg_duration"], 2)
        if avg_duration_row and avg_duration_row["avg_duration"] is not None
        else 0
    )

    rows = conn.execute(
        """
        SELECT
            run_id,
            workflow_name,
            status,
            conclusion,
            branch,
            actor_login,
            created_at,
            duration_seconds,
            html_url,
            failure_probability,
            predicted_target,
            risk_level,
            remediation_status,
            remediation_message,
            remediation_created_at
        FROM workflow_runs
        ORDER BY created_at DESC
        LIMIT 20
        """
    ).fetchall()

    recent_runs = []

    for row in rows:
        raw_probability = row["failure_probability"]

        if raw_probability is not None:
            probability_display = round(float(raw_probability) * 100, 2)
        else:
            probability_display = None

        risk_label = row["risk_level"]
        if not risk_label or risk_label == "N/A":
            risk_label = risk_label_from_probability(raw_probability)

        recent_runs.append(
            {
                "run_id": str(row["run_id"]),
                "workflow_name": row["workflow_name"],
                "status": row["status"],
                "conclusion": row["conclusion"],
                "branch": row["branch"],
                "actor_login": row["actor_login"],
                "created_at": row["created_at"],
                "duration_seconds": row["duration_seconds"],
                "html_url": row["html_url"],
                "predicted_target": row["predicted_target"],
                "failure_probability": probability_display,
                "risk_label": risk_label,
                "remediation_status": row["remediation_status"],
                "remediation_message": row["remediation_message"],
                "remediation_created_at": row["remediation_created_at"],
            }
        )

    conn.close()

    return {
        "total_runs": total_runs,
        "success_runs": success_runs,
        "failure_runs": failure_runs,
        "avg_duration": avg_duration,
        "recent_runs": recent_runs,
    }
