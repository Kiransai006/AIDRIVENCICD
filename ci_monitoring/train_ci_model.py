import json
import os
import sqlite3
from pathlib import Path

import joblib
import pandas as pd
from dotenv import load_dotenv
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

load_dotenv()

DB_PATH = os.getenv("CI_SQLITE_PATH", "data/processed/ci_monitoring.db")

DATA_PATH = Path("ci_monitoring/data/ci_runs_ml_dataset.csv")
PREDICTIONS_PATH = Path("ci_monitoring/data/ci_model_predictions.csv")
MODELS_DIR = Path("ci_monitoring/models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = MODELS_DIR / "best_ci_failure_model.joblib"
METRICS_PATH = MODELS_DIR / "model_metrics.json"


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


def risk_from_probability(probability: float) -> str:
    if probability >= 0.8:
        return "High"
    if probability >= 0.5:
        return "Medium"
    return "Low"


def build_dataset_from_sqlite():
    conn = sqlite3.connect(DB_PATH)

    query = """
    SELECT
        run_id,
        workflow_name,
        branch,
        actor_login,
        duration_seconds,
        conclusion
    FROM workflow_runs
    WHERE conclusion IN ('success', 'failure')
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        raise ValueError("No completed success/failure CI runs found in SQLite.")

    df["target"] = df["conclusion"].apply(lambda x: 1 if x == "failure" else 0)

    df = df[
        [
            "run_id",
            "workflow_name",
            "branch",
            "actor_login",
            "duration_seconds",
            "target",
        ]
    ]

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA_PATH, index=False)

    return df


def build_models():
    return {
        "logistic_regression": LogisticRegression(max_iter=1000),
        "random_forest": RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            random_state=42,
        ),
    }


def save_predictions_to_sqlite(df_out):
    conn = sqlite3.connect(DB_PATH)
    ensure_prediction_columns(conn)

    updated_count = 0

    for _, row in df_out.iterrows():
        probability = float(row["failure_probability"])
        prediction = int(row["predicted_target"])
        risk_level = risk_from_probability(probability)

        cursor = conn.execute(
            """
            UPDATE workflow_runs
            SET failure_probability = ?,
                predicted_target = ?,
                risk_level = ?
            WHERE run_id = ?
            """,
            (
                probability,
                prediction,
                risk_level,
                int(row["run_id"]),
            ),
        )

        updated_count += cursor.rowcount

    conn.commit()
    conn.close()

    print(f"Updated SQLite predictions for {updated_count} workflow runs.")


def main():
    df = build_dataset_from_sqlite()

    if df["target"].nunique() < 2:
        raise ValueError("Need both success and failure rows before training.")

    feature_cols = [c for c in df.columns if c not in ["target", "run_id"]]
    X = df[feature_cols].copy()
    y = df["target"].astype(int)

    categorical_cols = X.select_dtypes(include=["object"]).columns.tolist()
    numeric_cols = [c for c in X.columns if c not in categorical_cols]

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                    ]
                ),
                numeric_cols,
            ),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_cols,
            ),
        ]
    )

    min_class_count = y.value_counts().min()

    if len(df) < 6 or min_class_count < 2:
        print("Dataset too small for train/test split. Training on full dataset.")
        X_train, X_test = X, X
        y_train, y_test = y, y
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.3,
            random_state=42,
            stratify=y,
        )

    models = build_models()

    best_name = None
    best_pipeline = None
    best_f1 = -1
    results = {}

    for model_name, model in models.items():
        pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("model", model),
            ]
        )

        pipeline.fit(X_train, y_train)
        y_pred = pipeline.predict(X_test)

        acc = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, zero_division=0)

        results[model_name] = {
            "accuracy": round(float(acc), 4),
            "f1_score": round(float(f1), 4),
            "classification_report": classification_report(
                y_test,
                y_pred,
                zero_division=0,
                output_dict=True,
            ),
        }

        if f1 > best_f1:
            best_f1 = f1
            best_name = model_name
            best_pipeline = pipeline

    if best_pipeline is None:
        raise RuntimeError("No model was trained.")

    joblib.dump(best_pipeline, MODEL_PATH)

    df_out = df.copy()
    df_out["predicted_target"] = best_pipeline.predict(X)

    if hasattr(best_pipeline.named_steps["model"], "predict_proba"):
        df_out["failure_probability"] = best_pipeline.predict_proba(X)[:, 1]
    else:
        df_out["failure_probability"] = 0.0

    df_out["risk_level"] = df_out["failure_probability"].apply(risk_from_probability)

    PREDICTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(PREDICTIONS_PATH, index=False)

    save_predictions_to_sqlite(df_out)

    metrics_payload = {
        "best_model": best_name,
        "results": results,
        "rows_used": int(len(df)),
        "feature_columns": feature_cols,
    }

    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2)

    print(f"Best model: {best_name}")
    print(f"Saved model: {MODEL_PATH}")
    print(f"Saved metrics: {METRICS_PATH}")
    print(f"Saved predictions: {PREDICTIONS_PATH}")


if __name__ == "__main__":
    main()
