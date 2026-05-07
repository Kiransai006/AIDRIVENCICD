import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("CI_SQLITE_PATH", "data/processed/ci_monitoring.db")


def ensure_remediation_columns(conn):
    existing_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(workflow_runs)").fetchall()
    }

    if "remediation_status" not in existing_cols:
        conn.execute("ALTER TABLE workflow_runs ADD COLUMN remediation_status TEXT")

    if "remediation_message" not in existing_cols:
        conn.execute("ALTER TABLE workflow_runs ADD COLUMN remediation_message TEXT")

    if "remediation_created_at" not in existing_cols:
        conn.execute("ALTER TABLE workflow_runs ADD COLUMN remediation_created_at TEXT")

    conn.commit()


def build_remediation_message(row):
    workflow = row["workflow_name"] or "Unknown workflow"
    branch = row["branch"] or "Unknown branch"
    conclusion = row["conclusion"] or "unknown"
    risk_level = row["risk_level"] or "N/A"
    duration = row["duration_seconds"]
    probability = row["failure_probability"]

    probability_text = (
        f"{round(float(probability) * 100, 2)}%"
        if probability is not None
        else "N/A"
    )

    suggestions = [
        f"High-risk CI/CD run detected for workflow: {workflow}",
        f"Branch: {branch}",
        f"Current conclusion: {conclusion}",
        f"ML failure probability: {probability_text}",
        f"ML risk level: {risk_level}",
        "",
        "Recommended remediation steps:",
        "1. Open the GitHub Actions run and review the failed job logs.",
        "2. Check recent commits related to tests, dependencies, environment variables, and deployment files.",
        "3. Run the test suite locally using pytest to reproduce the failure.",
        "4. Verify Render/GitHub environment variables and secrets.",
        "5. Check requirements.txt for missing dependencies.",
        "6. Re-run the GitHub Actions workflow after applying fixes.",
    ]

    if conclusion == "failure":
        suggestions.append(
            "7. Since the run actually failed, prioritise the failed test cases and deployment errors."
        )

    if duration and float(duration) > 100:
        suggestions.append(
            "8. The workflow duration is high, so check for timeout, slow tests, or long dependency installation."
        )

    if risk_level == "High":
        suggestions.append(
            "9. Mark this run for immediate developer review before production deployment."
        )

    return "\n".join(suggestions)


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    ensure_remediation_columns(conn)

    rows = conn.execute(
        """
        SELECT
            run_id,
            workflow_name,
            conclusion,
            branch,
            duration_seconds,
            failure_probability,
            predicted_target,
            risk_level
        FROM workflow_runs
        WHERE risk_level = 'High'
           OR failure_probability >= 0.8
           OR conclusion = 'failure'
        ORDER BY created_at DESC
        """
    ).fetchall()

    updated = 0

    for row in rows:
        message = build_remediation_message(row)

        conn.execute(
            """
            UPDATE workflow_runs
            SET remediation_status = ?,
                remediation_message = ?,
                remediation_created_at = ?
            WHERE run_id = ?
            """,
            (
                "Generated",
                message,
                datetime.utcnow().isoformat(),
                row["run_id"],
            ),
        )

        updated += 1

    conn.commit()
    conn.close()

    print(f"Auto remediation generated for {updated} workflow runs.")


if __name__ == "__main__":
    main()
