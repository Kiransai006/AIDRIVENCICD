import pandas as pd
from pathlib import Path

INPUT_PATH = Path("ci_monitoring/data/ci_runs_raw.csv")
FEATURES_PATH = Path("ci_monitoring/data/ci_runs_features.csv")
ML_PATH = Path("ci_monitoring/data/ci_runs_ml_dataset.csv")


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Missing file: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH)

    if df.empty:
        raise ValueError("No CI workflow runs found in raw CSV.")

    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df.sort_values("created_at").reset_index(drop=True)

    df["duration_seconds"] = pd.to_numeric(df["duration_seconds"], errors="coerce").fillna(0)

    # Basic labels
    df["target"] = (df["conclusion"] == "failure").astype(int)
    df["is_success"] = (df["conclusion"] == "success").astype(int)
    df["is_failure"] = (df["conclusion"] == "failure").astype(int)
    df["is_completed"] = (df["status"] == "completed").astype(int)

    # Branch flags
    df["is_main_branch"] = (df["branch"] == "main").astype(int)

    # History features
    df["previous_failures_last_3"] = (
        df["target"].shift(1).rolling(window=3, min_periods=1).sum().fillna(0)
    )
    df["previous_failures_last_5"] = (
        df["target"].shift(1).rolling(window=5, min_periods=1).sum().fillna(0)
    )

    # Failure streak
    streaks = []
    streak = 0
    for value in df["target"]:
        streaks.append(streak)
        if value == 1:
            streak += 1
        else:
            streak = 0
    df["failure_streak_before_run"] = streaks

    # Time features
    df["run_hour"] = df["created_at"].dt.hour.fillna(0).astype(int)
    df["run_day_of_week"] = df["created_at"].dt.dayofweek.fillna(0).astype(int)

    # Text cleanup
    df["workflow_name"] = df["workflow_name"].fillna("unknown")
    df["branch"] = df["branch"].fillna("unknown")
    df["actor_login"] = df["actor_login"].fillna("unknown")
    df["status"] = df["status"].fillna("unknown")
    df["conclusion"] = df["conclusion"].fillna("unknown")

    # Save full features
    FEATURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(FEATURES_PATH, index=False)

    # Final ML dataset
    ml_df = df[
        [
            "run_id",
            "workflow_name",
            "branch",
            "actor_login",
            "status",
            "duration_seconds",
            "is_completed",
            "is_main_branch",
            "previous_failures_last_3",
            "previous_failures_last_5",
            "failure_streak_before_run",
            "run_hour",
            "run_day_of_week",
            "target",
        ]
    ].copy()

    ml_df.to_csv(ML_PATH, index=False)

    print(f"Saved features: {FEATURES_PATH}")
    print(f"Saved ML dataset: {ML_PATH}")
    print(f"Rows: {len(ml_df)}")
    print("\nTarget distribution:")
    print(ml_df["target"].value_counts())


if __name__ == "__main__":
    main()