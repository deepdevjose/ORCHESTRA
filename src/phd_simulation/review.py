"""Budgeted simulated human-review routing for uncertain predictions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ReviewDecision:
    """One review outcome after routing and optional expert adjustment."""
    reviewed: bool
    reason: str
    adjusted_urgency: float
    override: bool
    expert_estimate: float


def _expert_observable_estimate(row: pd.Series) -> float:
    """Simulated operator signal from observable indicators only.

    The hidden simulator target is intentionally not read here.  The target is
    used later only to score how useful a review would have been.
    """

    components = [
        26.0 * np.clip(float(row.get("focal_position_error_mm", 0.0)) / 0.25, 0, 1),
        22.0 * np.clip((18.0 - float(row.get("shielding_gas_flow_l_min", 18.0))) / 6.0, 0, 1),
        16.0 * np.clip((float(row.get("melt_pool_temp_c", 1450.0)) - 1450.0) / 260.0, 0, 1),
        10.0 * np.clip(float(row.get("back_reflection_intensity", 0.3)) / 0.65, 0, 1),
        8.0 * np.clip(float(row.get("plume_intensity", 0.4)) / 0.75, 0, 1),
        10.0 * np.clip(float(row.get("porosity_risk", 0.0)), 0, 1),
        10.0 * np.clip(float(row.get("visual_defect_score", 0.0)) / 35.0, 0, 1),
        7.0 * np.clip(float(row.get("lens_contamination_level", 0.0)), 0, 1),
        5.0 * np.clip(float(row.get("vibration_rms", 0.0)) / 0.35, 0, 1),
    ]
    return float(np.clip(sum(components), 0, 100))


def _conflict_score(row: pd.Series) -> float:
    thermal_high = float(row.get("melt_pool_temp_c", 1450.0)) > 1700
    gas_low = float(row.get("shielding_gas_flow_l_min", 18.0)) < 13
    quality_high = float(row.get("visual_defect_score", 0.0)) > 25 or float(row.get("porosity_risk", 0.0)) > 0.35
    optical_high = float(row.get("back_reflection_intensity", 0.0)) > 0.58 or float(row.get("lens_contamination_level", 0.0)) > 0.45
    indicators = [thermal_high, gas_low, quality_high, optical_high]
    return float(sum(indicators) / len(indicators))


class HumanReviewRouter:
    """Uncertainty-triggered review with a fixed review budget."""

    def __init__(self, budget: float = 0.25, high_urgency_threshold: float = 70.0, seed: int = 42):
        self.budget = float(budget)
        self.high_urgency_threshold = float(high_urgency_threshold)
        self.rng = np.random.default_rng(seed)

    def priority_scores(self, frame: pd.DataFrame, predictions: np.ndarray, uncertainties: np.ndarray) -> np.ndarray:
        """Score rows using uncertainty, observable conflict, and predicted risk."""
        conflict = frame.apply(_conflict_score, axis=1).to_numpy(dtype=float)
        high_risk = np.clip((np.asarray(predictions) - 55.0) / 45.0, 0, 1)
        return np.clip(0.58 * np.asarray(uncertainties) + 0.24 * conflict + 0.18 * high_risk, 0, 1)

    def route(self, frame: pd.DataFrame, predictions: np.ndarray, uncertainties: np.ndarray, mode: str) -> tuple[np.ndarray, np.ndarray]:
        """Select reviewed rows for no-review, all-review, random, or uncertainty mode."""
        n = len(frame)
        if mode == "no_review":
            return np.zeros(n, dtype=bool), np.array(["not_reviewed"] * n, dtype=object)
        if mode == "all_review":
            return np.ones(n, dtype=bool), np.array(["all_review"] * n, dtype=object)

        budget_count = max(1, int(round(n * self.budget))) if n else 0
        if mode == "random_review":
            order = self.rng.permutation(n)
            selected = order[:budget_count]
            reasons = np.array(["random_budget"] * n, dtype=object)
        elif mode == "uncertainty_triggered":
            priority = self.priority_scores(frame, predictions, uncertainties)
            selected = np.argsort(-priority, kind="stable")[:budget_count]
            reasons = np.array(["not_reviewed"] * n, dtype=object)
            reasons[selected] = "uncertainty_or_conflict"
        else:
            raise ValueError(f"Unknown review mode: {mode}")
        reviewed = np.zeros(n, dtype=bool)
        reviewed[selected] = True
        if mode == "random_review":
            reasons[selected] = "random_budget"
        return reviewed, reasons

    def apply(
        self,
        frame: pd.DataFrame,
        predictions: np.ndarray,
        uncertainties: np.ndarray,
        mode: str,
        *,
        noise_std: float = 5.0,
        override_threshold: float = 7.5,
    ) -> pd.DataFrame:
        """Apply the simulated expert signal while preserving the original prediction."""
        reviewed, reasons = self.route(frame, predictions, uncertainties, mode)
        adjusted: list[float] = []
        expert_estimates: list[float] = []
        overrides: list[bool] = []
        for index, (_, row) in enumerate(frame.iterrows()):
            prediction = float(predictions[index])
            expert = _expert_observable_estimate(row)
            if reviewed[index]:
                estimate = float(np.clip(expert + self.rng.normal(0, noise_std), 0, 100))
                adjusted_value = float(np.clip(0.45 * prediction + 0.55 * estimate, 0, 100))
                override = bool(abs(adjusted_value - prediction) >= override_threshold)
            else:
                estimate = np.nan
                adjusted_value = prediction
                override = False
            adjusted.append(adjusted_value)
            expert_estimates.append(estimate)
            overrides.append(override)
        out = frame.copy()
        out["predicted_urgency"] = np.asarray(predictions, dtype=float)
        out["uncertainty"] = np.asarray(uncertainties, dtype=float)
        out["human_review_triggered"] = reviewed
        out["review_reason"] = reasons
        out["expert_estimate"] = expert_estimates
        out["orchestra_urgency"] = adjusted
        out["human_override"] = overrides
        out["review_mode"] = mode
        return out


def action_from_urgency(urgency: float, uncertainty: float = 0.0, *, full_review: bool = True) -> int:
    """Map urgency and uncertainty to one of the five scheduling actions."""
    if urgency >= 84:
        return 4
    if full_review and uncertainty >= 0.72 and urgency >= 45:
        return 4
    if urgency >= 68 or (full_review and uncertainty >= 0.60):
        return 3
    if urgency >= 52 or (full_review and uncertainty >= 0.42):
        return 2
    if urgency >= 35 or (full_review and uncertainty >= 0.30):
        return 1
    return 0


def review_metrics(frame: pd.DataFrame, high_risk_threshold: float = 70.0) -> dict[str, float]:
    """Summarize review rate, overrides, high-risk recall, and risky decisions."""
    if frame.empty:
        return {"rows": 0, "review_rate": 0.0, "override_rate": 0.0, "high_risk_recall_before": 0.0, "high_risk_recall_after": 0.0, "risky_decisions": 0.0}
    true_high = frame["maintenance_urgency_score"].to_numpy(dtype=float) >= high_risk_threshold
    before_action = np.array([action_from_urgency(value, 0.0, full_review=False) for value in frame["predicted_urgency"]])
    after_action = np.array([
        action_from_urgency(value, uncertainty, full_review=bool(reviewed))
        for value, uncertainty, reviewed in zip(frame["orchestra_urgency"], frame["uncertainty"], frame["human_review_triggered"])
    ])
    before_safe = before_action >= 3
    after_safe = after_action >= 3
    return {
        "rows": float(len(frame)),
        "review_rate": float(frame["human_review_triggered"].mean()),
        "override_rate": float(frame["human_override"].mean()),
        "high_risk_recall_before": float((before_safe & true_high).sum() / max(true_high.sum(), 1)),
        "high_risk_recall_after": float((after_safe & true_high).sum() / max(true_high.sum(), 1)),
        "risky_decisions": float((true_high & ~after_safe).sum()),
    }
