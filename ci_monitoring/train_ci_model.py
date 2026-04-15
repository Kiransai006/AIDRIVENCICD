import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

DATA_PATH = Path("ci_monitoring/data/ci_runs_ml_dataset.csv")
MODELS_DIR = Path("ci_monitoring/models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = MODELS_DIR / "best_ci_failure_model.joblib"
METRICS_PATH = MODELS_DIR / "model_metrics.json"
PREDICTIONS_PATH = Path("ci_monitoring/data/ci_model_predictions.csv")


def build_models():
    return {
        "logistic_regression": LogisticRegression(max_iter=1000),
        "random_forest": RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            random_state=42,
        ),
    }


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Missing dataset: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)

    if df.empty:
        raise ValueError("Dataset is empty.")

    if "target" not in df.columns:
        raise ValueError("Dataset must contain 'target' column.")

    class_counts = df["target"].value_counts().to_dict()
    print("Target distribution:", class_counts)

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

    # Safer split logic for small datasets
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

    # Final protection: if training set has one class, fall back to full dataset
    if len(set(y_train)) < 2:
        print("Training split has only one class. Falling back to full dataset.")
        X_train, X_test = X, X
        y_train, y_test = y, y

    models = build_models()
    results = {}

    best_name = None
    best_pipeline = None
    best_f1 = -1

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
                y_test, y_pred, zero_division=0, output_dict=True
            ),
        }

        if f1 > best_f1:
            best_f1 = f1
            best_name = model_name
            best_pipeline = pipeline

    if best_pipeline is None:
        raise RuntimeError("No model was trained.")

    joblib.dump(best_pipeline, MODEL_PATH)

    metrics_payload = {
        "best_model": best_name,
        "results": results,
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "feature_columns": feature_cols,
        "used_full_dataset_fallback": bool(len(X_train) == len(df) and len(X_test) == len(df)),
    }

    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2)

    df_out = df.copy()
    df_out["predicted_target"] = best_pipeline.predict(X)
    if hasattr(best_pipeline.named_steps["model"], "predict_proba"):
        df_out["failure_probability"] = best_pipeline.predict_proba(X)[:, 1]
    else:
        df_out["failure_probability"] = 0.0

    df_out.to_csv(PREDICTIONS_PATH, index=False)

    print(f"Best model: {best_name}")
    print(f"Saved model: {MODEL_PATH}")
    print(f"Saved metrics: {METRICS_PATH}")
    print(f"Saved predictions: {PREDICTIONS_PATH}")
    print("\nModel results:")
    for name, metrics in results.items():
        print(f"- {name}: accuracy={metrics['accuracy']}, f1={metrics['f1_score']}")


if __name__ == "__main__":
    main()