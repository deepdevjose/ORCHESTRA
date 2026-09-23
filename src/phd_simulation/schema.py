from __future__ import annotations

from typing import Final


FEATURE_COLUMNS: Final[list[str]] = [
    "laser_power_w",
    "welding_speed_mm_s",
    "focal_position_error_mm",
    "shielding_gas_flow_l_min",
    "melt_pool_temp_c",
    "back_reflection_intensity",
    "plume_intensity",
    "spatter_count",
    "vibration_rms",
    "robot_path_error_mm",
    "bead_width_mm",
    "bead_height_mm",
    "porosity_risk",
    "visual_defect_score",
    "lens_contamination_level",
    "cooling_system_alarm",
    "time_since_lens_cleaning_h",
]

ACTION_NAMES: Final[dict[int, str]] = {
    0: "do_nothing",
    1: "inspect",
    2: "minor_maintenance",
    3: "major_maintenance",
    4: "urgent_intervention",
}

SCENARIOS: Final[tuple[str, ...]] = (
    "normal",
    "focal_drift",
    "lens_contamination",
    "low_shielding_gas",
    "thermal_overload",
    "motion_instability",
    "ood_focus_drift",
)

OOD_SCENARIOS: Final[set[str]] = {"ood_focus_drift"}

OBSERVATION_NAMES: Final[tuple[str, ...]] = (
    "decision_urgency",
    "uncertainty",
    "production_load",
    "resource_availability",
    "maintenance_age",
    "maintenance_cost_context",
    "failure_hazard",
)

REQUIRED_METADATA: Final[tuple[str, ...]] = (
    "case_id",
    "record_id",
    "cycle",
    "scenario",
    "distribution",
    "provenance_source",
    "provenance_seed",
    "quality_flag",
)
