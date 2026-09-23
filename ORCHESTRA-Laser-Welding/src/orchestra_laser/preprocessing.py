from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .synthetic_data import generate_laser_welding_data


def load_or_create_dataset(config: dict, raw_csv: Path | None = None) -> pd.DataFrame:
    if raw_csv and raw_csv.exists():
        return pd.read_csv(raw_csv)
    return generate_laser_welding_data(
        n_samples=int(config.get("n_samples", 600)),
        seed=int(config.get("random_seed", 42)),
    )


def clean_laser_welding_data(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in feature_columns:
        if col not in df.columns:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = df[col].fillna(df[col].median() if not df[col].isna().all() else 0.0)
    return df


def train_test_split(df: pd.DataFrame, train_fraction: float = 0.75, seed: int = 42):
    rng = np.random.default_rng(seed)
    idx = np.arange(len(df))
    rng.shuffle(idx)
    cut = int(len(idx) * train_fraction)
    return df.iloc[idx[:cut]].reset_index(drop=True), df.iloc[idx[cut:]].reset_index(drop=True)


class StandardScalerLite:
    def __init__(self):
        self.mean_: np.ndarray | None = None
        self.std_: np.ndarray | None = None

    def fit(self, x: np.ndarray) -> "StandardScalerLite":
        self.mean_ = x.mean(axis=0)
        self.std_ = x.std(axis=0)
        self.std_[self.std_ == 0] = 1.0
        return self

    def transform(self, x: np.ndarray) -> np.ndarray:
        if self.mean_ is None or self.std_ is None:
            raise RuntimeError("Scaler has not been fitted.")
        return (x - self.mean_) / self.std_

    def fit_transform(self, x: np.ndarray) -> np.ndarray:
        return self.fit(x).transform(x)

