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
        print("Gmail credentials not configured — skipping email alert.")
        return
 
    try:
        app_password = GMAIL_APP_PASSWORD.replace(" ", "").strip()
 
        message = MIMEMultipart()
        message["From"] = GMAIL_SENDER
        message["To"] = ALERT_RECEIVER
        message["Subject"] = subject
 
        message.attach(MIMEText(body, "plain"))
 
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, app_password)
            server.send_message(message)
 
        print(f"Email alert sent to {ALERT_RECEIVER}")
 
    except Exception as e:
        print(f"Email alert skipped — {e}")
        return
 
 
def build_email_body(row):
    probability = row["failure_probability"]
 
    probability_text = (
        f"{round(float(probability) * 100, 2)}%"
        if probability is not None
        else "N/A"
    )
 
    prediction_text = (
        "Failure Predicted"
        if row["predicted_target"] == 1
        else "Success Predicted"
        if row["predicted_target"] == 0
        else "N/A"
    )
 
    return f"""
CI/CD Monitoring Alert
 
A CI/CD workflow run requires attention.
 
Workflow: {row["workflow_name"]}
Run ID: {row["run_id"]}
Branch: {row["branch"]}
Actor: {row["actor_login"]}
Conclusion: {row["conclusion"]}
Duration: {row["duration_seconds"]} seconds
 
ML Prediction: {prediction_text}
ML Failure Probability: {probability_text}
ML Risk Level: {row["risk_level"] or "N/A"}
 
Auto Remediation Status: {row["remediation_status"] or "N/A"}
 
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
            predicted_target,
            risk_level,
            remediation_status,
            remediation_message,
            html_url
        FROM workflow_runs
        WHERE
            (
                risk_level IN ('High', 'Medium')
                OR conclusion = 'failure'
                OR predicted_target = 1
                OR failure_probability >= 0.5
                OR remediation_status = 'Generated'
            )
            AND COALESCE(email_alert_sent, 0) = 0
        ORDER BY created_at DESC
        LIMIT 10
        """
    ).fetchall()
 
    sent_count = 0
 
    print(f"Rows eligible for Gmail alert: {len(rows)}")
 
    for row in rows:
        subject = (
            f"CI/CD Alert: {row['workflow_name']} - "
            f"{row['risk_level'] or row['conclusion'] or 'Attention Required'}"
        )
 
        body = build_email_body(row)
 
        try:
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
 
        except Exception as e:
            print(f"Email skipped for run {row['run_id']}: {e}")
            continue
 
    conn.commit()
    conn.close()
 
    print(f"Gmail alerts sent: {sent_count}")
 
 
if __name__ == "__main__":
    main()