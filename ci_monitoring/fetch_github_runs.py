import os
import sqlite3
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

OWNER = os.getenv("GITHUB_OWNER")
REPO = os.getenv("GITHUB_REPO")
TOKEN = os.getenv("GITHUB_TOKEN")
DB_PATH = os.getenv("CI_SQLITE_PATH", "data/processed/ci_monitoring.db")

API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id INTEGER PRIMARY KEY,
    name TEXT,
    display_title TEXT,
    status TEXT,
    conclusion TEXT,
    event TEXT,
    branch TEXT,
    workflow_id INTEGER,
    workflow_name TEXT,
    actor_login TEXT,
    head_sha TEXT,
    html_url TEXT,
    created_at TEXT,
    updated_at TEXT,
    run_started_at TEXT,
    duration_seconds REAL,
    failure_probability REAL,
    predicted_target INTEGER,
    risk_level TEXT,
    source TEXT DEFAULT 'github_actions',
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

UPSERT_SQL = """
INSERT INTO workflow_runs (
    run_id, name, display_title, status, conclusion, event, branch,
    workflow_id, workflow_name, actor_login, head_sha, html_url,
    created_at, updated_at, run_started_at, duration_seconds, source
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(run_id) DO UPDATE SET
    name = excluded.name,
    display_title = excluded.display_title,
    status = excluded.status,
    conclusion = excluded.conclusion,
    event = excluded.event,
    branch = excluded.branch,
    workflow_id = excluded.workflow_id,
    workflow_name = excluded.workflow_name,
    actor_login = excluded.actor_login,
    head_sha = excluded.head_sha,
    html_url = excluded.html_url,
    created_at = excluded.created_at,
    updated_at = excluded.updated_at,
    run_started_at = excluded.run_started_at,
    duration_seconds = excluded.duration_seconds,
    source = excluded.source
;
"""


def ensure_prediction_columns(conn):
    existing_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(workflow_runs)").fetchall()
    }

    if "failure_probability" not in existing_cols:
        conn.execute("ALTER TABLE workflow_runs ADD COLUMN failure_probability REAL")

    if "predicted_target" not in existing_cols:
        conn.execute("ALTER TABLE workflow_runs ADD COLUMN predicted_target INTEGER")

    if "risk_level" not in existing_cols:
        conn.execute("ALTER TABLE workflow_runs ADD COLUMN risk_level TEXT")

    conn.commit()


def parse_duration_seconds(started_at: str | None, updated_at: str | None) -> float | None:
    if not started_at or not updated_at:
        return None

    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        return round((end - start).total_seconds(), 2)
    except Exception:
        return None


def fetch_runs(max_pages=5):
    missing = []
    if not OWNER:
        missing.append("GITHUB_OWNER")
    if not REPO:
        missing.append("GITHUB_REPO")
    if not TOKEN:
        missing.append("GITHUB_TOKEN")

    if missing:
        raise ValueError(f"Missing environment variables: {', '.join(missing)}")

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    all_runs = []
    per_page = 100

    for page in range(1, max_pages + 1):
        response = requests.get(
            API_URL,
            headers=headers,
            params={"per_page": per_page, "page": page},
            timeout=30,
        )
        response.raise_for_status()

        runs = response.json().get("workflow_runs", [])

        if not runs:
            break

        all_runs.extend(runs)

        if len(runs) < per_page:
            break

    return all_runs


def save_runs(runs):
    db_file = Path(DB_PATH)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute(CREATE_TABLE_SQL)
    ensure_prediction_columns(conn)

    for run in runs:
        duration = parse_duration_seconds(run.get("run_started_at"), run.get("updated_at"))

        values = (
            run.get("id"),
            run.get("name"),
            run.get("display_title"),
            run.get("status"),
            run.get("conclusion"),
            run.get("event"),
            run.get("head_branch"),
            run.get("workflow_id"),
            run.get("name"),
            (run.get("actor") or {}).get("login"),
            run.get("head_sha"),
            run.get("html_url"),
            run.get("created_at"),
            run.get("updated_at"),
            run.get("run_started_at"),
            duration,
            "github_actions",
        )

        conn.execute(UPSERT_SQL, values)

    conn.commit()
    conn.close()


def main():
    try:
        print(f"OWNER={OWNER}, REPO={REPO}, DB_PATH={DB_PATH}")
        runs = fetch_runs(max_pages=5)
        print(f"Fetched {len(runs)} runs from GitHub")
        save_runs(runs)
        print(f"Saved {len(runs)} workflow runs into {DB_PATH}")
    except Exception as e:
        print(f"ERROR in fetch_github_runs.py: {e}")
        raise


if __name__ == "__main__":
    main()
