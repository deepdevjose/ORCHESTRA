from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class HumanReviewResult:
    reviewed: bool
    original_prediction: float
    adjusted_prediction: float
    override: bool


class HumanOperatorAgent:
    """Simulates selective human review for uncertain laser welding cases."""

    def __init__(
        self,
        uncertainty_threshold: float,
        high_urgency_threshold: float,
        override_probability: float = 0.65,
        false_negative_sensitivity: float = 0.80,
        noise_std: float = 4.0,
        seed: int = 42,
    ):
        self.uncertainty_threshold = uncertainty_threshold
        self.high_urgency_threshold = high_urgency_threshold
        self.override_probability = override_probability
        self.false_negative_sensitivity = false_negative_sensitivity
        self.noise_std = noise_std
        self.rng = np.random.default_rng(seed)

    def review(self, prediction: float, uncertainty: float, true_urgency_proxy: float | None = None) -> HumanReviewResult:
        reviewed = uncertainty >= self.uncertainty_threshold or prediction >= self.high_urgency_threshold
        if not reviewed:
            return HumanReviewResult(False, prediction, prediction, False)

        adjusted = prediction
        override = False
        if true_urgency_proxy is not None:
            is_false_negative = prediction < self.high_urgency_threshold <= true_urgency_proxy
            if is_false_negative and self.rng.random() < self.false_negative_sensitivity:
                adjusted = true_urgency_proxy + self.rng.normal(0, self.noise_std)
                override = True
            elif self.rng.random() < self.override_probability:
                adjusted = 0.65 * prediction + 0.35 * true_urgency_proxy + self.rng.normal(0, self.noise_std)
                override = abs(adjusted - prediction) > 5
        else:
            adjusted = prediction + self.rng.normal(0, self.noise_std)
            override = abs(adjusted - prediction) > 5

        return HumanReviewResult(True, prediction, float(np.clip(adjusted, 0, 100)), bool(override))

