from __future__ import annotations

import numpy as np
import pandas as pd


SCENARIOS = [
    "normal",
    "focal_offset",
    "low_shielding_gas",
    "high_laser_power",
    "speed_variation",
    "fixture_vibration",
    "lens_contamination_proxy",
]


def generate_laser_welding_data(n_samples: int = 600, seed: int = 42) -> pd.DataFrame:
    """Create controlled laser welding samples for early paper development.

    This is a lab-informed synthetic generator. Replace or calibrate it with
    real laser welding station data once available.
    """
    rng = np.random.default_rng(seed)
    scenario = rng.choice(SCENARIOS, size=n_samples)

    df = pd.DataFrame({"scenario": scenario})
    df["laser_power_w"] = rng.normal(1800, 90, n_samples)
    df["welding_speed_mm_s"] = rng.normal(35, 3.0, n_samples)
    df["focal_position_error_mm"] = np.abs(rng.normal(0.08, 0.05, n_samples))
    df["shielding_gas_flow_l_min"] = rng.normal(18, 1.2, n_samples)
    df["melt_pool_temp_c"] = rng.normal(1450, 75, n_samples)
    df["back_reflection_intensity"] = rng.normal(0.35, 0.07, n_samples)
    df["plume_intensity"] = rng.normal(0.45, 0.08, n_samples)
    df["spatter_count"] = rng.poisson(4, n_samples).astype(float)
    df["vibration_rms"] = np.abs(rng.normal(0.08, 0.03, n_samples))
    df["robot_path_error_mm"] = np.abs(rng.normal(0.05, 0.025, n_samples))
    df["bead_width_mm"] = rng.normal(2.0, 0.12, n_samples)
    df["bead_height_mm"] = rng.normal(0.62, 0.06, n_samples)
    df["porosity_risk"] = np.clip(rng.normal(0.12, 0.05, n_samples), 0, 1)
    df["visual_defect_score"] = np.clip(rng.normal(8, 4, n_samples), 0, 100)
    df["lens_contamination_level"] = np.clip(rng.normal(0.12, 0.06, n_samples), 0, 1)
    df["cooling_system_alarm"] = (rng.random(n_samples) < 0.03).astype(float)
    df["time_since_lens_cleaning_h"] = rng.uniform(0, 45, n_samples)

    _apply_scenario_effects(df, rng)
    return df.round(4)


def _apply_scenario_effects(df: pd.DataFrame, rng: np.random.Generator) -> None:
    mask = df["scenario"] == "focal_offset"
    df.loc[mask, "focal_position_error_mm"] += rng.uniform(0.18, 0.45, mask.sum())
    df.loc[mask, "bead_width_mm"] += rng.normal(0.18, 0.06, mask.sum())
    df.loc[mask, "visual_defect_score"] += rng.uniform(8, 22, mask.sum())

    mask = df["scenario"] == "low_shielding_gas"
    df.loc[mask, "shielding_gas_flow_l_min"] -= rng.uniform(4, 8, mask.sum())
    df.loc[mask, "porosity_risk"] += rng.uniform(0.22, 0.48, mask.sum())
    df.loc[mask, "visual_defect_score"] += rng.uniform(10, 28, mask.sum())

    mask = df["scenario"] == "high_laser_power"
    df.loc[mask, "laser_power_w"] += rng.uniform(180, 420, mask.sum())
    df.loc[mask, "melt_pool_temp_c"] += rng.uniform(90, 230, mask.sum())
    df.loc[mask, "spatter_count"] += rng.poisson(5, mask.sum())
    df.loc[mask, "back_reflection_intensity"] += rng.uniform(0.08, 0.22, mask.sum())

    mask = df["scenario"] == "speed_variation"
    df.loc[mask, "welding_speed_mm_s"] += rng.choice([-1, 1], mask.sum()) * rng.uniform(6, 12, mask.sum())
    df.loc[mask, "bead_width_mm"] += rng.normal(0.0, 0.22, mask.sum())
    df.loc[mask, "visual_defect_score"] += rng.uniform(5, 18, mask.sum())

    mask = df["scenario"] == "fixture_vibration"
    df.loc[mask, "vibration_rms"] += rng.uniform(0.12, 0.28, mask.sum())
    df.loc[mask, "robot_path_error_mm"] += rng.uniform(0.08, 0.22, mask.sum())
    df.loc[mask, "visual_defect_score"] += rng.uniform(8, 24, mask.sum())

    mask = df["scenario"] == "lens_contamination_proxy"
    df.loc[mask, "lens_contamination_level"] += rng.uniform(0.25, 0.55, mask.sum())
    df.loc[mask, "back_reflection_intensity"] += rng.uniform(0.12, 0.28, mask.sum())
    df.loc[mask, "plume_intensity"] += rng.uniform(0.08, 0.18, mask.sum())
    df.loc[mask, "time_since_lens_cleaning_h"] += rng.uniform(15, 45, mask.sum())

    clipped = [
        "porosity_risk",
        "lens_contamination_level",
        "back_reflection_intensity",
        "plume_intensity",
    ]
    for col in clipped:
        df[col] = np.clip(df[col], 0, 1)
    df["visual_defect_score"] = np.clip(df["visual_defect_score"], 0, 100)
    df["shielding_gas_flow_l_min"] = np.clip(df["shielding_gas_flow_l_min"], 4, None)

