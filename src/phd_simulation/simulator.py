"""Seeded latent-process simulator and dataset validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from .schema import FEATURE_COLUMNS, OOD_SCENARIOS, SCENARIOS


@dataclass(frozen=True)
class SimulatorOptions:
    """Robustness knobs controlling sensor noise, missingness, drift, and delay."""
    sensor_noise: float = 0.018
    missing_modality_rate: float = 0.0
    concept_drift: float = 0.0
    resource_availability_floor: float = 0.30
    maintenance_delay: int = 0


def _sigmoid(value: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-np.asarray(value)))


def _bounded_normal(rng: np.random.Generator, mean: float, sd: float, size: int) -> np.ndarray:
    return rng.normal(mean, sd, size).astype(float)


def _scenario_for_case(index: int, n_cases: int, ood_fraction: float, rng: np.random.Generator) -> tuple[str, str]:
    n_ood = max(1, int(round(n_cases * ood_fraction)))
    if index < n_ood:
        return "ood_focus_drift", "ood"
    scenario = str(rng.choice(SCENARIOS[:-1], p=[0.34, 0.13, 0.13, 0.12, 0.13, 0.15]))
    return scenario, "in_distribution"


def _apply_sensor_noise(
    values: dict[str, float],
    rng: np.random.Generator,
    noise_scale: float,
    missing_rate: float,
) -> tuple[dict[str, float], list[str]]:
    """Apply modality-specific sensor noise and deterministic missingness tags."""

    noisy = dict(values)
    for name, value in values.items():
        if name in {"cooling_system_alarm", "spatter_count"}:
            continue
        scale = max(abs(value), 1.0) * noise_scale
        noisy[name] = float(value + rng.normal(0.0, scale))

    missing: list[str] = []
    if missing_rate > 0 and rng.random() < missing_rate:
        modality = str(rng.choice(["thermal", "optical", "motion", "quality"]))
        groups = {
            "thermal": ["melt_pool_temp_c"],
            "optical": ["back_reflection_intensity", "plume_intensity"],
            "motion": ["vibration_rms", "robot_path_error_mm"],
            "quality": ["porosity_risk", "visual_defect_score"],
        }
        for column in groups[modality]:
            noisy[column] = np.nan
        missing.append(modality)
    return noisy, missing


def _clip_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    bounds = {
        "laser_power_w": (900, 2800),
        "welding_speed_mm_s": (12, 65),
        "focal_position_error_mm": (0, 1.8),
        "shielding_gas_flow_l_min": (4, 24),
        "melt_pool_temp_c": (900, 2200),
        "back_reflection_intensity": (0, 1),
        "plume_intensity": (0, 1),
        "spatter_count": (0, 80),
        "vibration_rms": (0, 1.5),
        "robot_path_error_mm": (0, 1.2),
        "bead_width_mm": (0.8, 4.2),
        "bead_height_mm": (0.2, 1.3),
        "porosity_risk": (0, 1),
        "visual_defect_score": (0, 100),
        "lens_contamination_level": (0, 1),
        "time_since_lens_cleaning_h": (0, 240),
    }
    for column, (low, high) in bounds.items():
        out[column] = out[column].clip(low, high)
    out["cooling_system_alarm"] = out["cooling_system_alarm"].clip(0, 1).round()
    return out


def _assign_case_splits(
    frame: pd.DataFrame,
    seed: int,
    train_fraction: float = 0.60,
    calibration_fraction: float = 0.20,
) -> pd.DataFrame:
    out = frame.copy()
    rng = np.random.default_rng(seed + 991)
    id_cases = out.loc[out["distribution"] == "in_distribution", "case_id"].drop_duplicates().to_numpy()
    rng.shuffle(id_cases)
    train_end = int(len(id_cases) * train_fraction)
    calibration_end = int(len(id_cases) * (train_fraction + calibration_fraction))
    split_map = {case: "train" for case in id_cases[:train_end]}
    split_map.update({case: "calibration" for case in id_cases[train_end:calibration_end]})
    split_map.update({case: "test" for case in id_cases[calibration_end:]})
    out["split"] = out["case_id"].map(split_map).fillna("ood")
    return out


def validate_dataset(frame: pd.DataFrame) -> dict[str, object]:
    """Return structural, finite-feature, scenario, split, and OOD checks."""
    missing_features = [column for column in FEATURE_COLUMNS if column not in frame.columns]
    missing_metadata = [column for column in ["case_id", "record_id", "scenario", "distribution", "split"] if column not in frame.columns]
    finite = bool(np.isfinite(frame[FEATURE_COLUMNS].to_numpy(dtype=float, na_value=np.nan)).all()) if not missing_features else False
    return {
        "rows": int(len(frame)),
        "cases": int(frame["case_id"].nunique()) if "case_id" in frame.columns else 0,
        "missing_feature_columns": missing_features,
        "missing_metadata_columns": missing_metadata,
        "features_finite": finite,
        "scenario_counts": frame["scenario"].value_counts().to_dict() if "scenario" in frame.columns else {},
        "split_counts": frame["split"].value_counts().to_dict() if "split" in frame.columns else {},
        "ood_isolated": bool((frame.loc[frame["distribution"] == "ood", "split"] == "ood").all()) if "distribution" in frame.columns and "split" in frame.columns else False,
    }


def generate_laser_dataset(
    n_cases: int = 180,
    episode_length: int = 40,
    seed: int = 42,
    ood_fraction: float = 0.15,
    options: SimulatorOptions | None = None,
    train_fraction: float = 0.60,
    calibration_fraction: float = 0.20,
) -> pd.DataFrame:
    """Generate seeded trajectories from a latent laser-welding process model.

    The simulator separates *hidden* process health from measured sensors.  A
    case is a trajectory, so train/calibration/test splits are assigned by
    case rather than by row.  This prevents adjacent cycles from leaking into
    both training and evaluation and leaves OOD trajectories entirely held out.
    """

    options = options or SimulatorOptions()
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []

    for case_index in range(n_cases):
        scenario, distribution = _scenario_for_case(case_index, n_cases, ood_fraction, rng)
        case_id = f"case_{seed}_{case_index:04d}"
        base_health = float(rng.uniform(0.03, 0.18) if scenario == "normal" else rng.uniform(0.16, 0.38))
        if distribution == "ood":
            base_health = float(rng.uniform(0.35, 0.52))
        fault_severity = float(rng.uniform(0.45, 0.95) if scenario != "normal" else rng.uniform(0.0, 0.18))
        drift_rate = float(rng.uniform(0.004, 0.012))
        if scenario == "normal":
            drift_rate *= 0.45
        if distribution == "ood":
            drift_rate *= 1.6
        phase = float(rng.uniform(0, 2 * np.pi))

        for cycle in range(episode_length):
            progress = cycle / max(episode_length - 1, 1)
            load = float(np.clip(0.52 + 0.22 * np.sin(phase + cycle / 8) + rng.normal(0, 0.045), 0.18, 0.98))
            drift_multiplier = 1.0 + options.concept_drift * progress
            health = float(np.clip(base_health + drift_rate * cycle * drift_multiplier + 0.035 * load + rng.normal(0, 0.008), 0, 1.35))
            hidden_fault = float(np.clip(fault_severity * (0.45 + 0.55 * progress) + rng.normal(0, 0.018), 0, 1.5))

            focal_fault = 0.0
            gas_fault = 0.0
            thermal_fault = 0.0
            lens_fault = 0.0
            motion_fault = 0.0
            if scenario in {"focal_drift", "ood_focus_drift"}:
                focal_fault = hidden_fault * (0.50 if scenario == "focal_drift" else 1.20)
            if scenario == "low_shielding_gas":
                gas_fault = hidden_fault
            if scenario == "thermal_overload":
                thermal_fault = hidden_fault
            if scenario == "lens_contamination":
                lens_fault = hidden_fault
            if scenario == "motion_instability":
                motion_fault = hidden_fault
            if distribution == "ood":
                gas_fault += 0.32 * hidden_fault
                thermal_fault += 0.28 * hidden_fault

            power = 1800 + 75 * rng.normal() + 220 * thermal_fault + 120 * load
            speed = 35 + 2.8 * rng.normal() - 2.2 * thermal_fault + 4.0 * (load - 0.5)
            focal_error = 0.06 + abs(0.035 * rng.normal()) + 0.10 * health + 0.42 * focal_fault
            gas_flow = 18.0 + 0.8 * rng.normal() - 4.8 * gas_fault
            melt_temp = 1450 + 55 * rng.normal() + 195 * (power / 1800 - 1) + 260 * thermal_fault + 65 * health
            back_reflection = 0.30 + 0.035 * rng.normal() + 0.25 * lens_fault + 0.16 * focal_fault + 0.05 * health
            plume = 0.40 + 0.045 * rng.normal() + 0.20 * gas_fault + 0.12 * lens_fault + 0.04 * health
            spatter = max(0.0, rng.poisson(3.0 + 8.0 * thermal_fault + 4.0 * gas_fault + 2.0 * health))
            vibration = abs(0.07 + 0.018 * rng.normal() + 0.32 * motion_fault + 0.05 * health)
            path_error = abs(0.045 + 0.012 * rng.normal() + 0.19 * motion_fault + 0.025 * health)
            bead_width = 2.0 + 0.06 * rng.normal() + 0.25 * focal_fault - 0.10 * (speed - 35) / 10
            bead_height = 0.62 + 0.03 * rng.normal() + 0.12 * thermal_fault - 0.05 * gas_fault
            porosity = np.clip(0.08 + 0.30 * gas_fault + 0.12 * thermal_fault + 0.08 * health + 0.03 * rng.normal(), 0, 1)
            visual_defect = np.clip(5 + 3 * rng.normal() + 22 * focal_fault + 20 * gas_fault + 16 * motion_fault + 18 * lens_fault + 10 * health, 0, 100)
            lens = np.clip(0.08 + 0.05 * rng.normal() + 0.48 * lens_fault + 0.12 * health, 0, 1)
            cooling_alarm = float(rng.random() < np.clip(0.015 + 0.16 * thermal_fault + 0.03 * health, 0, 0.9))
            cleaning_hours = max(0.0, 24 + 15 * rng.normal() + 90 * lens_fault + 34 * progress)

            observed, missing_modalities = _apply_sensor_noise(
                {
                    "laser_power_w": power,
                    "welding_speed_mm_s": speed,
                    "focal_position_error_mm": focal_error,
                    "shielding_gas_flow_l_min": gas_flow,
                    "melt_pool_temp_c": melt_temp,
                    "back_reflection_intensity": back_reflection,
                    "plume_intensity": plume,
                    "spatter_count": spatter,
                    "vibration_rms": vibration,
                    "robot_path_error_mm": path_error,
                    "bead_width_mm": bead_width,
                    "bead_height_mm": bead_height,
                    "porosity_risk": porosity,
                    "visual_defect_score": visual_defect,
                    "lens_contamination_level": lens,
                    "cooling_system_alarm": cooling_alarm,
                    "time_since_lens_cleaning_h": cleaning_hours,
                },
                rng,
                options.sensor_noise,
                options.missing_modality_rate,
            )

            hazard = float(np.clip(
                0.34 * health
                + 0.22 * hidden_fault
                + 0.12 * focal_fault
                + 0.11 * gas_fault
                + 0.10 * thermal_fault
                + 0.08 * lens_fault
                + 0.08 * motion_fault
                + 0.05 * load
                + rng.normal(0, 0.018),
                0,
                1.5,
            ))
            urgency = float(np.clip(100 * _sigmoid(5.8 * (hazard - 0.43)), 0, 100))
            failure_hazard = float(np.clip(_sigmoid(7.0 * (hazard - 0.72)), 0, 1))
            process_instability = float(np.clip(100 * (0.70 * hazard + 0.30 * np.clip(visual_defect / 100, 0, 1)), 0, 100))

            row: dict[str, object] = dict(observed)
            row.update(
                {
                    "case_id": case_id,
                    "record_id": f"{case_id}_cycle_{cycle:03d}",
                    "cycle": cycle,
                    "timestamp_s": cycle * 0.5,
                    "scenario": scenario,
                    "distribution": distribution,
                    "seed": seed,
                    "provenance_source": "orchestra_phd_latent_simulator_v1",
                    "provenance_seed": seed,
                    "quality_flag": "missing_" + "+".join(missing_modalities) if missing_modalities else "ok",
                    "missing_modalities": "+".join(missing_modalities),
                    "production_load": load,
                    "resource_availability": float(rng.uniform(options.resource_availability_floor, 1.0)),
                    "maintenance_cost_context": float(np.clip(0.35 + 0.45 * load + 0.08 * rng.normal(), 0.2, 1.0)),
                    "latent_health": health,
                    "latent_fault_severity": hidden_fault,
                    "failure_hazard": failure_hazard,
                    "failure_event": bool(rng.random() < failure_hazard * 0.16),
                    "process_instability_score": process_instability,
                    "maintenance_urgency_score": urgency,
                    "maintenance_label": "high" if urgency > 70 else "medium" if urgency > 40 else "low",
                }
            )
            rows.append(row)

    frame = _clip_features(pd.DataFrame(rows))
    for column in FEATURE_COLUMNS:
        if frame[column].isna().any():
            # Missingness is retained in quality metadata, but a model-ready
            # copy is deterministic and uses train-time medians later.
            frame[column] = frame[column].fillna(frame[column].median())
    frame = _assign_case_splits(frame, seed, train_fraction, calibration_fraction)
    return frame


def regenerate_with_condition(
    base: pd.DataFrame,
    *,
    seed: int,
    sensor_noise: float | None = None,
    missing_modality_rate: float | None = None,
    concept_drift: float | None = None,
    resource_availability_floor: float | None = None,
    maintenance_delay: int | None = None,
) -> pd.DataFrame:
    """Regenerate a matched dataset under one named sensitivity condition."""
    """Regenerate a matched-size scenario under one robustness condition."""

    return generate_laser_dataset(
        n_cases=int(base["case_id"].nunique()),
        episode_length=int(base.groupby("case_id").size().median()),
        seed=seed,
        ood_fraction=float((base["distribution"] == "ood").mean()),
        options=SimulatorOptions(
            sensor_noise=0.018 if sensor_noise is None else sensor_noise,
            missing_modality_rate=0.0 if missing_modality_rate is None else missing_modality_rate,
            concept_drift=0.0 if concept_drift is None else concept_drift,
            resource_availability_floor=0.30 if resource_availability_floor is None else resource_availability_floor,
            maintenance_delay=0 if maintenance_delay is None else maintenance_delay,
        ),
    )
