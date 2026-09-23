from __future__ import annotations

import numpy as np
import pandas as pd

from .baselines import (
    evaluate_policy,
    fixed_preventive_policy_factory,
    greedy_orchestra_policy,
    prediction_only_policy,
    reactive_policy,
    rule_based_policy,
)
from .human_agent import HumanOperatorAgent
from .uncertainty import estimate_uncertainty


def add_scheduling_context(df: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    out = df.copy()
    out["production_load"] = rng.uniform(0.25, 0.95, len(out))
    out["resource_availability"] = rng.uniform(0.35, 1.0, len(out))
    out["maintenance_cost_context"] = rng.uniform(0.25, 0.90, len(out))
    return out


def apply_orchestra_review(df: pd.DataFrame, predictions: np.ndarray, config: dict) -> pd.DataFrame:
    out = df.copy()
    out["predicted_urgency"] = predictions
    out["uncertainty"] = estimate_uncertainty(out, predictions)

    human_cfg = config["human_review"]
    agent = HumanOperatorAgent(
        uncertainty_threshold=float(config["uncertainty_threshold"]),
        high_urgency_threshold=float(config["high_urgency_threshold"]),
        override_probability=float(human_cfg["override_probability"]),
        false_negative_sensitivity=float(human_cfg["false_negative_sensitivity"]),
        noise_std=float(human_cfg["noise_std"]),
        seed=int(config["random_seed"]),
    )

    reviewed = []
    adjusted = []
    overrides = []
    for pred, uncertainty, true_urgency in zip(
        out["predicted_urgency"],
        out["uncertainty"],
        out["maintenance_urgency_score"],
    ):
        result = agent.review(float(pred), float(uncertainty), float(true_urgency))
        reviewed.append(result.reviewed)
        adjusted.append(result.adjusted_prediction)
        overrides.append(result.override)

    out["human_review_triggered"] = reviewed
    out["human_override"] = overrides
    out["orchestra_urgency"] = adjusted
    return out


def run_baseline_comparison(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    weights = config["reward_weights"]
    n_episodes = int(config["n_eval_episodes"])
    episode_length = int(config["episode_length"])
    seed = int(config["random_seed"])
    rows = [
        evaluate_policy("reactive", df, reactive_policy, weights, n_episodes, episode_length, seed),
        evaluate_policy("fixed_preventive", df, fixed_preventive_policy_factory(20), weights, n_episodes, episode_length, seed),
        evaluate_policy("prediction_only", df, prediction_only_policy, weights, n_episodes, episode_length, seed),
        evaluate_policy("rule_based", df, rule_based_policy, weights, n_episodes, episode_length, seed),
        evaluate_policy("full_orchestra_greedy", df, greedy_orchestra_policy, weights, n_episodes, episode_length, seed),
    ]
    return pd.DataFrame(rows)


def run_ablation_study(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    variants = []

    no_human = df.copy()
    no_human["orchestra_urgency"] = no_human["predicted_urgency"]
    no_human["uncertainty"] = 0.0
    variants.append(("without_human_review", no_human))

    no_uncertainty = df.copy()
    no_uncertainty["uncertainty"] = 0.0
    variants.append(("without_uncertainty_trigger", no_uncertainty))

    full = df.copy()
    variants.append(("full_orchestra", full))

    rows = []
    for name, data in variants:
        result = evaluate_policy(
            name,
            data,
            greedy_orchestra_policy,
            config["reward_weights"],
            int(config["n_eval_episodes"]),
            int(config["episode_length"]),
            int(config["random_seed"]),
        )
        rows.append(result)
    return pd.DataFrame(rows)


def run_sensitivity_analysis(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    base_weights = dict(config["reward_weights"])
    for risk_weight in [1.0, 2.0, 3.0]:
        for cost_weight in [0.5, 0.8, 1.2]:
            weights = dict(base_weights)
            weights["risk"] = risk_weight
            weights["cost"] = cost_weight
            result = evaluate_policy(
                f"risk_{risk_weight}_cost_{cost_weight}",
                df,
                greedy_orchestra_policy,
                weights,
                int(config["n_eval_episodes"]),
                int(config["episode_length"]),
                int(config["random_seed"]),
            )
            result["risk_weight"] = risk_weight
            result["cost_weight"] = cost_weight
            rows.append(result)
    return pd.DataFrame(rows)

