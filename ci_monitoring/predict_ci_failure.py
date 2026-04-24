from pathlib import Path
import os
import sqlite3

import joblib
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

MODEL_PATH = Path("ci_monitoring/models/best_ci_failure_model.joblib")
INPUT_PATH = Path("ci_monitoring/data/ci_runs_ml_dataset.csv")
PREDICTIONS_PATH = Path("ci_monitoring/data/ci_model_predictions.csv")
DB_PATH = os.getenv("CI_SQLITE_PATH", "data/processed/ci_monitoring.db")


def risk_from_probability(probability: float) -> str:
    if probability >= 0.8:
        return "High"
    if probability >= 0.5:
        return "Medium"
    return "Low"


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


def main():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Input dataset not found: {INPUT_PATH}")

    model = joblib.load(MODEL_PATH)
    df = pd.read_csv(INPUT_PATH)

    if df.empty:
        print("Input dataset is empty. No predictions generated.")
        return

    feature_cols = [c for c in df.columns if c not in ["target", "run_id"]]
    X = df[feature_cols].copy()

    df["predicted_target"] = model.predict(X)

    if hasattr(model.named_steps["model"], "predict_proba"):
        df["failure_probability"] = model.predict_proba(X)[:, 1]
    else:
        df["failure_probability"] = 0.0

    df["risk_level"] = df["failure_probability"].apply(risk_from_probability)

    PREDICTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df[["run_id", "target", "predicted_target", "failure_probability", "risk_level"]].to_csv(
        PREDICTIONS_PATH,
        index=False,
    )

    conn = sqlite3.connect(DB_PATH)
    ensure_prediction_columns(conn)

    for _, row in df.iterrows():
        conn.execute(
            """
            UPDATE workflow_runs
            SET failure_probability = ?,
                predicted_target = ?,
                risk_level = ?
            WHERE run_id = ?
            """,
            (
                float(row["failure_probability"]),
                int(row["predicted_target"]),
                row["risk_level"],
                int(row["run_id"]),
            ),
        )

    conn.commit()
    conn.close()

    print("Predictions saved to CSV and SQLite successfully.")
    print(df[["run_id", "target", "predicted_target", "failure_probability", "risk_level"]])


if __name__ == "__main__":
    main()
