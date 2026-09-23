"""Fast regression tests for reproducibility, environment behavior, and auditability."""

from __future__ import annotations

import numpy as np

from .audit import audit_report, hash_trace
from .environment import LaserWeldingSchedulingEnv
from .simulator import generate_laser_dataset, validate_dataset


def test_seeded_dataset_is_reproducible_and_ood_isolated():
    """Verify identical seeds reproduce the dataset and preserve OOD isolation."""
    first = generate_laser_dataset(n_cases=12, episode_length=8, seed=123, ood_fraction=0.25)
    second = generate_laser_dataset(n_cases=12, episode_length=8, seed=123, ood_fraction=0.25)
    assert first.equals(second)
    report = validate_dataset(first)
    assert report["features_finite"] is True
    assert report["ood_isolated"] is True
    assert set(first.loc[first["split"] == "ood", "distribution"]) == {"ood"}


def test_environment_accepts_all_actions_and_returns_finite_rewards():
    """Verify all five scheduling actions produce finite, correctly tagged rewards."""
    data = generate_laser_dataset(n_cases=8, episode_length=6, seed=9, ood_fraction=0.25)
    env = LaserWeldingSchedulingEnv(data.loc[data["split"] == "test"], {"risk": 3, "downtime": 1, "cost": 0.8, "unnecessary_maintenance": 1, "human_review": 0.15, "failure": 45}, episode_length=6)
    env.reset(seed=9)
    for action in range(5):
        env.reset(seed=9)
        _, reward, _, info = env.step(action)
        assert np.isfinite(reward)
        assert info["action"] == action


def test_hash_chained_trace_is_reconstructable():
    """Verify a one-step trace can be hashed and audited without missing rows."""
    data = generate_laser_dataset(n_cases=8, episode_length=6, seed=9, ood_fraction=0.25)
    env = LaserWeldingSchedulingEnv(data.loc[data["split"] == "test"], {"risk": 3, "downtime": 1, "cost": 0.8, "unnecessary_maintenance": 1, "human_review": 0.15, "failure": 45}, episode_length=6)
    env.reset(seed=9)
    _, _, _, info = env.step(0)
    trace = hash_trace(__import__("pandas").DataFrame([{**info, "policy": "test", "seed": 9, "reward": 0.0}]))
    report = audit_report(trace)
    assert report["completeness_rate"] == 1.0
    assert report["hash_chain_valid"] is True
