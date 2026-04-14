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
    source TEXT DEFAULT 'github_actions',
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

UPSERT_SQL = """
INSERT OR REPLACE INTO workflow_runs (
    run_id, name, display_title, status, conclusion, event, branch,
    workflow_id, workflow_name, actor_login, head_sha, html_url,
    created_at, updated_at, run_started_at, duration_seconds, source
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

def parse_duration_seconds(started_at: str | None, updated_at: str | None) -> float | None:
    if not started_at or not updated_at:
        return None
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        return round((end - start).total_seconds(), 2)
    except Exception:
        return None

def fetch_runs():
    if not OWNER or not REPO or not TOKEN:
        raise ValueError("Missing GITHUB_OWNER, GITHUB_REPO, or GITHUB_TOKEN in .env")

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {TOKEN}",
        "X-GitHub-Api-Version": "2026-03-10",
    }

    response = requests.get(API_URL, headers=headers, params={"per_page": 100}, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data.get("workflow_runs", [])

def save_runs(runs):
    db_file = Path(DB_PATH)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute(CREATE_TABLE_SQL)

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
    runs = fetch_runs()
    save_runs(runs)
    print(f"Saved {len(runs)} workflow runs into {DB_PATH}")

if __name__ == "__main__":
    main()