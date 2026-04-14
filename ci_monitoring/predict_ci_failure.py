from pathlib import Path

import joblib
import pandas as pd

MODEL_PATH = Path("ci_monitoring/models/best_ci_failure_model.joblib")
INPUT_PATH = Path("ci_monitoring/data/ci_runs_ml_dataset.csv")


def main():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Input dataset not found: {INPUT_PATH}")

    model = joblib.load(MODEL_PATH)
    df = pd.read_csv(INPUT_PATH)

    feature_cols = [c for c in df.columns if c not in ["target", "run_id"]]
    X = df[feature_cols].copy()

    df["predicted_target"] = model.predict(X)

    if hasattr(model.named_steps["model"], "predict_proba"):
        df["failure_probability"] = model.predict_proba(X)[:, 1]
    else:
        df["failure_probability"] = 0.0

    print(df[["run_id", "target", "predicted_target", "failure_probability"]])


if __name__ == "__main__":
    main()