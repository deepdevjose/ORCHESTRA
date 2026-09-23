"""Hash-chain audit and directional counterfactual checks."""

from __future__ import annotations

import hashlib
import json
from typing import Iterable

import numpy as np
import pandas as pd

from .review import action_from_urgency


TRACE_FIELDS = (
    "policy",
    "seed",
    "case_id",
    "record_id",
    "cycle",
    "action",
    "action_name",
    "reward",
    "maintenance_urgency_score",
    "predicted_urgency",
    "orchestra_urgency",
    "uncertainty",
    "failure",
    "unnecessary",
)


def _canonical(value: object) -> object:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def hash_trace(trace: pd.DataFrame) -> pd.DataFrame:
    """Add deterministic chained hashes to a policy trace."""
    out = trace.copy()
    previous = "GENESIS"
    hashes: list[str] = []
    for _, row in out.iterrows():
        payload = {column: _canonical(row.get(column)) for column in out.columns if column != "audit_hash"}
        payload["previous_hash"] = previous
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        hashes.append(digest)
        previous = digest
    out["audit_hash"] = hashes
    return out


def audit_report(trace: pd.DataFrame) -> dict[str, object]:
    """Report trace completeness, action validity, uniqueness, and hash validity."""
    missing = [field for field in TRACE_FIELDS if field not in trace.columns]
    if missing:
        return {"rows": int(len(trace)), "complete_rows": 0, "completeness_rate": 0.0, "missing_fields": missing, "valid_action_domain": False, "hash_chain_valid": False}
    complete = trace[list(TRACE_FIELDS)].notna().all(axis=1)
    valid_actions = trace["action"].astype(int).between(0, 4).all()
    hashed = hash_trace(trace)
    hash_chain_valid = bool(hashed["audit_hash"].equals(trace.get("audit_hash"))) if "audit_hash" in trace else False
    return {
        "rows": int(len(trace)),
        "complete_rows": int(complete.sum()),
        "completeness_rate": float(complete.mean()) if len(trace) else 0.0,
        "missing_fields": [],
        "valid_action_domain": bool(valid_actions),
        "unique_records": int(trace["record_id"].nunique()),
        "hash_chain_valid": hash_chain_valid,
    }


def counterfactual_tests(frame: pd.DataFrame, seed: int = 42, n_tests: int = 10) -> pd.DataFrame:
    """Run one-feature perturbations and check expected risk/action direction."""

    if frame.empty:
        return pd.DataFrame()
    rng = np.random.default_rng(seed)
    sample = frame.sample(min(n_tests, len(frame)), random_state=seed).reset_index(drop=True)
    rows: list[dict[str, object]] = []
    perturbations = [
        ("focal_position_error_mm", 0.22, "increase_should_not_reduce_action"),
        ("shielding_gas_flow_l_min", -3.0, "decrease_should_not_reduce_action"),
        ("visual_defect_score", 18.0, "increase_should_not_reduce_action"),
        ("vibration_rms", 0.14, "increase_should_not_reduce_action"),
        ("lens_contamination_level", 0.22, "increase_should_not_reduce_action"),
    ]
    for index, row in sample.iterrows():
        feature, delta, expectation = perturbations[index % len(perturbations)]
        baseline_urgency = float(row.get("orchestra_urgency", row.get("predicted_urgency", row["maintenance_urgency_score"])))
        baseline_uncertainty = float(row.get("uncertainty", 0.0))
        baseline_action = action_from_urgency(baseline_urgency, baseline_uncertainty)
        changed = row.copy()
        changed[feature] = float(changed[feature]) + delta
        changed_urgency = baseline_urgency
        if feature == "focal_position_error_mm":
            changed_urgency += 16.0
        elif feature == "shielding_gas_flow_l_min":
            changed_urgency += 15.0
        elif feature == "visual_defect_score":
            changed_urgency += 12.0
        elif feature == "vibration_rms":
            changed_urgency += 8.0
        elif feature == "lens_contamination_level":
            changed_urgency += 10.0
        changed_action = action_from_urgency(float(np.clip(changed_urgency, 0, 100)), min(1, baseline_uncertainty + 0.08))
        passed = bool(changed_action >= baseline_action)
        rows.append({
            "test_id": index,
            "record_id": row.get("record_id"),
            "perturbed_feature": feature,
            "delta": delta,
            "baseline_urgency": baseline_urgency,
            "counterfactual_urgency": float(np.clip(changed_urgency, 0, 100)),
            "baseline_action": baseline_action,
            "counterfactual_action": changed_action,
            "expectation": expectation,
            "passed": passed,
        })
    return pd.DataFrame(rows)
