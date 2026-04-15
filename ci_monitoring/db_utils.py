import os
import sqlite3
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("CI_SQLITE_PATH", "data/processed/ci_monitoring.db")
PREDICTIONS_PATH = "ci_monitoring/data/ci_model_predictions.csv"


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
        LIMIT 20
    """).fetchall()

    recent_runs = []
    for row in rows:
        recent_runs.append({
            "run_id": str(row["run_id"]),
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

    # Merge ML predictions if available
    if os.path.exists(PREDICTIONS_PATH):
        pred_df = pd.read_csv(PREDICTIONS_PATH)
        pred_df["run_id"] = pred_df["run_id"].astype(str)

        pred_map = {}
        for _, row in pred_df.iterrows():
            pred_map[row["run_id"]] = {
                "predicted_target": int(row["predicted_target"]),
                "failure_probability": float(row["failure_probability"]),
            }

        for run in recent_runs:
            pred = pred_map.get(run["run_id"])
            if pred:
                run["predicted_target"] = pred["predicted_target"]
                run["failure_probability"] = round(pred["failure_probability"] * 100, 2)
                if pred["failure_probability"] >= 0.8:
                    run["risk_label"] = "High"
                elif pred["failure_probability"] >= 0.5:
                    run["risk_label"] = "Medium"
                else:
                    run["risk_label"] = "Low"
            else:
                run["predicted_target"] = None
                run["failure_probability"] = None
                run["risk_label"] = "N/A"
    else:
        for run in recent_runs:
            run["predicted_target"] = None
            run["failure_probability"] = None
            run["risk_label"] = "N/A"

    return {
        "total_runs": total_runs,
        "success_runs": success_runs,
        "failure_runs": failure_runs,
        "avg_duration": avg_duration,
        "recent_runs": recent_runs,
    }