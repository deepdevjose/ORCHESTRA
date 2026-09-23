from __future__ import annotations

import numpy as np
import pandas as pd


def minmax(series: pd.Series) -> pd.Series:
    low = series.min()
    high = series.max()
    if high == low:
        return series * 0.0
    return (series - low) / (high - low)


def add_maintenance_urgency(df: pd.DataFrame) -> pd.DataFrame:
    """Derive a maintenance urgency score from laser welding instability signals."""
    out = df.copy()

    thermal_risk = minmax((out["melt_pool_temp_c"] - 1450).abs())
    power_risk = minmax((out["laser_power_w"] - 1800).abs())
    speed_risk = minmax((out["welding_speed_mm_s"] - 35).abs())
    focal_risk = minmax(out["focal_position_error_mm"])
    gas_risk = 1.0 - minmax(out["shielding_gas_flow_l_min"])
    optical_risk = 0.55 * minmax(out["back_reflection_intensity"]) + 0.45 * minmax(out["plume_intensity"])
    spatter_risk = minmax(out["spatter_count"])
    motion_risk = 0.55 * minmax(out["vibration_rms"]) + 0.45 * minmax(out["robot_path_error_mm"])
    quality_risk = 0.45 * minmax(out["visual_defect_score"]) + 0.35 * out["porosity_risk"] + 0.20 * minmax((out["bead_width_mm"] - 2.0).abs())
    maintenance_risk = (
        0.50 * out["lens_contamination_level"]
        + 0.30 * minmax(out["time_since_lens_cleaning_h"])
        + 0.20 * out["cooling_system_alarm"]
    )

    raw = (
        0.12 * thermal_risk
        + 0.08 * power_risk
        + 0.07 * speed_risk
        + 0.11 * focal_risk
        + 0.08 * gas_risk
        + 0.12 * optical_risk
        + 0.08 * spatter_risk
        + 0.10 * motion_risk
        + 0.14 * quality_risk
        + 0.10 * maintenance_risk
    )

    out["process_instability_score"] = np.clip(100 * raw, 0, 100)
    out["maintenance_urgency_score"] = np.clip(100 * minmax(out["process_instability_score"]), 0, 100)
    out["maintenance_label"] = pd.cut(
        out["maintenance_urgency_score"],
        bins=[-0.1, 40, 70, 100.1],
        labels=["low", "medium", "high"],
    ).astype(str)
    return out

