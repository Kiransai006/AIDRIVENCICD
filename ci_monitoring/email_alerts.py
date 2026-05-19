import os
import sqlite3
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("CI_SQLITE_PATH", "data/processed/ci_monitoring.db")

GMAIL_SENDER = os.getenv("GMAIL_SENDER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
ALERT_RECEIVER = os.getenv("ALERT_RECEIVER")


def ensure_alert_columns(conn):
    existing_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(workflow_runs)").fetchall()
    }

    columns = {
        "email_alert_sent": "INTEGER DEFAULT 0",
        "email_alert_sent_at": "TEXT",
    }

    for col_name, col_type in columns.items():
        if col_name not in existing_cols:
            conn.execute(f"ALTER TABLE workflow_runs ADD COLUMN {col_name} {col_type}")

    conn.commit()


def send_email_alert(subject, body):
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD or not ALERT_RECEIVER:
        raise ValueError(
            "Missing Gmail alert environment variables: "
            "GMAIL_SENDER, GMAIL_APP_PASSWORD, ALERT_RECEIVER"
        )

    message = MIMEMultipart()
    message["From"] = GMAIL_SENDER
    message["To"] = ALERT_RECEIVER
    message["Subject"] = subject

    message.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
        server.send_message(message)


def build_email_body(row):
    probability = row["failure_probability"]

    probability_text = (
        f"{round(float(probability) * 100, 2)}%"
        if probability is not None
        else "N/A"
    )

    return f"""
CI/CD Monitoring Alert

A high-risk or failed CI/CD workflow run has been detected.

Workflow: {row["workflow_name"]}
Run ID: {row["run_id"]}
Branch: {row["branch"]}
Actor: {row["actor_login"]}
Conclusion: {row["conclusion"]}
Duration: {row["duration_seconds"]} seconds

ML Failure Probability: {probability_text}
ML Risk Level: {row["risk_level"] or "N/A"}

Suggested Auto Remediation:
{row["remediation_message"] or "No remediation message available."}

GitHub Actions Run:
{row["html_url"]}

This alert was generated automatically by the CloudCart AI-driven CI/CD monitoring system.
"""


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    ensure_alert_columns(conn)

    rows = conn.execute(
        """
        SELECT
            run_id,
            workflow_name,
            conclusion,
            branch,
            actor_login,
            duration_seconds,
            failure_probability,
            risk_level,
            remediation_message,
            html_url
        FROM workflow_runs
        WHERE
            (
                risk_level = 'High'
                OR conclusion = 'failure'
                OR failure_probability >= 0.8
            )
            AND COALESCE(email_alert_sent, 0) = 0
        ORDER BY created_at DESC
        LIMIT 10
        """
    ).fetchall()

    sent_count = 0

    for row in rows:
        subject = f"CI/CD Alert: {row['workflow_name']} - {row['risk_level'] or row['conclusion']}"

        body = build_email_body(row)

        send_email_alert(subject, body)

        conn.execute(
            """
            UPDATE workflow_runs
            SET email_alert_sent = 1,
                email_alert_sent_at = ?
            WHERE run_id = ?
            """,
            (
                datetime.utcnow().isoformat(),
                row["run_id"],
            ),
        )

        sent_count += 1

    conn.commit()
    conn.close()

    print(f"Gmail alerts sent: {sent_count}")


if __name__ == "__main__":
    main()
