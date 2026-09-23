from __future__ import annotations

import numpy as np
import pandas as pd


def estimate_uncertainty(df: pd.DataFrame, predictions: np.ndarray) -> np.ndarray:
    """Estimate prediction uncertainty from process instability and boundary cases.

    This fallback is deterministic and explainable. It can be replaced later by
    ensemble variance, quantile regression, conformal prediction, or MC dropout.
    """
    pred = np.asarray(predictions, dtype=float)
    boundary_uncertainty = 1.0 - np.minimum.reduce(
        [
            np.abs(pred - 40.0) / 40.0,
            np.abs(pred - 70.0) / 30.0,
            np.ones_like(pred),
        ]
    )
    sensor_conflict = (
        0.30 * df["porosity_risk"].to_numpy(float)
        + 0.25 * df["lens_contamination_level"].to_numpy(float)
        + 0.20 * np.clip(df["back_reflection_intensity"].to_numpy(float), 0, 1)
        + 0.15 * np.clip(df["plume_intensity"].to_numpy(float), 0, 1)
        + 0.10 * df["cooling_system_alarm"].to_numpy(float)
    )
    return np.clip(0.55 * boundary_uncertainty + 0.45 * sensor_conflict, 0, 1)


def should_trigger_human_review(
    prediction: float,
    uncertainty: float,
    uncertainty_threshold: float,
    high_urgency_threshold: float,
) -> bool:
    return bool(uncertainty >= uncertainty_threshold or prediction >= high_urgency_threshold)

