"""Baseline, full ORCHESTRA, and ablation scheduling policies."""

from __future__ import annotations

import pandas as pd

from .review import action_from_urgency


def corrective_policy(row: pd.Series) -> int:
    """Apply urgent intervention when the latent urgency is at least 78."""
    return 4 if float(row["maintenance_urgency_score"]) >= 78 else 0


def periodic_policy_factory(interval: int = 8):
    """Return a stateful policy that applies minor maintenance periodically."""
    counter = {"step": 0}

    def policy(row: pd.Series) -> int:
        """Return minor maintenance at the configured periodic interval."""
        counter["step"] += 1
        return 2 if counter["step"] % interval == 0 else 0

    return policy


def alert_only_policy(row: pd.Series) -> int:
    """React only to high predicted urgency and otherwise do nothing."""
    urgency = float(row.get("predicted_urgency", row["maintenance_urgency_score"]))
    return 4 if urgency >= 84 else 3 if urgency >= 68 else 0


def rule_based_policy(row: pd.Series) -> int:
    """Use urgency and uncertainty thresholds without simulated human review."""
    urgency = float(row.get("predicted_urgency", row["maintenance_urgency_score"]))
    uncertainty = float(row.get("uncertainty", 0.0))
    if urgency >= 84:
        return 4
    if urgency >= 68:
        return 3
    if urgency >= 52 or uncertainty >= 0.65:
        return 2
    if urgency >= 35 or uncertainty >= 0.38:
        return 1
    return 0


def predicted_urgency_policy(row: pd.Series) -> int:
    """Prediction-only scheduling control; it is not a trained PPO policy."""
    urgency = float(row.get("predicted_urgency", row["maintenance_urgency_score"]))
    return action_from_urgency(urgency, float(row.get("uncertainty", 0.0)), full_review=False)


# Backwards-compatible import for local experiments written before the name was
# corrected.  The runner uses ``predicted_urgency_policy`` explicitly.
ppo_only_policy = predicted_urgency_policy


def full_orchestra_policy(row: pd.Series) -> int:
    """Use adjusted ORCHESTRA urgency and uncertainty with full review logic."""
    urgency = float(row.get("orchestra_urgency", row.get("predicted_urgency", row["maintenance_urgency_score"])))
    uncertainty = float(row.get("uncertainty", 0.0))
    return action_from_urgency(urgency, uncertainty, full_review=True)


def ablation_policy(row: pd.Series, variant: str) -> int:
    """Return the policy action for one named E6 component ablation."""
    if variant == "without_review":
        return predicted_urgency_policy(row)
    if variant == "without_ppo":
        return rule_based_policy(row)
    if variant == "without_xgboost":
        return rule_based_policy(row)
    if variant == "without_provenance":
        return full_orchestra_policy(row)
    if variant == "without_uncertainty_trigger":
        adjusted = row.copy()
        adjusted["uncertainty"] = 0.0
        return predicted_urgency_policy(adjusted)
    return full_orchestra_policy(row)
