from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from .schema import ACTION_NAMES, OBSERVATION_NAMES


@dataclass(frozen=True)
class StepOutcome:
    reward: float
    downtime: float
    cost: float
    failure: bool
    unnecessary: bool
    risk_after_action: float
    action_name: str
    resource_blocked: bool
    maintenance_age: float


class LaserWeldingSchedulingEnv:
    """Dynamic five-action scheduling environment backed by latent trajectories."""

    def __init__(self, data: pd.DataFrame, reward_weights: dict[str, float], episode_length: int = 40, seed: int = 42, maintenance_delay: int = 0):
        if data.empty:
            raise ValueError("Scheduling environment received an empty dataset")
        self.data = data.sort_values(["case_id", "cycle"]).reset_index(drop=True)
        self.reward_weights = dict(reward_weights)
        self.episode_length = int(episode_length)
        self.seed = int(seed)
        self.maintenance_delay = int(maintenance_delay)
        self.rng = np.random.default_rng(seed)
        self.case_ids = self.data["case_id"].drop_duplicates().tolist()
        self.case_frame = self.data.iloc[:0].copy()
        self.current_case = ""
        self.current_step = 0
        self.maintenance_age = 0.0
        self.deferred_steps = 0.0

    def reset(self, case_id: str | None = None, seed: int | None = None) -> np.ndarray:
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self.current_case = case_id or str(self.rng.choice(self.case_ids))
        self.case_frame = self.data.loc[self.data["case_id"] == self.current_case].reset_index(drop=True)
        self.current_step = 0
        self.maintenance_age = 0.0
        self.deferred_steps = 0.0
        return self.state()

    def current_row(self) -> pd.Series:
        if self.case_frame.empty:
            self.reset()
        index = min(self.current_step, len(self.case_frame) - 1)
        return self.case_frame.iloc[index]

    def state(self) -> np.ndarray:
        row = self.current_row()
        decision = float(row.get("orchestra_urgency", row.get("predicted_urgency", row["maintenance_urgency_score"])))
        uncertainty = float(row.get("uncertainty", 0.0))
        return np.array([
            np.clip(decision / 100.0, 0, 1),
            np.clip(uncertainty, 0, 1),
            np.clip(float(row.get("production_load", 0.5)), 0, 1),
            np.clip(float(row.get("resource_availability", 0.8)), 0, 1),
            np.clip(self.maintenance_age / 40.0, 0, 1),
            np.clip(float(row.get("maintenance_cost_context", 0.5)), 0, 1),
            np.clip(float(row.get("failure_hazard", 0.0)) + self.deferred_steps * 0.01, 0, 1),
        ], dtype=np.float32)

    @staticmethod
    def evaluate_action(row: pd.Series, action: int, reward_weights: dict[str, float], maintenance_age: float = 0.0, deferred_steps: float = 0.0) -> StepOutcome:
        if action not in ACTION_NAMES:
            raise ValueError(f"Unknown action: {action}")
        decision = float(row.get("orchestra_urgency", row.get("predicted_urgency", row["maintenance_urgency_score"])))
        true_urgency = float(row["maintenance_urgency_score"])
        load = float(row.get("production_load", 0.5))
        resource = float(row.get("resource_availability", 0.8))
        uncertainty = float(row.get("uncertainty", 0.0))
        base_risk = np.clip(true_urgency / 100.0 + 0.004 * maintenance_age + 0.02 * deferred_steps, 0, 1.5)
        reduction = {0: 0.0, 1: 0.10, 2: 0.38, 3: 0.66, 4: 0.88}[action]
        resource_blocked = bool(action >= 3 and resource < 0.42)
        if resource_blocked:
            reduction *= 0.55
        risk_after = float(np.clip(base_risk * (1 - reduction), 0, 1.5))
        downtime = {0: 0.0, 1: 0.06 + 0.08 * load, 2: 0.20 + 0.18 * load, 3: 0.45 + 0.25 * load, 4: 0.78 + 0.18 * load}[action]
        cost = {0: 0.0, 1: 0.06, 2: 0.22, 3: 0.50, 4: 0.86}[action] * (1 + 0.25 * float(row.get("maintenance_cost_context", 0.5)))
        failure = bool(risk_after > 0.82 and action in (0, 1))
        unnecessary = bool(action >= 2 and true_urgency < {2: 38, 3: 55, 4: 76}[action])
        reward = 1.0
        reward -= reward_weights.get("risk", 3.0) * risk_after
        reward -= reward_weights.get("downtime", 1.0) * downtime
        reward -= reward_weights.get("cost", 0.8) * cost
        reward -= reward_weights.get("unnecessary_maintenance", 1.0) * float(unnecessary)
        reward -= reward_weights.get("human_review", 0.15) * uncertainty
        reward -= reward_weights.get("failure", 45.0) * float(failure)
        if decision >= 82 and action == 4:
            reward += 2.5
        elif decision >= 68 and action >= 3:
            reward += 1.5
        elif decision < 35 and action == 0 and uncertainty < 0.45:
            reward += 0.9
        if decision >= 82 and action < 4:
            reward -= 7.0
        elif decision >= 68 and action < 3:
            reward -= 4.0
        elif decision >= 52 and action < 2:
            reward -= 2.0
        next_age = 0.0 if action >= 2 and not resource_blocked else maintenance_age + 1.0
        return StepOutcome(
            reward=float(reward),
            downtime=float(downtime),
            cost=float(cost),
            failure=failure,
            unnecessary=unnecessary,
            risk_after_action=risk_after,
            action_name=ACTION_NAMES[action],
            resource_blocked=resource_blocked,
            maintenance_age=float(next_age),
        )

    def step(self, action: int) -> tuple[np.ndarray, float, bool, dict[str, object]]:
        row = self.current_row()
        result = self.evaluate_action(row, int(action), self.reward_weights, self.maintenance_age, self.deferred_steps)
        if int(action) >= 2 and not result.resource_blocked:
            self.maintenance_age = float(self.maintenance_delay)
            self.deferred_steps = float(self.maintenance_delay)
        else:
            self.maintenance_age += 1.0
            self.deferred_steps += 1.0 if int(action) == 0 else 0.25
        self.current_step += 1
        done = self.current_step >= min(self.episode_length, len(self.case_frame))
        info = {
            "record_id": row["record_id"],
            "case_id": row["case_id"],
            "cycle": int(row["cycle"]),
            "scenario": row["scenario"],
            "maintenance_urgency_score": float(row["maintenance_urgency_score"]),
            "predicted_urgency": float(row.get("predicted_urgency", row.get("maintenance_urgency_score", 0.0))),
            "orchestra_urgency": float(row.get("orchestra_urgency", row.get("predicted_urgency", row.get("maintenance_urgency_score", 0.0)))),
            "uncertainty": float(row.get("uncertainty", 0.0)),
            "action": int(action),
            **result.__dict__,
        }
        return self.state(), result.reward, done, info


