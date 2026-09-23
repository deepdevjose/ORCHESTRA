from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .preprocessing import StandardScalerLite


@dataclass
class RegressionMetrics:
    mae: float
    rmse: float
    r2: float


class NumpyRidgeRegressor:
    """Small no-dependency fallback model for smoke tests and early drafts."""

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.coef_: np.ndarray | None = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> "NumpyRidgeRegressor":
        x_aug = np.c_[np.ones(len(x)), x]
        eye = np.eye(x_aug.shape[1])
        eye[0, 0] = 0
        self.coef_ = np.linalg.pinv(x_aug.T @ x_aug + self.alpha * eye) @ x_aug.T @ y
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        if self.coef_ is None:
            raise RuntimeError("Model has not been fitted.")
        x_aug = np.c_[np.ones(len(x)), x]
        return x_aug @ self.coef_


class PredictiveAgent:
    def __init__(self, feature_columns: list[str], prefer_xgboost: bool = True):
        self.feature_columns = feature_columns
        self.scaler = StandardScalerLite()
        self.model_name = "numpy_ridge"
        self.model = NumpyRidgeRegressor(alpha=2.5)

        if prefer_xgboost:
            try:
                from xgboost import XGBRegressor

                self.model = XGBRegressor(
                    n_estimators=180,
                    max_depth=4,
                    learning_rate=0.05,
                    subsample=0.9,
                    colsample_bytree=0.9,
                    objective="reg:squarederror",
                    random_state=42,
                )
                self.model_name = "xgboost"
            except Exception:
                pass

    def fit(self, df: pd.DataFrame) -> "PredictiveAgent":
        x = df[self.feature_columns].to_numpy(dtype=float)
        y = df["maintenance_urgency_score"].to_numpy(dtype=float)
        x_scaled = self.scaler.fit_transform(x)
        self.model.fit(x_scaled, y)
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        x = df[self.feature_columns].to_numpy(dtype=float)
        pred = self.model.predict(self.scaler.transform(x))
        return np.clip(np.asarray(pred, dtype=float), 0, 100)

    def evaluate(self, df: pd.DataFrame) -> RegressionMetrics:
        y = df["maintenance_urgency_score"].to_numpy(dtype=float)
        pred = self.predict(df)
        mae = float(np.mean(np.abs(y - pred)))
        rmse = float(np.sqrt(np.mean((y - pred) ** 2)))
        denom = np.sum((y - y.mean()) ** 2)
        r2 = float(1.0 - np.sum((y - pred) ** 2) / denom) if denom > 0 else 0.0
        return RegressionMetrics(mae=mae, rmse=rmse, r2=r2)

    def save_report(self, path: Path, metrics: RegressionMetrics) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model_name,
            "mae": metrics.mae,
            "rmse": metrics.rmse,
            "r2": metrics.r2,
            "features": self.feature_columns,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

