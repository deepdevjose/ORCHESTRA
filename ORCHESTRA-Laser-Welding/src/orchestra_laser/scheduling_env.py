from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


ACTION_NAMES = {
    0: "do_nothing",
    1: "inspect",
    2: "minor_maintenance",
    3: "major_maintenance",
    4: "urgent_intervention",
}


@dataclass
class StepResult:
    reward: float
    downtime: float
    cost: float
    failure: bool
    unnecessary: bool
    action_name: str
    risk_after_action: float
    alignment_bonus: float


class LaserMaintenanceSchedulingEnv:
    """Lightweight Gym-like environment for ORCHESTRA maintenance scheduling."""

    def __init__(self, data: pd.DataFrame, reward_weights: dict, episode_length: int = 120, seed: int = 42):
        self.data = data.reset_index(drop=True)
        self.reward_weights = reward_weights
        self.episode_length = episode_length
        self.rng = np.random.default_rng(seed)
        self.t = 0
        self.time_since_maintenance = 0.0
        self.current_idx = 0

    def reset(self) -> np.ndarray:
        self.t = 0
        self.time_since_maintenance = 0.0
        self.current_idx = int(self.rng.integers(0, len(self.data)))
        return self._state()

    def _row(self) -> pd.Series:
        return self.data.iloc[self.current_idx % len(self.data)]

    def _state(self) -> np.ndarray:
        row = self._row()
        return np.array(
            [
                row.get("orchestra_urgency", row["maintenance_urgency_score"]) / 100.0,
                row.get("uncertainty", 0.0),
                row.get("production_load", 0.5),
                row.get("resource_availability", 0.8),
                min(self.time_since_maintenance / 60.0, 1.0),
                row.get("maintenance_cost_context", 0.5),
                row.get("process_instability_score", 0.0) / 100.0,
            ],
            dtype=float,
        )

    def step(self, action: int) -> tuple[np.ndarray, float, bool, dict]:
        row = self._row()
        result = self.evaluate_action(row, action, self.reward_weights)

        if action in (2, 3, 4):
            self.time_since_maintenance = 0.0
        else:
            self.time_since_maintenance += 1.0

        self.t += 1
        self.current_idx += 1
        done = self.t >= self.episode_length
        info = result.__dict__
        return self._state(), result.reward, done, info

    @staticmethod
    def evaluate_action(row: pd.Series, action: int, reward_weights: dict) -> StepResult:
        decision_urgency = float(row.get("orchestra_urgency", row["maintenance_urgency_score"]))
        true_urgency = float(row["maintenance_urgency_score"])
        production_load = float(row.get("production_load", 0.5))
        resource_availability = float(row.get("resource_availability", 0.8))
        uncertainty = float(row.get("uncertainty", 0.0))

        risk_after_action = true_urgency / 100.0
        downtime = 0.0
        cost = 0.0
        unnecessary = False
        alignment_bonus = 0.0

        if action == 0:
            risk_after_action *= 1.15
            if decision_urgency >= 70:
                alignment_bonus -= 2.5
            elif decision_urgency < 35 and uncertainty < 0.45:
                alignment_bonus += 1.50
        elif action == 1:
            risk_after_action *= 0.85
            downtime = 0.05 + 0.08 * production_load
            cost = 0.06
            if 35 <= decision_urgency < 55 or (uncertainty > 0.45 and decision_urgency < 55):
                alignment_bonus += 1.00
        elif action == 2:
            risk_after_action *= 0.50
            downtime = 0.18 + 0.18 * production_load
            cost = 0.22
            unnecessary = true_urgency < 35
            if 50 <= decision_urgency < 70:
                alignment_bonus += 1.50
        elif action == 3:
            risk_after_action *= 0.22
            downtime = 0.38 + 0.25 * production_load
            cost = 0.48
            unnecessary = true_urgency < 50
            if 65 <= decision_urgency < 85:
                alignment_bonus += 2.00
        elif action == 4:
            risk_after_action *= 0.08
            downtime = 0.70 + 0.20 * production_load
            cost = 0.82
            unnecessary = true_urgency < 75
            if decision_urgency >= 82:
                alignment_bonus += 2.50
        else:
            raise ValueError(f"Unknown action: {action}")

        resource_penalty = max(0.0, 0.5 - resource_availability)
        failure = risk_after_action > 0.82 and action in (0, 1)
        under_treatment_penalty = 0.0
        over_treatment_penalty = 0.0
        if decision_urgency >= 85 and action < 4:
            under_treatment_penalty = 8.0
        elif decision_urgency >= 70 and action < 3:
            under_treatment_penalty = 5.0
        elif decision_urgency >= 55 and action < 2:
            under_treatment_penalty = 2.5

        if action == 1 and decision_urgency < 35 and uncertainty < 0.45:
            over_treatment_penalty = 1.25
        elif action == 2 and decision_urgency < 45:
            over_treatment_penalty = 2.0
        elif action == 3 and decision_urgency < 65:
            over_treatment_penalty = 3.5
        elif action == 4 and decision_urgency < 85:
            over_treatment_penalty = 5.0
        failure_penalty = 40.0 if failure else 0.0
        human_review_penalty = reward_weights.get("human_review", 0.15) * uncertainty

        reward = 1.0
        reward -= reward_weights.get("risk", 2.0) * risk_after_action
        reward -= reward_weights.get("downtime", 1.0) * downtime
        reward -= reward_weights.get("cost", 0.8) * cost
        reward -= reward_weights.get("unnecessary_maintenance", 0.7) * float(unnecessary)
        reward -= resource_penalty
        reward -= failure_penalty
        reward -= under_treatment_penalty
        reward -= over_treatment_penalty
        reward -= human_review_penalty
        reward += alignment_bonus

        return StepResult(
            reward=float(reward),
            downtime=float(downtime),
            cost=float(cost),
            failure=bool(failure),
            unnecessary=bool(unnecessary),
            action_name=ACTION_NAMES[action],
            risk_after_action=float(risk_after_action),
            alignment_bonus=float(alignment_bonus),
        )