def run_episode(env: LaserWeldingSchedulingEnv, policy: Callable[[pd.Series], int], *, case_id: str, seed: int, policy_name: str) -> tuple[dict[str, float | int | str], pd.DataFrame]:
    env.reset(case_id=case_id, seed=seed)
    trace: list[dict[str, object]] = []
    totals = {"reward": 0.0, "downtime": 0.0, "cost": 0.0, "failures": 0.0, "unnecessary": 0.0, "reviewed": 0.0, "resource_blocked": 0.0}
    done = False
    while not done:
        row = env.current_row()
        action = int(policy(row))
        _, reward, done, info = env.step(action)
        event = {"policy": policy_name, "seed": seed, **info, "reward": reward}
        trace.append(event)
        totals["reward"] += float(reward)
        totals["downtime"] += float(info["downtime"])
        totals["cost"] += float(info["cost"])
        totals["failures"] += float(info["failure"])
        totals["unnecessary"] += float(info["unnecessary"])
        totals["reviewed"] += float(row.get("human_review_triggered", False))
        totals["resource_blocked"] += float(info["resource_blocked"])
    totals.update({"policy": policy_name, "case_id": case_id, "seed": seed, "steps": len(trace)})
    return totals, pd.DataFrame(trace)


def evaluate_policy(env: LaserWeldingSchedulingEnv, policy: Callable[[pd.Series], int], *, policy_name: str, episodes: int = 20, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    summaries: list[dict[str, float | int | str]] = []
    traces: list[pd.DataFrame] = []
    for episode in range(episodes):
        case_id = env.case_ids[episode % len(env.case_ids)]
        summary, trace = run_episode(env, policy, case_id=case_id, seed=seed + episode, policy_name=policy_name)
        summaries.append(summary)
        traces.append(trace)
    return pd.DataFrame(summaries), pd.concat(traces, ignore_index=True) if traces else pd.DataFrame()


def observation_names() -> tuple[str, ...]:
    return OBSERVATION_NAMES
