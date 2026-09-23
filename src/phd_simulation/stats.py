from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def mean_ci(values: Iterable[float], confidence: float = 0.95) -> tuple[float, float, float]:
    array = np.asarray(list(values), dtype=float)
    if len(array) == 0:
        return float("nan"), float("nan"), float("nan")
    mean = float(array.mean())
    if len(array) == 1:
        return mean, mean, mean
    try:
        from scipy.stats import t

        critical = float(t.ppf((1 + confidence) / 2, len(array) - 1))
    except Exception:
        critical = 1.96
    half_width = critical * float(array.std(ddof=1)) / np.sqrt(len(array))
    return mean, mean - half_width, mean + half_width


def aggregate_metrics(frame: pd.DataFrame, group_columns: list[str], metric_columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for keys, group in frame.groupby(group_columns, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        base = dict(zip(group_columns, keys))
        for metric in metric_columns:
            mean, lower, upper = mean_ci(group[metric].to_numpy(dtype=float))
            base[f"{metric}_mean"] = mean
            base[f"{metric}_ci95_low"] = lower
            base[f"{metric}_ci95_high"] = upper
            base[f"{metric}_std"] = float(group[metric].std(ddof=1)) if len(group) > 1 else 0.0
        rows.append(base)
    return pd.DataFrame(rows)


def paired_test(frame: pd.DataFrame, metric: str, treatment: str, control: str, unit: str = "seed") -> dict[str, float | str]:
    pivot = frame.pivot_table(index=unit, columns="policy", values=metric, aggfunc="mean")
    if treatment not in pivot.columns or control not in pivot.columns:
        return {"metric": metric, "treatment": treatment, "control": control, "n": 0, "difference_mean": np.nan, "p_value": np.nan, "test": "unavailable"}
    differences = (pivot[treatment] - pivot[control]).dropna().to_numpy(dtype=float)
    p_value = np.nan
    test = "paired_bootstrap"
    try:
        from scipy.stats import wilcoxon

        if len(differences) >= 2 and np.any(differences != 0):
            p_value = float(wilcoxon(differences, zero_method="wilcox", alternative="two-sided").pvalue)
            test = "wilcoxon_signed_rank"
    except Exception:
        pass
    return {
        "metric": metric,
        "treatment": treatment,
        "control": control,
        "n": int(len(differences)),
        "difference_mean": float(differences.mean()) if len(differences) else np.nan,
        "p_value": p_value,
        "test": test,
    }


def bootstrap_difference_ci(
    frame: pd.DataFrame,
    *,
    metric: str,
    treatment: str,
    control: str,
    unit: str = "seed",
    samples: int = 2000,
    seed: int = 42,
) -> dict[str, float | int]:
    pivot = frame.pivot_table(index=unit, columns="policy", values=metric, aggfunc="mean")
    if treatment not in pivot.columns or control not in pivot.columns:
        return {"n": 0, "difference_mean": np.nan, "ci95_low": np.nan, "ci95_high": np.nan}
    differences = (pivot[treatment] - pivot[control]).dropna().to_numpy(dtype=float)
    if len(differences) == 0:
        return {"n": 0, "difference_mean": np.nan, "ci95_low": np.nan, "ci95_high": np.nan}
    rng = np.random.default_rng(seed)
    draws = rng.choice(differences, size=(samples, len(differences)), replace=True).mean(axis=1)
    return {
        "n": int(len(differences)),
        "difference_mean": float(differences.mean()),
        "ci95_low": float(np.quantile(draws, 0.025)),
        "ci95_high": float(np.quantile(draws, 0.975)),
    }
