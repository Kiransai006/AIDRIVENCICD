import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

GMAIL_SENDER = os.getenv("GMAIL_SENDER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
ALERT_RECEIVER = os.getenv("ALERT_RECEIVER")


def main():
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD or not ALERT_RECEIVER:
        raise ValueError("Missing GMAIL_SENDER, GMAIL_APP_PASSWORD, or ALERT_RECEIVER")

    subject = "Test Alert: CloudCart CI/CD Gmail Integration"

    body = """
Hello,

This is a test email from the CloudCart AI-driven CI/CD Monitoring System.

If you received this email, Gmail alert integration is working correctly.

Test Flow:
CI Monitoring → ML Prediction → Auto Remediation → Gmail Alert

Regards,
CloudCart CI/CD Monitoring System
"""

    msg = MIMEMultipart()
    msg["From"] = GMAIL_SENDER
    msg["To"] = ALERT_RECEIVER
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
        server.send_message(msg)

    print("Test Gmail alert sent successfully.")


if __name__ == "__main__":
    main()
