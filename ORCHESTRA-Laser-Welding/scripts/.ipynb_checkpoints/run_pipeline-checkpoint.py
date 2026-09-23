from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orchestra_laser.config import Paths, load_config
from orchestra_laser.experiments import (
    add_scheduling_context,
    apply_orchestra_review,
    run_ablation_study,
    run_baseline_comparison,
    run_sensitivity_analysis,
)
from orchestra_laser.predictive_agent import PredictiveAgent
from orchestra_laser.preprocessing import clean_laser_welding_data, load_or_create_dataset, train_test_split
from orchestra_laser.urgency import add_maintenance_urgency


def main() -> None:
    paths = Paths()
    paths.ensure()
    config = load_config(paths.config)

    print("ORCHESTRA laser welding pipeline")
    print(f"Project root: {paths.root}")

    df = load_or_create_dataset(config)
    df = clean_laser_welding_data(df, config["feature_columns"])
    df = add_maintenance_urgency(df)
    df = add_scheduling_context(df, seed=int(config["random_seed"]))

    train_df, test_df = train_test_split(
        df,
        train_fraction=float(config["train_fraction"]),
        seed=int(config["random_seed"]),
    )

    agent = PredictiveAgent(config["feature_columns"])
    agent.fit(train_df)
    metrics = agent.evaluate(test_df)
    predictions = agent.predict(test_df)
    test_df = apply_orchestra_review(test_df, predictions, config)

    processed_path = paths.processed_data / "laser_welding_orchestra_dataset.csv"
    test_df.to_csv(processed_path, index=False)

    agent.save_report(paths.models / "predictive_agent_report.json", metrics)

    baseline_table = run_baseline_comparison(test_df, config)
    ablation_table = run_ablation_study(test_df, config)
    sensitivity_table = run_sensitivity_analysis(test_df, config)

    baseline_table.to_csv(paths.tables / "baseline_comparison.csv", index=False)
    ablation_table.to_csv(paths.tables / "ablation_study.csv", index=False)
    sensitivity_table.to_csv(paths.tables / "sensitivity_analysis.csv", index=False)

    summary = {
        "predictive_agent": {
            "model": agent.model_name,
            "mae": metrics.mae,
            "rmse": metrics.rmse,
            "r2": metrics.r2,
        },
        "rows_train": len(train_df),
        "rows_test": len(test_df),
        "human_review_rate": float(test_df["human_review_triggered"].mean()),
        "human_override_rate": float(test_df["human_override"].mean()),
        "outputs": {
            "processed_dataset": str(processed_path),
            "baseline_comparison": str(paths.tables / "baseline_comparison.csv"),
            "ablation_study": str(paths.tables / "ablation_study.csv"),
            "sensitivity_analysis": str(paths.tables / "sensitivity_analysis.csv"),
        },
    }
    (paths.logs / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

