from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from .scheduling_env import LaserMaintenanceSchedulingEnv


Policy = Callable[[pd.Series], int]


def reactive_policy(row: pd.Series) -> int:
    return 4 if row["maintenance_urgency_score"] >= 85 else 0


def fixed_preventive_policy_factory(interval: int = 20) -> Policy:
    counter = {"t": 0}

    def policy(row: pd.Series) -> int:
        counter["t"] += 1
        return 2 if counter["t"] % interval == 0 else 0

    return policy


def prediction_only_policy(row: pd.Series) -> int:
    urgency = float(row.get("predicted_urgency", row["maintenance_urgency_score"]))
    if urgency >= 75:
        return 3
    if urgency >= 55:
        return 2
    if urgency >= 40:
        return 1
    return 0


def rule_based_policy(row: pd.Series) -> int:
    urgency = float(row.get("orchestra_urgency", row["maintenance_urgency_score"]))
    uncertainty = float(row.get("uncertainty", 0.0))
    if urgency >= 80:
        return 4
    if urgency >= 65:
        return 3
    if urgency >= 45 or uncertainty >= 0.45:
        return 2
    if uncertainty >= 0.25:
        return 1
    return 0


def greedy_orchestra_policy(row: pd.Series) -> int:
    urgency = float(row.get("orchestra_urgency", row["maintenance_urgency_score"]))
    load = float(row.get("production_load", 0.5))
    if urgency >= 82:
        return 4
    if urgency >= 68 and load < 0.75:
        return 3
    if urgency >= 52:
        return 2
    if urgency >= 35 or row.get("uncertainty", 0.0) > 0.35:
        return 1
    return 0


def evaluate_policy(
    name: str,
    df: pd.DataFrame,
    policy: Policy,
    reward_weights: dict,
    n_episodes: int = 30,
    episode_length: int = 120,
    seed: int = 42,
) -> dict:
    env = LaserMaintenanceSchedulingEnv(df, reward_weights, episode_length=episode_length, seed=seed)
    totals = []
    for _ in range(n_episodes):
        env.reset()
        episode = {"reward": 0.0, "downtime": 0.0, "cost": 0.0, "failures": 0, "unnecessary": 0}
        done = False
        while not done:
            row = env._row()
            action = policy(row)
            _, reward, done, info = env.step(action)
            episode["reward"] += reward
            episode["downtime"] += info["downtime"]
            episode["cost"] += info["cost"]
            episode["failures"] += int(info["failure"])
            episode["unnecessary"] += int(info["unnecessary"])
        totals.append(episode)

    out = {"policy": name}
    for key in totals[0]:
        out[f"mean_{key}"] = float(np.mean([x[key] for x in totals]))
        out[f"std_{key}"] = float(np.std([x[key] for x in totals]))
    return out

