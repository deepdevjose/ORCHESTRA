from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orchestra_laser.config import Paths, load_config
from orchestra_laser.experiments import add_scheduling_context, apply_orchestra_review
from orchestra_laser.ppo_agent import GymLaserMaintenanceEnv, evaluate_ppo_model
from orchestra_laser.predictive_agent import PredictiveAgent
from orchestra_laser.preprocessing import clean_laser_welding_data, load_or_create_dataset, train_test_split
from orchestra_laser.urgency import add_maintenance_urgency


def build_orchestra_dataset(config: dict):
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
    predictions = agent.predict(test_df)
    test_df = apply_orchestra_review(test_df, predictions, config)
    return test_df, agent.model_name


def main() -> None:
    try:
        from stable_baselines3 import PPO
    except Exception as exc:
        raise SystemExit(
            "Stable-Baselines3 PPO is not available. Install with:\n"
            "python -m pip install gymnasium stable-baselines3\n"
            f"Original error: {exc}"
        )

    paths = Paths()
    paths.ensure()
    config = load_config(paths.config)
    data, predictive_model_name = build_orchestra_dataset(config)

    env = GymLaserMaintenanceEnv(
        data=data,
        reward_weights=config["reward_weights"],
        episode_length=int(config["episode_length"]),
        seed=int(config["random_seed"]),
    )

    model = PPO(
        "MlpPolicy",
        env,
        verbose=0,
        seed=int(config["random_seed"]),
        n_steps=128,
        batch_size=128,
        learning_rate=0.00025,
        gamma=0.98,
        ent_coef=0.02,
    )
    model.learn(total_timesteps=50000)

    model_path = paths.models / "ppo_laser_maintenance_scheduler.zip"
    model.save(model_path)

    metrics = evaluate_ppo_model(model, env, n_episodes=30)
    metrics["policy"] = "stable_baselines3_ppo"
    metrics["predictive_model"] = predictive_model_name
    metrics["model_path"] = str(model_path)

    out_path = paths.tables / "ppo_evaluation.csv"
    import pandas as pd

    pd.DataFrame([metrics]).to_csv(out_path, index=False)
    (paths.logs / "ppo_run_summary.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()



